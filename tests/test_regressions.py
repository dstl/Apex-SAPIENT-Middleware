#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import json
import struct
import xml.etree.ElementTree as ET
from collections.abc import Callable
from textwrap import dedent
from typing import Sequence, Union

import trio
from google.protobuf.json_format import MessageToDict
from google.protobuf.json_format import Parse as MessageFromJson
from google.protobuf.message import Message
from pytest import fixture

from sapient_msg.latest.sapient_message_pb2 import SapientMessage


async def test_xml_asm_to_xml_dmm(
    add_dummy_node: Callable,
    xml_registration: str,
    xml_detection_report: str,
    xml_registration_ack: str,
    xml_sensor_status: str,
):
    dmm: trio.abc.Stream = add_dummy_node("Peer", format="XML", peername="XmlPeer")
    asm: trio.abc.Stream = add_dummy_node("Child", format="XML", peername="XmlChild")

    # REGISTRATION
    await asm.send_all(xml_registration.encode() + b"\0")
    assert_xml_are_equal(await asm.receive_some(), xml_registration_ack)
    assert_xml_are_equal(await dmm.receive_some(), xml_registration)

    # DETECTION
    await asm.send_all(xml_detection_report.encode() + b"\0")
    assert_xml_are_equal(await dmm.receive_some(), xml_detection_report)

    # HEARTBEAT
    await asm.send_all(xml_sensor_status.encode() + b"\0")
    assert_xml_are_equal(await dmm.receive_some(), xml_sensor_status)


async def test_xml_asm_to_proto_dmm(
    add_dummy_node: Callable,
    xml_registration: str,
    proto_registration: dict,
    xml_detection_report: str,
    proto_detection_report: dict,
    xml_registration_ack: str,
    xml_sensor_status: str,
    proto_sensor_status: dict,
):
    dmm: trio.abc.Stream = add_dummy_node("Peer", format="PROTO", peername="XmlPeer")
    asm: trio.abc.Stream = add_dummy_node("Child", format="XML", peername="XmlChild")

    # REGISTRATION
    await asm.send_all(xml_registration.encode() + b"\0")
    assert_xml_are_equal(await asm.receive_some(), xml_registration_ack)
    assert_dict_are_equal(to_dict(await dmm.receive_some()), to_dict(proto_registration))

    # DETECTION
    await asm.send_all(xml_detection_report.encode() + b"\0")
    assert_dict_are_equal(to_dict(await dmm.receive_some()), to_dict(proto_detection_report))

    # HEARTBEAT
    await asm.send_all(xml_sensor_status.encode() + b"\0")
    assert_dict_are_equal(to_dict(await dmm.receive_some()), to_dict(proto_sensor_status))


async def test_proto_asm_to_proto_dmm(
    add_dummy_node: Callable,
    proto_registration: dict,
    proto_detection_report: dict,
    proto_registration_ack: str,
    proto_sensor_status: dict,
):
    dmm: trio.abc.Stream = add_dummy_node("Peer", format="PROTO", peername="XmlPeer")
    asm: trio.abc.Stream = add_dummy_node("Child", format="PROTO", peername="XmlChild")

    # REGISTRATION
    await asm.send_all(serialize_dict(proto_registration))
    assert_dict_are_equal(to_dict(await asm.receive_some()), to_dict(proto_registration_ack))
    assert_dict_are_equal(to_dict(await dmm.receive_some()), to_dict(proto_registration))

    # DETECTION
    await asm.send_all(serialize_dict(proto_detection_report))
    assert_dict_are_equal(to_dict(await dmm.receive_some()), to_dict(proto_detection_report))

    # HEARTBEAT
    await asm.send_all(serialize_dict(proto_sensor_status))
    assert to_dict(await dmm.receive_some()) == to_dict(proto_sensor_status)


XML_TYPES = Union[bytes, bytearray, str, ET.Element]
PROTO_TYPES = Union[bytes, bytearray, str, Message, dict]


def serialize_dict(message: dict) -> bytes:
    sapient = SapientMessage()
    MessageFromJson(json.dumps(message), sapient)
    msg_bytes = sapient.SerializeToString()
    return struct.pack("<I", len(msg_bytes)) + msg_bytes


def to_dict(data: PROTO_TYPES, normalize: bool = True) -> dict:
    if isinstance(data, dict):
        return do_normalize(data) if normalize else data
    if isinstance(data, Message):
        return MessageToDict(data)
    if isinstance(data, (bytes, bytearray)):
        (size,) = struct.unpack("<I", data[:4])
        data = bytes(data[4 : 4 + size])
    elif isinstance(data, str):
        data = data.encode()
    message = SapientMessage()
    message.ParseFromString(data)
    return to_dict(MessageToDict(message), normalize=normalize)


def do_normalize(data: dict) -> dict:
    output = data.copy()
    for tag in ("timestamp", "nodeId", "taskId", "reportId", "objectId", "destinationId"):
        if tag in output:
            output[tag] = tag
    for key, inner in output.items():
        if isinstance(inner, dict):
            output[key] = do_normalize(inner)
    return output


def to_xml(data: XML_TYPES) -> ET.Element:
    if isinstance(data, ET.Element):
        return data
    if isinstance(data, (bytes, bytearray)):
        data = data.strip(b"\0").decode("utf8")
    assert isinstance(data, str)
    return ET.fromstring(data)


def assert_xml_are_equal(e1: XML_TYPES, e2: XML_TYPES, except_tags: Sequence[str] = ("timestamp",)):
    e1 = to_xml(e1)
    e2 = to_xml(e2)
    assert e1.tag == e2.tag
    if e1.tag not in except_tags:
        assert (e1.text or "").strip() == (e2.text or "").strip()
    assert (e1.tail or "").strip() == (e2.tail or "").strip()
    assert e1.attrib == e2.attrib
    assert len(e1) == len(e2)
    for c1, c2 in zip(e1, e2):
        assert_xml_are_equal(c1, c2)


def assert_dict_are_equal(test_dict: dict, expected_dict: dict, dump_files: bool = False):
    # Just an easier way to spot mis-matched dicts using file comparsion of the contents
    if test_dict != expected_dict:
        if dump_files:
            with open("test_dict.txt", "w") as test_file:
                json.dump(test_dict, test_file)

            with open("expected_dict.txt", "w") as exp_file:
                json.dump(expected_dict, exp_file)

        assert False


@fixture
def xml_registration() -> str:
    return dedent(
        """
        <?xml version="1.0" ?>
        <SensorRegistration>
            <timestamp>2024-02-09T16:17:27.521839Z</timestamp>
            <sensorID>1</sensorID>
            <sensorType>Silverfish : UGV</sensorType>
            <name>DUMMY_ASM</name>
            <capabilities Category="Wifi_interface" Type="NODE_TYPE_CYBER" Value="20" Units="dBm"/>
            <heartbeatDefinition>
                <heartbeatInterval units="seconds" value="5"/>
                <sensorLocationDefinition>
                    <locationType units="decimal degrees-metres"
                                  datum="WGS84" zone="30n" north="True">GPS</locationType>
                </sensorLocationDefinition>
            </heartbeatDefinition>
            <modeDefinition type="Permanent">
                <modeName>Default</modeName>
                <settleTime units="seconds" value="1"/>
                <scanType>Steerable</scanType>
                <detectionDefinition>
                    <locationType units="decimal degrees-metres"
                                  datum="WGS84" zone="30n" north="True">GPS</locationType>
                    <geometricError type="Standard Deviation" units="meters"
                                  variationType="Linear with Range">
                        <performanceValue type="eRmin" value="0.1"/>
                        <performanceValue type="eRmax" value="0.5"/>
                    </geometricError>
                    <detectionReport category="detection" type="confidence"
                                     units="probability" onChange="0"/>
                    <detectionClassDefinition>
                        <confidenceDefinition>Multiple Class</confidenceDefinition>
                        <classPerformance type="FAR" units="Per Period"
                                        unitValue="1" variationType="Linear with Range">
                            <performanceValue type="eRmin" value="0.1"/>
                            <performanceValue type="eRmax" value="0.5"/>
                        </classPerformance>
                        <classDefinition type="Human">
                            <confidence units="probability"/>
                        </classDefinition>
                        <classDefinition type="Vehicle">
                            <confidence units="probability"/>
                        </classDefinition>
                    </detectionClassDefinition>
                    <behaviourDefinition type="Walking">
                        <confidence units="probability"/>
                    </behaviourDefinition>
                </detectionDefinition>
                <taskDefinition>
                    <regionDefinition>
                        <regionType>Area of Interest</regionType>
                        <locationType units="decimal degrees-metres" datum="WGS84"
                                      zone="30n" north="True">GPS</locationType>
                    </regionDefinition>
                    <command name="Request" units="Registration, Reset, Heartbeat, Stop, Start"
                             completionTime="10" completionTimeUnits="seconds"/>
                    <command name="LookAt" units="RangeBearing" completionTime="10"
                             completionTimeUnits="seconds"/>
                    <command name="GoTo" units="Location" completionTime="0"
                             completionTimeUnits="seconds"/>
                    <command name="NetSurv" units="surveyTask" completionTime="30"
                             completionTimeUnits="seconds"/>
                </taskDefinition>
            </modeDefinition>
        </SensorRegistration>
        """
    ).strip()


@fixture
def xml_sensor_status() -> str:
    return dedent(
        """
        <?xml version="1.0" ?>
        <StatusReport>
            <timestamp>2024-02-09T16:17:27.538443Z</timestamp>
            <sourceID>1</sourceID>
            <reportID>1</reportID>
            <system>OK</system>
            <info>New</info>
            <sensorLocation>
                <location>
                    <X>50.78942393071742</X>
                    <Y>-1.11786027775316</Y>
                    <Z>0.0</Z>
                    <eX>0.0</eX>
                    <eY>0.0</eY>
                    <eZ>0.0</eZ>
                </location>
            </sensorLocation>
        </StatusReport>
        """
    ).strip()


@fixture
def xml_detection_report() -> str:
    return dedent(
        """
        <?xml version="1.0" ?>
        <DetectionReport>
            <timestamp>2024-02-09T16:17:41.577384Z</timestamp>
            <sourceID>1</sourceID>
            <reportID>4</reportID>
            <objectID>1</objectID>
            <taskID>0</taskID>
            <location>
                <X>50.78942393071742</X>
                <Y>-1.11786027775316</Y>
                <Z>0.0</Z>
            </location>
        </DetectionReport>
        """
    ).strip()


@fixture
def xml_registration_ack() -> str:
    return dedent(
        """
        <?xml version="1.0" ?>
        <SensorRegistrationACK>
            <sensorID>1</sensorID>
            <timestamp>2024-02-12T10:21:36.104985Z</timestamp>
        </SensorRegistrationACK>
        """
    ).strip()


@fixture
def proto_registration() -> dict:
    return {
        "timestamp": "2024-02-09T16:17:27.521839Z",
        "nodeId": "8cb1d098-74ba-4ddc-ab37-6bfbca14d582",
        "registration": {
            "nodeDefinition": [
                {"nodeType": "NODE_TYPE_OTHER", "nodeSubType": ["Silverfish : UGV"]}
            ],
            "icdVersion": "BSI Flex 335 v2.0",
            "name": "Silverfish : UGV",
            "shortName": "DUMMY_ASM",
            "capabilities": [
                {
                    "category": "Wifi_interface",
                    "type": "NODE_TYPE_CYBER",
                    "value": "20",
                    "units": "dBm",
                }
            ],
            "statusDefinition": {
                "statusInterval": {"units": "TIME_UNITS_SECONDS", "value": 5.0},
                "locationDefinition": {
                    "locationUnits": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                    "locationDatum": "LOCATION_DATUM_WGS84_E",
                    "zone": "30n",
                },
            },
            "modeDefinition": [
                {
                    "modeName": "Default",
                    "modeType": "MODE_TYPE_PERMANENT",
                    "settleTime": {"units": "TIME_UNITS_SECONDS", "value": 1.0},
                    "scanType": "SCAN_TYPE_STEERABLE",
                    "detectionDefinition": [
                        {
                            "locationType": {
                                "locationUnits": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                                "locationDatum": "LOCATION_DATUM_WGS84_E",
                                "zone": "30n",
                            },
                            "detectionReport": [
                                {
                                    "category": "DETECTION_REPORT_CATEGORY_DETECTION",
                                    "type": "confidence",
                                    "units": "probability",
                                    "onChange": False,
                                }
                            ],
                            "detectionClassDefinition": [
                                {
                                    "confidenceDefinition": "CONFIDENCE_DEFINITION_MULTI_CLASS",
                                    "classPerformance": [
                                        {
                                            "type": "FAR",
                                            "units": "Per Period",
                                            "unitValue": "1",
                                            "variationType": "Linear with Range",
                                        }
                                    ],
                                    "classDefinition": [
                                        {"type": "Human", "units": "probability"},
                                        {"type": "Vehicle", "units": "probability"},
                                    ],
                                }
                            ],
                            "behaviourDefinition": [{"type": "Walking", "units": "probability"}],
                            "geometricError": {
                                "type": "Standard Deviation",
                                "units": "meters",
                                "variationType": "Linear with Range",
                                "performanceValue": [
                                    {"type": "eRmin", "units": "eRmin", "unitValue": "0.1"},
                                    {"type": "eRmax", "units": "eRmax", "unitValue": "0.5"},
                                ],
                            },
                        }
                    ],
                    "task": {
                        "regionDefinition": {
                            "regionType": ["REGION_TYPE_AREA_OF_INTEREST"],
                            "regionArea": [
                                {
                                    "locationUnits": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                                    "locationDatum": "LOCATION_DATUM_WGS84_E",
                                    "zone": "30n",
                                }
                            ],
                        },
                        "command": [
                            {
                                "units": "Registration, Reset, Heartbeat, Stop, Start",
                                "completionTime": {
                                    "units": "TIME_UNITS_SECONDS",
                                    "value": 10.0,
                                },
                                "type": "COMMAND_TYPE_REQUEST",
                            },
                            {
                                "units": "RangeBearing",
                                "completionTime": {
                                    "units": "TIME_UNITS_SECONDS",
                                    "value": 10.0,
                                },
                                "type": "COMMAND_TYPE_LOOK_AT",
                            },
                            {
                                "units": "Location",
                                "completionTime": {"units": "TIME_UNITS_SECONDS", "value": 0.0},
                                "type": "COMMAND_TYPE_REQUEST",
                            },
                            {
                                "units": "surveyTask",
                                "completionTime": {
                                    "units": "TIME_UNITS_SECONDS",
                                    "value": 30.0,
                                },
                                "type": "COMMAND_TYPE_REQUEST",
                            },
                        ],
                    },
                }
            ],
            "configData": [{"manufacturer": "manufacturer", "model": "model"}],
        },
    }


@fixture
def proto_detection_report() -> dict:
    return {
        "timestamp": "2024-02-09T16:17:41.577384Z",
        "nodeId": "8cb1d098-74ba-4ddc-ab37-6bfbca14d582",
        "detectionReport": {
            "reportId": "01HPEKBXJSMRBM8E32STY8MRX5",
            "objectId": "01HPEKBXJSB6WY59ZZ2GH4QF76",
            "taskId": "01HPEKBXJSNYV36Q2FYWPRDMCJ",
            "location": {
                "x": 50.78942393071742,
                "y": -1.11786027775316,
                "z": 0.0,
                "coordinateSystem": "LOCATION_COORDINATE_SYSTEM_UNSPECIFIED",
                "datum": "LOCATION_DATUM_UNSPECIFIED",
            },
        },
    }


@fixture
def proto_sensor_status() -> dict:
    return {
        "timestamp": "2024-02-09T16:17:27.538443Z",
        "nodeId": "8cb1d098-74ba-4ddc-ab37-6bfbca14d582",
        "statusReport": {
            "reportId": "01HPEM0345M2F3PHMB1NXN1MHG",
            "system": "SYSTEM_OK",
            "info": "INFO_NEW",
            "nodeLocation": {
                "x": 50.78942393071742,
                "y": -1.11786027775316,
                "z": 0.0,
                "xError": 0.0,
                "yError": 0.0,
                "zError": 0.0,
                "coordinateSystem": "LOCATION_COORDINATE_SYSTEM_UNSPECIFIED",
                "datum": "LOCATION_DATUM_UNSPECIFIED",
            },
        },
    }


@fixture
def proto_registration_ack() -> dict:
    return {
        "timestamp": "2024-02-12T12:27:49.635631Z",
        "nodeId": "8cb1d098-74ba-4ddc-ab37-6bfbca14d582",
        "destinationId": "8cb1d098-74ba-4ddc-ab37-6bfbca14d582",
        "registrationAck": {"acceptance": True},
    }
