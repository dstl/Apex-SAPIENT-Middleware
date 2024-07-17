#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import functools
import json
import logging
import os
import struct
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Union

import pytest
import trio
import ulid
from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.message import Message

from sapient_apex_server.apex import ApexMain
from sapient_apex_server.parse_proto import parse_proto
from sapient_apex_server.parse_xml import parse_xml
from sapient_apex_server.structures import (
    ErrorSeverity,
    MessageFormat,
    MessageRecord,
    ReceivedDataRecord,
)
from sapient_apex_server.time_util import datetime_to_str
from sapient_apex_server.translator.id_generator import IdGenerator
from sapient_apex_server.trio_util import receive_size_prefixed, receive_until
from sapient_apex_server.validate_proto import ValidationOptions, Validator
from sapient_apex_server.xml_conversion.to_xml import message_to_element
from sapient_msg.latest.sapient_message_pb2 import SapientMessage

from tests.msg_templates import (
    get_detection_message_template,
    get_invalid_status_message_template,
    get_register_template,
    get_status_message_template,
    get_task_ack_message_template,
)

logger = logging.getLogger("apex_tests")
_CONNECTION_LIMIT = 128 * 1024 * 1024 * 1024
_IP_ADDRESS = os.environ.get("APEX_HOST", "127.0.0.1")
config_filename = str(Path(__file__).parent / "resources/config_files/apex_config_conversions.json")
parse_xml_partial = functools.partial(parse_xml, enable_sensor_id_auto=False)
parse_proto_partial = functools.partial(parse_proto, enable_message_conversion=True)


def get_config(filename: str) -> dict:
    logger.info("Using config file: " + filename)
    config_path = Path(filename)
    if not config_path.exists():
        logger.critical("Error: Could not find config file")
    with config_path.open("rb") as f:
        result = json.load(f)
        logger.info(result)
    logger.info("Using config: \n" + json.dumps(result, indent=2))
    return result


def launch_apex():
    config = get_config(config_filename)

    return ApexMain(config)


@pytest.fixture
async def apex():
    with trio.fail_after(20):
        apex = launch_apex()
        apex.startup_complete.wait()
        yield apex
        apex.shutdown()


def json_to_xml(message_class: type, json_dict: dict) -> ET.Element:
    msg = message_class()
    ParseDict(json_dict, msg)
    elem = message_to_element(msg.node_id)
    return elem


def json_to_proto(message_class: type, json_dict: dict) -> Message:
    msg = message_class()
    ParseDict(json_dict, msg)
    return msg


async def send_msg_to_apex(
    message, send_stream: trio.SocketStream, msg_format
) -> Union[ET.Element, Message, SapientMessage]:
    if msg_format is MessageFormat.PROTO:
        send_msg_proto = message.SerializeToString()
        packed_len = struct.pack("<I", len(send_msg_proto))
        msg_bytes = packed_len + send_msg_proto
    else:
        msg_bytes = ET.tostring(message, encoding="utf8", xml_declaration=True) + b"\0"
    await send_stream.send_all(msg_bytes)

    return message


async def receive_msg_from_apex(
    rec_stream, receive_fn, parse_fn, read_buffer, validator, id_generator
) -> MessageRecord:
    rec_msg_bytes = None
    with trio.move_on_after(5):
        rec_msg_bytes = await receive_fn(
            rec_stream,
            read_buffer,
            delimiter=b"\0",
            max_size=_CONNECTION_LIMIT,
            return_delimiter=True,
        )
    if rec_msg_bytes is None:
        logger.error("No message received from stream")
        assert False

    msg_received = ReceivedDataRecord(0, 1, datetime.utcnow(), rec_msg_bytes)
    return parse_fn(msg_received, validator, id_generator)


def check_received_proto_matches_expected(rec_proto, expected_file):
    rec_proto_dict = MessageToDict(rec_proto)
    with open(expected_file) as file:
        expected_proto = json.load(file)
    # Remove common message fields
    for key in ["timestamp", "nodeId", "destinationId"]:
        try:
            del rec_proto_dict[key]
            del expected_proto[key]
        except KeyError:
            pass
    # Remove status report fields if message is a status report
    try:
        del rec_proto_dict["statusReport"]["reportId"]
        del expected_proto["statusReport"]["reportId"]
        del rec_proto_dict["statusReport"]["statusRegion"][0]["regionId"]
        del expected_proto["statusReport"]["statusRegion"][0]["regionId"]
    except KeyError:
        pass
    # Remove detection report fields if message is a detection
    try:
        del rec_proto_dict["detectionReport"]["objectId"]
        del expected_proto["detectionReport"]["objectId"]
        del rec_proto_dict["detectionReport"]["reportId"]
        del expected_proto["detectionReport"]["reportId"]
        del rec_proto_dict["detectionReport"]["taskId"]
        del expected_proto["detectionReport"]["taskId"]
    except KeyError:
        pass
    # Remove task id field if message is a task
    try:
        del rec_proto_dict["task"]["taskId"]
        del expected_proto["task"]["taskId"]
        del rec_proto_dict["task"]["region"][0]["regionId"]
        del expected_proto["task"]["region"][0]["regionId"]
    except KeyError:
        pass
    # Remove alert fields if message is an alert
    try:
        del rec_proto_dict["alert"]["alertId"]
        del expected_proto["alert"]["alertId"]
        del rec_proto_dict["alert"]["regionId"]
        del expected_proto["alert"]["regionId"]
    except KeyError:
        pass
    assert expected_proto == rec_proto_dict


def check_received_xml_matches_expected(rec_xml, expected_file):
    expected_xml = ET.parse(expected_file).getroot()
    for key in ["timestamp", "sourceID"]:
        if (elem := expected_xml.find(key)) is not None:
            expected_xml.remove(elem)
        if (elem := rec_xml.find(key)) is not None:
            rec_xml.remove(elem)
    ET.indent(expected_xml)
    ET.indent(rec_xml)
    assert ET.tostring(expected_xml) == ET.tostring(rec_xml)


async def send_registration_message(
    send_stream,
    rec_stream,
    msg_format,
    read_buffer,
    validator,
    id_generator,
    auto_sensor_id=False,
):
    if msg_format is MessageFormat.PROTO:
        message = json_to_proto(SapientMessage, get_register_template("1"))
        receive_fn = receive_size_prefixed
        parse_fn = parse_proto_partial
    else:
        # sensor_id is optional in SAPIENT v6, if not specified
        # we expect Apex to make one & send it back to the sensor
        # in the SensorRegistrationACK
        message = ET.parse("tests/resources/xml/registration.xml").getroot()
        if auto_sensor_id is True:
            message.remove(message.find("sensorID"))

        receive_fn = receive_until
        parse_fn = parse_xml_partial
    send_msg = await send_msg_to_apex(message, send_stream, msg_format)
    rec_msg = await receive_msg_from_apex(
        rec_stream,
        receive_until,
        parse_xml_partial,
        read_buffer,
        validator,
        id_generator,
    )
    assert rec_msg.parsed is not None
    assert rec_msg.parsed.parsed_xml is not None
    rec_msg_xml = rec_msg.parsed.parsed_xml

    if msg_format is MessageFormat.PROTO:
        assert rec_msg_xml.find("sensorID").text == "1000001"
        assert send_msg.node_id == "1"
        check_received_xml_matches_expected(
            rec_msg_xml,
            "tests/resources/xml/proto_converted/registration.xml",
        )
    else:
        if auto_sensor_id is not True:
            assert send_msg.find("sensorID").text == rec_msg_xml.find("sensorID").text

        assert send_msg.find("sensorType").text == rec_msg_xml.find("sensorType").text
        assert rec_msg.parsed.parsed_proto is not None
        check_received_proto_matches_expected(
            rec_msg.parsed.parsed_proto,
            "tests/resources/proto/bsi_flex_335_v1_0/registration_proto.json",
        )

    rec_ack_msg = await receive_msg_from_apex(
        send_stream, receive_fn, parse_fn, read_buffer, validator, id_generator
    )
    if msg_format is MessageFormat.PROTO:
        ack_msg_proto = rec_ack_msg.parsed.parsed_proto
        assert ack_msg_proto.registration_ack is not None
        assert ack_msg_proto.destination_id == send_msg.node_id
    else:
        ack_msg_xml = rec_ack_msg.parsed.parsed_xml
        assert ack_msg_xml.tag == "SensorRegistrationACK"

        # The ack should contain the auto-generated sensorID
        if auto_sensor_id is True:
            assert ack_msg_xml.find("sensorID").text == "1000001"
        else:
            assert ack_msg_xml.find("sensorID").text == send_msg.find("sensorID").text


class TestConversions:
    asm_stream: trio.SocketStream
    asm_proto_stream: trio.SocketStream
    hldmm_stream: trio.SocketStream
    id_generator: IdGenerator
    validator: Validator
    read_buffer: bytearray

    @pytest.fixture(autouse=True)
    async def before_each(self, apex):
        logger.info("opening streams")
        self.__class__.asm_stream = await trio.open_tcp_stream(_IP_ADDRESS, 5000)
        self.__class__.asm_proto_stream = await trio.open_tcp_stream(_IP_ADDRESS, 5010)
        self.__class__.hldmm_stream = await trio.open_tcp_stream(_IP_ADDRESS, 5001)
        logger.info("streams opened")

        self.__class__.id_generator = IdGenerator({})
        self.__class__.validator = Validator(ValidationOptions())
        logger.info("parsers created")

        self.__class__.read_buffer = bytearray()

        yield

        logger.info("Closing streams")
        await self.__class__.asm_stream.aclose()
        await self.__class__.hldmm_stream.aclose()
        logger.info("\nShutting Down Apex")

    async def test_xml_registration(self, before_each):
        await send_registration_message(
            self.asm_stream,
            self.hldmm_stream,
            MessageFormat.XML,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )

    async def test_xml_registration_auto_sensor_id(self, before_each):
        await send_registration_message(
            self.asm_stream,
            self.hldmm_stream,
            MessageFormat.XML,
            self.read_buffer,
            self.validator,
            self.id_generator,
            auto_sensor_id=True,
        )

    async def test_xml_status(self, before_each):
        await send_registration_message(
            self.asm_stream,
            self.hldmm_stream,
            MessageFormat.XML,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        send_msg_xml = await send_msg_to_apex(
            ET.parse("tests/resources/xml/status.xml").getroot(),
            self.asm_stream,
            MessageFormat.XML,
        )
        rec_msg = await receive_msg_from_apex(
            self.hldmm_stream,
            receive_until,
            parse_xml_partial,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        rec_msg_xml = rec_msg.parsed.parsed_xml

        check_received_proto_matches_expected(
            rec_msg.parsed.parsed_proto,
            "tests/resources/proto/bsi_flex_335_v1_0/status_proto.json",
        )
        send_msg_xml.remove(send_msg_xml.find("timestamp"))
        rec_msg_xml.remove(rec_msg_xml.find("timestamp"))
        assert ET.tostring(send_msg_xml) == ET.tostring(rec_msg_xml)

    async def test_xml_detection(self, before_each):
        await send_registration_message(
            self.asm_stream,
            self.hldmm_stream,
            MessageFormat.XML,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        send_msg_xml = await send_msg_to_apex(
            ET.parse("tests/resources/xml/detection.xml").getroot(),
            self.asm_stream,
            MessageFormat.XML,
        )
        rec_msg = await receive_msg_from_apex(
            self.hldmm_stream,
            receive_until,
            parse_xml_partial,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        rec_msg_xml = rec_msg.parsed.parsed_xml

        send_msg_xml.remove(send_msg_xml.find("timestamp"))
        rec_msg_xml.remove(rec_msg_xml.find("timestamp"))
        assert ET.tostring(send_msg_xml) == ET.tostring(rec_msg_xml)
        check_received_proto_matches_expected(
            rec_msg.parsed.parsed_proto,
            "tests/resources/proto/bsi_flex_335_v1_0/detection_proto.json",
        )

    async def test_proto_registration(self, before_each):
        await send_registration_message(
            self.asm_proto_stream,
            self.hldmm_stream,
            MessageFormat.PROTO,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )

    async def test_proto_status(self, before_each):
        await send_registration_message(
            self.asm_proto_stream,
            self.hldmm_stream,
            MessageFormat.PROTO,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        send_msg_proto = await send_msg_to_apex(
            json_to_proto(SapientMessage, get_status_message_template("1", ulid.new().str)),
            self.asm_proto_stream,
            MessageFormat.PROTO,
        )
        rec_msg = await receive_msg_from_apex(
            self.hldmm_stream,
            receive_until,
            parse_xml_partial,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        rec_msg_xml = rec_msg.parsed.parsed_xml

        assert send_msg_proto.status_report is not None
        assert rec_msg_xml.tag == "StatusReport"
        assert send_msg_proto.node_id == "1"
        assert rec_msg_xml.find("sourceID").text == "1000001"
        check_received_xml_matches_expected(
            rec_msg_xml,
            "tests/resources/xml/proto_converted/status.xml",
        )

    async def test_proto_detection(self, before_each):
        await send_registration_message(
            self.asm_proto_stream,
            self.hldmm_stream,
            MessageFormat.PROTO,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        await send_msg_to_apex(
            json_to_proto(
                SapientMessage,
                get_detection_message_template("1", ulid.new().str, ulid.new().str),
            ),
            self.asm_proto_stream,
            MessageFormat.PROTO,
        )
        rec_msg = await receive_msg_from_apex(
            self.hldmm_stream,
            receive_until,
            parse_xml_partial,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        rec_msg_xml = rec_msg.parsed.parsed_xml

        assert rec_msg_xml.tag == "DetectionReport"
        assert rec_msg_xml.find("sourceID").text == "1000001"
        check_received_xml_matches_expected(
            rec_msg_xml,
            "tests/resources/xml/proto_converted/detection.xml",
        )

    async def test_proto_error(self, before_each):
        await send_registration_message(
            self.asm_proto_stream,
            self.hldmm_stream,
            MessageFormat.PROTO,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        await send_msg_to_apex(
            json_to_proto(SapientMessage, get_invalid_status_message_template("1", ulid.new().str)),
            self.asm_proto_stream,
            MessageFormat.PROTO,
        )
        rec_msg = await receive_msg_from_apex(
            self.asm_proto_stream,
            receive_size_prefixed,
            parse_proto_partial,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )

        assert rec_msg.error is not None
        assert rec_msg.error.severity is ErrorSeverity.SILENT
        assert rec_msg.error.description == "Unknown status info: SYSTEM_UNSPECIFIED"

    async def test_task_to_proto_asm(self, before_each):
        await send_registration_message(
            self.asm_proto_stream,
            self.hldmm_stream,
            MessageFormat.PROTO,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        task_xml = ET.parse("tests/resources/xml/task.xml").getroot()
        task_xml.find("timestamp").text = datetime_to_str(datetime.utcnow())
        await send_msg_to_apex(
            task_xml,
            self.hldmm_stream,
            MessageFormat.XML,
        )
        rec_msg = await receive_msg_from_apex(
            self.asm_proto_stream,
            receive_size_prefixed,
            parse_proto_partial,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )

        assert rec_msg.parsed.parsed_proto.destination_id == "1"
        rec_task = rec_msg.parsed.parsed_proto.task
        assert rec_task is not None
        try:
            ulid.parse(rec_task.task_id)
        except ValueError:
            logger.error(f"received task id {rec_task.task_id} is not a ULID")
            assert False
        check_received_proto_matches_expected(
            rec_msg.parsed.parsed_proto, "tests/resources/proto/bsi_flex_335_v1_0/task_proto.json"
        )

    async def test_task_to_xml_asm(self, before_each):
        await send_registration_message(
            self.asm_stream,
            self.hldmm_stream,
            MessageFormat.XML,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        await send_msg_to_apex(
            ET.parse("tests/resources/xml/task.xml").getroot(),
            self.hldmm_stream,
            MessageFormat.XML,
        )
        rec_msg = await receive_msg_from_apex(
            self.asm_stream,
            receive_until,
            parse_xml_partial,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        rec_task = rec_msg.parsed.parsed_xml

        check_received_xml_matches_expected(rec_task, "tests/resources/xml/task.xml")

    async def test_task_ack(self, before_each):
        await send_registration_message(
            self.asm_proto_stream,
            self.hldmm_stream,
            MessageFormat.PROTO,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        task_xml = ET.parse("tests/resources/xml/task.xml").getroot()
        task_xml.find("timestamp").text = datetime_to_str(datetime.utcnow())
        sent_task = await send_msg_to_apex(
            task_xml,
            self.hldmm_stream,
            MessageFormat.XML,
        )
        rec_task = await receive_msg_from_apex(
            self.asm_proto_stream,
            receive_size_prefixed,
            parse_proto_partial,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )

        assert rec_task.parsed.parsed_proto.task is not None
        task_id = rec_task.parsed.parsed_proto.task.task_id
        await send_msg_to_apex(
            json_to_proto(SapientMessage, get_task_ack_message_template("1", task_id)),
            self.asm_proto_stream,
            MessageFormat.PROTO,
        )
        rec_task_ack = await receive_msg_from_apex(
            self.hldmm_stream,
            receive_until,
            parse_xml_partial,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )

        assert rec_task_ack.parsed.parsed_xml.tag == "SensorTaskACK"
        assert rec_task_ack.parsed.parsed_xml.find("status").text == "Accepted"
        assert rec_task_ack.parsed.parsed_xml.find("taskID").text == sent_task.find("taskID").text

    def create_alert_xml(self, sensor_id):
        alert_xml = ET.parse("tests/resources/xml/alert.xml").getroot()
        alert_xml.find("timestamp").text = datetime_to_str(datetime.utcnow())
        alert_xml.find("sourceID").text = str(sensor_id)
        return alert_xml

    async def test_alert_from_xml(self, before_each):
        await send_registration_message(
            self.asm_proto_stream,
            self.hldmm_stream,
            MessageFormat.PROTO,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )
        await send_msg_to_apex(self.create_alert_xml(1000001), self.hldmm_stream, MessageFormat.XML)
        rec_msg = await receive_msg_from_apex(
            self.asm_proto_stream,
            receive_size_prefixed,
            parse_proto_partial,
            self.read_buffer,
            self.validator,
            self.id_generator,
        )

        assert rec_msg.parsed.parsed_proto.alert is not None
        check_received_proto_matches_expected(
            rec_msg.parsed.parsed_proto, "tests/resources/proto/bsi_flex_335_v1_0/alert_proto.json"
        )
