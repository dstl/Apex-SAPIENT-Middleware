#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import json
import logging
import os
import random
import struct
import sys
import uuid
from collections import defaultdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Collection, Dict, List, Optional, Set

import trio
import ulid
from google.protobuf.json_format import MessageToDict, ParseDict

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.append(ROOT_DIR)


from sapient_apex_server.apex import ApexMain
from sapient_apex_server.time_util import datetime_to_str
from sapient_apex_server.trio_util import receive_size_prefixed
from sapient_msg.latest.sapient_message_pb2 import SapientMessage
from tests.msg_templates import (
    get_detection_message_template,
    get_register_template,
    get_status_message_template,
    get_task_message_template,
)

logger = logging.getLogger("apex_route_test")


class NodeType(Enum):
    CHILD = 1
    PEER = 2
    PRT_ALL = 3  # Gets all messages
    PRT_HL = 4  # Only gets high-level (DMM) messages
    RCRD = 5


# Configuration of the test - change these to tweak the test settings.
_IP_ADDRESS = os.environ.get("APEX_HOST", "127.0.0.1")  # Set APEX_HOST to Apex when in Docker
_START_OWN_APEX = True  # Set to False to use externally started Apex instance
_LOG_LEVEL = logging.DEBUG  # Setting to DEBUG logs all messages, slows things a lot
_CONNECTION_LIMIT = 128 * 1024 * 1024
COUNT_BY_NODE_TYPE = {
    NodeType.CHILD: 3,
    NodeType.PEER: 2,
    NodeType.PRT_HL: 2,
    NodeType.PRT_ALL: 2,
    NodeType.RCRD: 2,
}
PORT_BY_NODE_TYPE = {
    NodeType.CHILD: 5010,
    NodeType.PEER: 5001,
    NodeType.PRT_HL: 5002,
    NodeType.PRT_ALL: 5004,
    NodeType.RCRD: 5003,
}
MESSAGE_COUNT = 5  # Count of all messages sent by every connection, not including tasks.
TASK_MESSAGE_COUNT = 2  # Count of task messages sent from each DMM to each ASM
MAX_DELAY = 0.05


def get_messages(node_id: uuid.UUID, node_type: NodeType, asm_node_ids: Collection[uuid.UUID]):
    """Returns test protobuf messages to write to each connection (as list of JSON dicts)."""
    result = []
    count_remaining = MESSAGE_COUNT
    if node_type in (NodeType.CHILD, NodeType.PEER):
        result.append(get_register_template(node_id=str(node_id)))
        count_remaining -= 1
    result.extend(
        (
            get_status_message_template(node_id=str(node_id), report_id=ulid.new().str)
            if i % 10 == 0
            else get_detection_message_template(
                node_id=str(node_id), report_id=ulid.new().str, object_id=ulid.new().str
            )
        )
        for i in range(count_remaining)
    )
    if node_type == NodeType.PEER:
        for asm_node_id in asm_node_ids:
            result.extend(
                get_task_message_template(
                    str(node_id), ulid.new().str, ulid.new().str, str(asm_node_id)
                )
                for _ in range(TASK_MESSAGE_COUNT)
            )
    return result


class ApexRouteTestRunner:
    """Runs the routing tests."""

    def __init__(self):
        """Initialises the class by just setting some member variables.

        No actual sending or receiving (or testing) is done here. But this function does decide
        what connections will be established and what messages will be sent.
        """

        # Establish what node connections we will use, stored both as dictionary mapping from node
        # type to all node IDs for that type, and dictionary mapping back from node ID to its type.
        self.node_type_to_ids: Dict[NodeType, List[uuid.UUID]] = {
            node_type: [uuid.uuid4() for _ in range(count_for_type)]
            for node_type, count_for_type in COUNT_BY_NODE_TYPE.items()
        }
        self.node_id_to_type: Dict[uuid.UUID, NodeType] = {
            node_id: node_type
            for node_type, node_ids in self.node_type_to_ids.items()
            for node_id in node_ids
        }

        # Also decide which messages to send (stored as the JSON dictionary representation).
        self.messages_to_send: Dict[uuid.UUID, List[dict]] = {
            node_id: get_messages(node_id, node_type, self.node_type_to_ids[NodeType.CHILD])
            for node_id, node_type in self.node_id_to_type.items()
        }

        # Create a place to store messages received on each connection, keyed on recipient ID.
        self.messages_received = {node_id: [] for node_id in self.node_id_to_type.keys()}

        # Event to signal when all connections are established so sending may begin
        self.all_connections_open_event = trio.Event()

    async def run_all(self):
        """Runs the substantial content of the tests.

        This method establishes connections to Apex, sends messages through them, and records what
        messages are received. It requires that an instance of Apex is already running before it is
        called. The received messages are not checked for correctness here; that is done in check().
        """

        assert not self.all_connections_open_event.is_set()
        async with trio.open_nursery() as connection_nursery:
            async with trio.open_nursery() as writer_nursery:
                # Start all connections, waiting for each one to connect (using nursery.start())
                for node_id, node_type in self.node_id_to_type.items():
                    await connection_nursery.start(
                        self._run_one_connection, node_type, node_id, writer_nursery
                    )
                # ALl have connected, so open the floodgates to messages
                self.all_connections_open_event.set()

            # When we get here, that means that all writers have finished. Give the readers a moment
            # more to finish processing any unread messages then shut everything down.
            await trio.sleep(0.25)
            connection_nursery.cancel_scope.cancel()

    async def _run_one_connection(
        self,
        node_type: NodeType,
        node_id: uuid.UUID,
        writer_nursery: trio.Nursery,
        task_status,
    ):
        """Opens a single connection, and reads and (in a separate task) writes messages on it."""
        node_str = f"{node_type.name} {str(node_id)[:4]}"
        port = PORT_BY_NODE_TYPE[node_type]
        connection_msg_count = 0

        try:
            # Establish this connection
            logger.info(f"{node_str} reader - connecting to {_IP_ADDRESS}:{port}")
            async with await trio.open_tcp_stream(_IP_ADDRESS, port) as stream:
                logger.info(f"{node_str} reader - connected")
                task_status.started()

                # Start the writer task
                writer_nursery.start_soon(
                    self._run_one_writer,
                    node_str,
                    stream,
                    self.messages_to_send[node_id],
                )

                # Read all messages until this task is cancelled
                read_buffer = bytearray()
                logger.info(f"{node_str} reader - starting read loop")
                while True:
                    # Wait for message to be received
                    msg_bytes = await receive_size_prefixed(
                        stream, read_buffer, max_size=_CONNECTION_LIMIT
                    )

                    # Convert to dictionary and save for later checking
                    msg_proto = SapientMessage()
                    msg_proto.ParseFromString(bytes(msg_bytes))
                    msg_dict = MessageToDict(msg_proto, preserving_proto_field_name=True)
                    self.messages_received[node_id].append(msg_dict)
                    connection_msg_count += 1
                    logger.debug("%s reader - received: %s", node_str, msg_dict)

        except Exception as e:
            logger.error(f"{node_str} reader - got {type(e).__name__}: {e}")
            raise
        finally:
            logger.info(
                f"{node_str} reader - finished after reading {connection_msg_count} messages"
            )

    async def _run_one_writer(
        self,
        node_str: str,
        stream: trio.abc.SendStream,
        messages: list,
    ):
        """Writes a given list of messages to a stream."""

        # Wait for all connections to be established before writing, so no messages are missed.
        await self.all_connections_open_event.wait()
        try:
            logger.info(f"{node_str} writer - started")

            for message_dict in messages:
                await trio.sleep(random.uniform(MAX_DELAY / 2, MAX_DELAY))

                message_dict["timestamp"] = datetime_to_str(datetime.utcnow())
                logger.debug("%s writer - writing: %s", node_str, message_dict)

                message_proto = ParseDict(message_dict, SapientMessage())
                msg_bytes = message_proto.SerializeToString()
                packed_len = struct.pack("<I", len(msg_bytes))
                await stream.send_all(packed_len + msg_bytes)

            logger.info(f"{node_str} writer - all {len(messages)} messages written")

        except Exception as e:
            logger.error(f"{node_str} writer - got {type(e).__name__}: {e}")
            raise
        finally:
            logger.info(f"{node_str} writer - done")

    def check_all(self):
        """Checks all connections received the messages they should have.

        This is the actual test. It compares messages received by each connection against the
        messages sent by other connections that were expected to be routed to it.
        """
        # What are we checking?  (in all cases, exclude from own node_id)
        # to ASM --- from DMM: (only dest_id==me); from Apex: reg ack
        # to DMM --- from ASM: all; from prnt_hl: all; from prnt_all: all
        # to prnt_hl --- from DMM (only dest_id==None)
        # to prnt_all --- from ASM, DMM, prnt_hl, prnt_all: all, from Apex: reg ack
        # to recorder --- nothing received
        source_node_types_by_destination_type = {
            NodeType.CHILD: {NodeType.PEER},
            NodeType.PEER: {NodeType.CHILD, NodeType.PRT_HL, NodeType.PRT_ALL},
            NodeType.PRT_HL: {NodeType.PEER},
            NodeType.PRT_ALL: set(NodeType),
            NodeType.RCRD: set(),
        }

        for node_id, node_type in self.node_id_to_type.items():
            self._check_messages_received_by_connection(
                node_type,
                node_id,
                source_node_types_by_destination_type[node_type],
                destination_id_must_be_absent=node_type == NodeType.PRT_HL,
                destination_id_must_be_present=node_type == NodeType.CHILD,
                has_registration_acks=node_type in (NodeType.CHILD, NodeType.PEER),
            )

    def _group_messages_by_sender_type_and_id(
        self, destination_node_id: uuid.UUID
    ) -> Dict[Optional[NodeType], Dict[uuid.UUID, list]]:
        """Groups messages received on a connection into a two-level nested dictionary.

        The outer dictionary is keyed on source connection type (or None if not known, which is
        presumably from Apex itself) while the inner dictionary is keyed on source node ID.
        """
        messages = self.messages_received[destination_node_id]
        result = defaultdict(lambda: defaultdict(list))
        for msg in messages:
            sender_node_id = uuid.UUID(msg["node_id"])
            node_type = self.node_id_to_type.get(sender_node_id)
            result[node_type][sender_node_id].append(msg)
        return result

    def _check_messages_received_by_connection(
        self,
        destination_node_type: NodeType,
        destination_node_id: uuid.UUID,
        source_node_types: Set[NodeType],
        destination_id_must_be_absent: bool = False,
        destination_id_must_be_present: bool = False,
        has_registration_acks: bool = False,
    ):
        """Checks all the messages received by a connection are correct.

        To do this, we pick through what messages were received and compare against what we would
        expect based on what messages we know were sent by the other connections.
        """
        messages_by_sender_type_and_id = self._group_messages_by_sender_type_and_id(
            destination_node_id
        )

        # Record number of checks, so that log can provide confidence checking was done.
        checked_source_id_count = 0
        checked_message_count = 0

        # Extremely careful check of what types of connections were expected to have sent messages
        # to this connection. Roughly speaking, it should be source_node_types, but in fact may be
        # a subset if there were not configured to be any connections of that type, or only one of
        # that type it's the same as destination type (i.e. a single PRNT_ALL connection).
        expected_source_node_types = {
            node_type
            for node_type, node_id_list in self.node_type_to_ids.items()
            if node_type in source_node_types and len(set(node_id_list) - {destination_node_id}) > 0
        }
        if has_registration_acks:
            expected_source_node_types.add(None)
        assert messages_by_sender_type_and_id.keys() == expected_source_node_types
        checked_source_type_count = len(expected_source_node_types)

        # Registration ack from Apex
        if has_registration_acks:
            assert len(messages_by_sender_type_and_id[None]) == 1
            apex_id, apex_messages = messages_by_sender_type_and_id[None].popitem()
            assert len(apex_messages) == 1
            assert "registration_ack" in apex_messages[0]
            assert apex_messages[0].get("destination_id") == str(destination_node_id)
            del messages_by_sender_type_and_id[None]
            checked_source_id_count += 1
            checked_message_count += 1

        for node_type, node_id_to_received in messages_by_sender_type_and_id.items():
            expected_node_ids = set(self.node_type_to_ids[node_type]) - {destination_node_id}
            assert set(node_id_to_received.keys()) - {destination_node_id} == expected_node_ids
            checked_source_id_count += len(expected_node_ids)

            for source_node_id, received_messages in node_id_to_received.items():
                if destination_id_must_be_present:
                    expected_messages = [
                        msg
                        for msg in self.messages_to_send[source_node_id]
                        if msg.get("destination_id") == str(destination_node_id)
                    ]
                elif destination_id_must_be_absent:
                    expected_messages = [
                        msg
                        for msg in self.messages_to_send[source_node_id]
                        if msg.get("destination_id") is None
                    ]
                else:
                    expected_messages = self.messages_to_send[source_node_id]
                checked_message_count += len(expected_messages)
                assert received_messages == expected_messages

        logger.info(
            f"{destination_node_type.name} {str(destination_node_id)[:4]}: "
            + f"checked types: {checked_source_type_count}, "
            + f"connections: {checked_source_id_count}, "
            + f"messages: {checked_message_count}"
        )


def launch_apex():
    config_filename = TESTS_DIR + "/resources/config_files/apex_config_routing.json"
    logger.info("Using config file: " + config_filename)
    config_path = Path(config_filename)
    if not config_path.exists():
        logger.critical("Error: Could not find config file")
    with config_path.open("rb") as f:
        result = json.load(f)

    # Remove "detection_timestamp_reasonable" to prevent validation issues in test
    validation_config = result.get("validationOptions", {})
    types_config = validation_config.get("validationTypes", [])
    if "detection_timestamp_reasonable" in types_config:
        types_config.remove("detection_timestamp_reasonable")

    logger.info("Using config: \n" + json.dumps(result, indent=2))
    return ApexMain(result)


def test_apex():
    if _START_OWN_APEX:
        apex = launch_apex()
        startup_success = apex.startup_complete.wait(10)
        assert startup_success, "Apex failed to start"
        logger.info("\n***** Apex Startup Complete *****\n Beginning Testing ...\n")
    else:
        logger.info("Beginning testing ...")
        apex = None
    try:
        test_runner = ApexRouteTestRunner()
        trio.run(test_runner.run_all)
        test_runner.check_all()
    finally:
        if apex is not None:
            logger.info("\nShutting Down Apex")
            apex.shutdown()


if __name__ == "__main__":
    logging.basicConfig(level=_LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    test_apex()
