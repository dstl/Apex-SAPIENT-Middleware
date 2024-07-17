#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

import trio
from google.protobuf.json_format import ParseDict
from pytest import fixture

from sapient_apex_replay.replay import read_proto_message, read_xml_message, start_replayer
from sapient_apex_server.sqlite_saver import SqliteSaver
from sapient_apex_server.structures import ConnectionRecord, ReceivedDataRecord, MessageFormat
from sapient_apex_server.time_util import datetime_to_str
from sapient_apex_server.translator.id_generator import IdGenerator
from sapient_apex_server.validate_proto import ValidationOptions, Validator
from sapient_msg.latest.sapient_message_pb2 import SapientMessage
from tests.test_msg_parsing import parse_proto_partial as parse_proto
from tests.test_routing import NodeType, get_messages

_IP_ADDRESS = os.environ.get("APEX_HOST", "127.0.0.1")
_REPLAY_TEST_PORT = 5004
_LOG_MESSAGES = False  # Slows things down a lot
logger = logging.getLogger("apex_client")
message_count = 11
id_generator = IdGenerator({})


@fixture(params=["PROTO", "XML"])
def replay_test_config(tmpdir, request):
    return {
        "log_level": "INFO",
        "filename": str(tmpdir / "sqlite.sql"),
        "is_outbound": False,
        "host": "127.0.0.1",
        "port": 5004,
        "topic": "apex_topic",
        "wait_every_n_messages": 1,
        "send_pending_on_exit": True,
        "start_time": datetime_to_str(datetime.utcnow()),
        "end_time": datetime_to_str(datetime.utcnow() + timedelta(0, 60)),
        "speed_multiplier": 2,
        "format": f"{request.param}",
        "icd_version": "BSI Flex 335 v2.0",
    }


@dataclass
class SavedMessages:
    first_message_time: datetime
    messages_bytes: List[bytes]


async def start_receiver(received_messages: list, config: dict):
    """Connects to port TCP port and records all messages received"""
    stream = await trio.open_tcp_stream(_IP_ADDRESS, _REPLAY_TEST_PORT)
    message_format = MessageFormat[config.get("format", "PROTO")]
    logger.info(f"Connection opened for {message_format}")
    read_buffer = bytearray()
    while True:
        try:
            if message_format == MessageFormat.PROTO:
                msg = await read_proto_message(stream, read_buffer)
            elif message_format == MessageFormat.XML:
                msg = await read_xml_message(stream, read_buffer)

            received_messages.append(msg)
        except EOFError:
            logger.info("Connection closed by caller")
            return
        if _LOG_MESSAGES:
            logger.info("Received message:\n" + str(msg))
        else:
            logger.debug("Got message")


async def start_all(first_message_time: datetime, config: dict):
    """Starts a task running the replay script and another receiving the replayed messages"""
    received_messages = []

    config = config.copy()
    config["start_time"] = datetime_to_str(first_message_time + timedelta(seconds=0.5))

    async with trio.open_nursery() as nursery:
        await nursery.start(start_replayer, config)
        nursery.start_soon(start_receiver, received_messages, config)

    return received_messages


def build_msg_db(config):
    node_id = uuid.uuid4()
    msg_list = []
    validator = Validator(ValidationOptions())

    # Set first message time to 1 second in the past, so we can start the replay script
    # just afterwards and test that it still looks back for the cached registration.
    initial_time = datetime.utcnow() - timedelta(seconds=1)

    # Open DB
    db_saver = SqliteSaver(config["filename"], True)

    # Insert connection record into database
    db_saver.insert_connection(
        ConnectionRecord(
            id=1, type="CHILD", format="PROTO", peer="127.0.0.1:12345", time=initial_time
        )
    )
    # Write message to DB
    for i, msg in enumerate(get_messages(node_id, NodeType.CHILD, asm_node_ids=())):
        msg_bytes = ParseDict(msg, SapientMessage()).SerializeToString()
        raw_message = ReceivedDataRecord(
            connection_id=1,
            message_id=i,
            timestamp=initial_time if i == 0 else datetime.utcnow(),
            data_bytes=msg_bytes,
        )

        msg_info = parse_proto(
            msg_data=raw_message,
            validator=validator,
            generator=id_generator,
            enable_message_conversion=True,  # so that message.xml is filled in
        )
        msg_list.append(msg_info)

    db_saver.insert_message_multi(msg_list)
    db_saver.close()

    return SavedMessages(initial_time, [msg.received.data_bytes for msg in msg_list])


def test_replay_script(replay_test_config):
    """This test executes the replay script, connects to the replay scripts TCP port,
    receives all messages from the replay script, and finally compares the received
    messages to the messages stored within the SQL DB to ensure they are valid
    """
    saved_messages = build_msg_db(replay_test_config)
    received_messages = trio.run(start_all, saved_messages.first_message_time, replay_test_config)

    message_format = MessageFormat[replay_test_config.get("format", "PROTO")]

    if message_format == MessageFormat.PROTO:
        assert received_messages == saved_messages.messages_bytes
    elif message_format == MessageFormat.XML:
        for received_message_bytes in received_messages:
            received_message = received_message_bytes.decode("utf8")
            # Just checking for the presense of the xml header, the remaining contents
            # should be already be validated in other tests.
            assert received_message.find("<?xml version") == 0
