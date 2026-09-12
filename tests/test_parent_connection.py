#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from datetime import datetime, timedelta
from unittest.mock import MagicMock

from sapient_apex_server.connection import ParentConnection, SensorInfo, SharedData
from sapient_msg.latest.sapient_message_pb2 import SapientMessage
from sapient_apex_server.structures import (
    MessageFormat,
    MessageRecord,
    ParsedRecord,
    ReceivedDataRecord,
)


def _message(destination_id=None):
    timestamp = datetime.utcnow()
    parsed_proto = SapientMessage(node_id="parent-node")
    parsed_proto.timestamp.FromDatetime(timestamp)
    if destination_id is not None:
        parsed_proto.destination_id = destination_id
    return MessageRecord(
        received=ReceivedDataRecord(
            connection_id=1,
            message_id=1,
            timestamp=timestamp,
            data_bytes=parsed_proto.SerializeToString(),
        ),
        data_decoded_xml="",
        data_binary_proto=parsed_proto.SerializeToString(),
        decoded_timestamp=timestamp,
        parsed=ParsedRecord(
            message_type="registration_ack",
            node_id="parent-node",
            internal_sensor_id=None,
            destination_node_id=destination_id,
            message_timestamp=timestamp,
            detection_confidence=None,
            parsed_proto=parsed_proto,
            parsed_xml=None,
        ),
    )


def test_parent_routes_targeted_message_to_child_without_reflection():
    child_writer = MagicMock()
    dmm_writer = MagicMock()
    source_parent_writer = MagicMock()
    other_parent_writer = MagicMock()

    shared_data = SharedData(
        config={"enableTimeSyncAdjustment": False},
        middleware_node_id="middleware",
        registered_sensors={},
        next_auto_sensor_id=1,
        dmm_msg_format=MessageFormat.PROTO,
        dmm_writers=[dmm_writer],
        parent_high_level_writers=[],
        parent_all_writers=[],
        parent_message_format=MessageFormat.PROTO,
    )

    source_parent = ParentConnection(
        shared_data,
        source_parent_writer,
        {"forwardAll": True},
        MessageFormat.PROTO,
    )
    ParentConnection(
        shared_data,
        other_parent_writer,
        {"forwardAll": True},
        MessageFormat.PROTO,
    )

    shared_data.registered_sensors["child-node"] = SensorInfo(
        writer=child_writer,
        registration=_message(),
        dmm_msg_offset=timedelta(),
        message_format=MessageFormat.PROTO,
    )

    msg = _message("child-node")
    source_parent.handle_message(msg, MagicMock())

    child_writer.assert_called_once()
    child_msg, child_version = child_writer.call_args.args
    assert child_msg is not msg
    assert child_msg.parsed.message_timestamp == msg.parsed.message_timestamp
    assert child_version == msg.sapient_version
    dmm_writer.assert_called_once_with(msg, msg.sapient_version)
    source_parent_writer.assert_not_called()
    other_parent_writer.assert_called_once_with(msg, msg.sapient_version)
    assert msg.forwarded_count == 3


def test_parent_applies_child_timestamp_offset_without_mutating_other_routes():
    child_writer = MagicMock()
    dmm_writer = MagicMock()
    source_parent_writer = MagicMock()
    other_parent_writer = MagicMock()
    offset = timedelta(seconds=17)

    shared_data = SharedData(
        config={"enableTimeSyncAdjustment": True},
        middleware_node_id="middleware",
        registered_sensors={},
        next_auto_sensor_id=1,
        dmm_msg_format=MessageFormat.PROTO,
        dmm_writers=[dmm_writer],
        parent_high_level_writers=[],
        parent_all_writers=[],
        parent_message_format=MessageFormat.PROTO,
    )

    source_parent = ParentConnection(
        shared_data, source_parent_writer, {"forwardAll": True}, MessageFormat.PROTO
    )
    ParentConnection(
        shared_data, other_parent_writer, {"forwardAll": True}, MessageFormat.PROTO
    )
    shared_data.registered_sensors["child-node"] = SensorInfo(
        writer=child_writer,
        registration=_message(),
        dmm_msg_offset=offset,
        message_format=MessageFormat.PROTO,
    )

    msg = _message("child-node")
    original_timestamp = msg.parsed.message_timestamp
    source_parent.handle_message(msg, MagicMock())

    child_msg = child_writer.call_args.args[0]
    assert child_msg is not msg
    assert child_msg.parsed.message_timestamp == original_timestamp + offset
    assert child_msg.parsed.parsed_proto.timestamp.ToDatetime() == original_timestamp + offset
    assert msg.parsed.message_timestamp == original_timestamp
    assert msg.parsed.parsed_proto.timestamp.ToDatetime() == original_timestamp
    dmm_writer.assert_called_once_with(msg, msg.sapient_version)
    other_parent_writer.assert_called_once_with(msg, msg.sapient_version)
    source_parent_writer.assert_not_called()
    assert msg.forwarded_count == 3
