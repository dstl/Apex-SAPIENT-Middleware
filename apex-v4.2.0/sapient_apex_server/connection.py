#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Contains logic for handling messages sent to connections.

The classes in this file contain the "business" logic for connections:

* Whether messages are erroneous (although some errors will already have been caught in parsing,
  which happens before messages are passed to these classes).

* Which other connections, if any, to forward messages on to.

They do not handle the mechanics of reading messages from a socket, using other threads to do the
parsing or write to the SQLite database.
"""
import logging
import string
import textwrap
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import chain
from typing import Dict, List, Optional

from sapient_apex_server.message_io import WriterType
from sapient_apex_server.parse_xml import insert_sensor_id
from sapient_apex_server.structures import (
    ErrorRecord,
    ErrorSeverity,
    FatalError,
    MessageFormat,
    MessageRecord,
    NoisyError,
    SapientVersion,
    SilentError,
)
from sapient_apex_server.time_util import (
    datetime_to_int,
    datetime_to_pb,
    datetime_to_str,
)
from sapient_apex_server.translator.id_generator import IdGenerator
from sapient_msg.latest.error_pb2 import Error
from sapient_msg.latest.registration_ack_pb2 import RegistrationAck
from sapient_msg.latest.sapient_message_pb2 import SapientMessage

logger = logging.getLogger("apex")


# foo.translate(trans_table_no_whitespace) will remove all whitespace from foo
translation_table_no_whitespace = str.maketrans("", "", string.whitespace)


@dataclass
class SensorInfo:
    """Information about an ASM needed by other connections."""

    writer: WriterType
    registration: MessageRecord
    dmm_msg_offset: timedelta
    message_format: MessageFormat
    recent_status_new: Optional[MessageRecord] = None
    recent_status_unchanged: Optional[MessageRecord] = None


@dataclass
class ParentWriter:
    writer: WriterType
    message_format: MessageFormat


@dataclass
class SharedData:
    """Data shared between all connections."""

    config: dict
    middleware_node_id: str
    registered_sensors: Dict[str, SensorInfo]
    next_auto_sensor_id: int
    dmm_msg_format: MessageFormat
    dmm_writers: List[WriterType]
    parent_high_level_writers: List[ParentWriter]
    parent_all_writers: List[ParentWriter]
    parent_message_format: MessageFormat

    def send_to_parent(
        self,
        msg: MessageRecord,
        high_level: bool,
        except_writer: Optional[WriterType] = None,
    ):
        if msg.error is not None:
            return
        writers = self.parent_all_writers
        if high_level:
            writers = chain(writers, self.parent_high_level_writers)
        for writer in writers:
            if writer != except_writer:
                writer.writer(msg, msg.sapient_version)
                msg.forwarded_count += 1

    def send_registration_ack(
        self,
        writer: WriterType,
        destination_id: str,
        message_format: MessageFormat,
        generator: IdGenerator,
    ):
        if message_format is MessageFormat.PROTO:
            register_ack = SapientMessage(
                timestamp=datetime_to_pb(datetime.utcnow()),
                node_id=self.middleware_node_id,
                destination_id=destination_id,
                registration_ack=RegistrationAck(acceptance=True),
            )
            writer(register_ack, SapientVersion.LATEST)
        else:
            message = ET.Element("SensorRegistrationACK")

            sensor_id_elem = ET.SubElement(message, "sensorID")
            sensor_id_elem.text = str(generator.node_id_map[destination_id].xml_id)
            timestamp = ET.SubElement(message, "timestamp")
            timestamp.text = datetime_to_str(datetime.utcnow())
            ET.indent(message)
            writer(message, SapientVersion.VERSION6)


def _send_error_reply_if_necessary(
    writer: WriterType,
    conn_desc: str,
    msg: MessageRecord,
    message_format: MessageFormat,
    node_id: str,
    destination_id: Optional[str],
):
    if msg.error is None:
        return
    logger.debug(
        "Connection {} ({}) {} error in message:\n{}".format(
            msg.received.connection_id,
            conn_desc,
            msg.error.severity.name.title(),
            textwrap.indent(msg.error.description, "    "),
        )
    )

    if msg.error.severity == ErrorSeverity.NOISY:
        if message_format == MessageFormat.PROTO:
            err_msg = SapientMessage(
                timestamp=datetime_to_pb(datetime.utcnow()),
                node_id=node_id,
                destination_id=None,
                error=Error(
                    packet=bytes(msg.received.data_bytes),
                    error_message=[msg.error.description],
                ),
            )
            if destination_id is not None:
                err_msg.destination_id = destination_id
            writer(err_msg, SapientVersion.LATEST)
        else:
            message = ET.Element("Error")
            timestamp = ET.SubElement(message, "timestamp")
            timestamp.text = str(datetime_to_int(datetime.utcnow()))
            packet = ET.SubElement(message, "packet")
            packet.text = msg.data_decoded_xml
            errorMessage = ET.SubElement(message, "errorMessage")
            errorMessage.text = msg.error.description
            writer(message, SapientVersion.VERSION6)


def _apply_timestamp_offset(
    config: dict, msg: MessageRecord, offset: timedelta, message_format: MessageFormat
):
    if not config["enableTimeSyncAdjustment"]:
        msg.updated_data_bytes = (
            msg.received.data_bytes
            if message_format is MessageFormat.XML
            else msg.data_binary_proto
        )
        return
    msg.parsed.message_timestamp += offset
    if message_format is MessageFormat.PROTO:
        msg.parsed.parsed_proto.timestamp.FromDatetime(msg.parsed.message_timestamp)
        msg.updated_data_bytes = msg.parsed.parsed_proto.SerializeToString()
    else:
        time_elem = msg.parsed.parsed_xml.find("timestamp")
        time_elem.text = datetime_to_str(msg.parsed.message_timestamp)


class ChildConnection:
    """Connection from an ASM.

    Messages are all forwarded to the DMM (if no error). Node ID from registration is recorded,
    and then messages from the DMM to that Node ID is forwarded back to this connection.
    """

    def __init__(
        self,
        shared_data: SharedData,
        writer: WriterType,
        connection_config: dict,
        message_format: MessageFormat,
    ):
        self.shared_data = shared_data
        self.writer = writer

        self.registration = None
        self.node_id = None
        self.sensor_id = None
        self.message_format = message_format
        self.last_status_report_system = None  # For checking "unchanged" status reports

        self.time_offset = None  # If time sync adjustment enabled, this is added to all timestamps

        # Config for detection confidence filtering
        detection_filter_config = self.shared_data.config.get("detectionConfidenceFiltering", {})
        self.detection_confidence_threshold = None
        if detection_filter_config.get("enable"):
            self.detection_confidence_threshold = detection_filter_config.get("threshold", 0)
            if self.detection_confidence_threshold <= 0 or self.detection_confidence_threshold >= 1:
                logger.warning(
                    "Got invalid detection confidence threshold: "
                    + str(self.detection_confidence_threshold)
                )
            if detection_filter_config.get("storeInDatabase"):
                self.detection_filter_error_severity = ErrorSeverity.SILENT
            else:
                self.detection_filter_error_severity = ErrorSeverity.UNSTORED

    def _filter_detection(self, msg: MessageRecord):
        # Check whether it makes sense to apply filter
        if self.detection_confidence_threshold is None:
            return
        if msg.parsed is None or msg.parsed.detection_confidence is None:
            return

        # Check whether filter is passed
        if msg.parsed.detection_confidence >= self.detection_confidence_threshold:
            return

        # Failed filter
        msg.error = ErrorRecord(
            self.detection_filter_error_severity,
            f"Detection confidence {msg.parsed.detection_confidence} "
            + f"less than filter threshold {self.detection_confidence_threshold}",
        )

    def _handle_registration(self, reg_msg: MessageRecord, generator: IdGenerator):
        # Check for errors
        if reg_msg.error is not None:
            return
        if reg_msg.registration is None:
            reg_msg.error = SilentError("Registration message expected")
            return
        if reg_msg.parsed.node_id is None:
            reg_msg.error = FatalError("Child sent registration message with no ID")
            return

        # Adjustment for trial with no time sync: fix up time in message before forwarding
        time_offset = reg_msg.received.timestamp - reg_msg.parsed.message_timestamp
        self.time_offset = time_offset - timedelta(milliseconds=100)  # Include "message delay"
        _apply_timestamp_offset(
            self.shared_data.config,
            reg_msg,
            self.time_offset,
            self.shared_data.dmm_msg_format,
        )

        # Assign sensor ID if necessary, this should be now be usually set during the parsing stage
        if reg_msg.parsed.internal_sensor_id is None and self.shared_data.config.get(
            "enableMessageConversion", True
        ):
            # This can only happen from an XML connection, so we can generate new id without
            # creating a ULID
            reg_msg.parsed.internal_sensor_id = generator.get_next_id()
            insert_sensor_id(reg_msg.parsed.parsed_xml, reg_msg.parsed.internal_sensor_id)

        # Successfully received registration message.
        self.node_id = reg_msg.parsed.node_id
        self.sensor_id = reg_msg.parsed.internal_sensor_id or None
        self.registration = reg_msg
        # Use -time_offset so that DMM messages are shifted back to ASM's view of time
        self.shared_data.registered_sensors[self.node_id] = SensorInfo(
            self.writer, reg_msg, -time_offset, self.message_format
        )

        for dmm_writer in self.shared_data.dmm_writers:
            dmm_writer(reg_msg, reg_msg.sapient_version)
        reg_msg.forwarded_count = len(self.shared_data.dmm_writers)

        if self.shared_data.config.get("sendRegistrationAck", True):
            self.shared_data.send_registration_ack(
                self.writer, self.node_id, self.message_format, generator
            )

    def _handle_other(self, msg: MessageRecord, generator: IdGenerator):
        # Check for errors
        if msg.error is not None:
            return
        if msg.parsed.node_id != self.node_id:
            msg.error = NoisyError(
                f"Expected node ID {self.node_id}, got node ID {msg.parsed.node_id}"
            )
            return
        node_info = self.shared_data.registered_sensors.get(self.node_id)
        if node_info is None or node_info.writer is not self.writer:
            msg.error = SilentError(f"Node ID {self.node_id} hijacked by another connection")
            return

        # Adjustment for trial with no time sync: fix up time in message before forwarding
        _apply_timestamp_offset(
            self.shared_data.config,
            msg,
            self.time_offset,
            self.shared_data.dmm_msg_format,
        )

        # Handle registration messages
        if msg.registration is not None:
            # We allow an ASM to re-register but it must have the same node ID as before and that
            # node ID must not have been hijacked (which are both checked for above).
            logger.info(
                "Connection for node ID {} sent duplicate registration ({} -> {})".format(
                    self.registration.parsed.node_id,
                    self.registration.registration.node_name,
                    msg.registration.node_name,
                )
            )
            self.registration = msg
            self.last_status_report_system = None
            node_info.registration = msg
            node_info.recent_status_new = None
            node_info.recent_status_unchanged = None

            if self.shared_data.config.get("sendRegistrationAck", True):
                self.shared_data.send_registration_ack(
                    self.writer, self.node_id, self.message_format, generator
                )

        # Handle status reports
        if msg.status_report is not None:
            if msg.status_report.is_unchanged:
                if self.last_status_report_system is None:
                    msg.error = NoisyError('Status report "Unchanged" received before "New"')
                    return
                elif self.last_status_report_system != msg.status_report.system:
                    msg.error = NoisyError(
                        f'Status report "Unchanged" has system "{msg.status_report.system}"'
                        + f' different from last "New" system "{self.last_status_report_system}"'
                    )
                    return
            else:
                self.last_status_report_system = msg.status_report.system
            # Record to allow forwarding to DMMs that connect later.
            if msg.status_report.is_unchanged:
                node_info.recent_status_unchanged = msg
            else:
                node_info.recent_status_new = msg
                node_info.recent_status_unchanged = None

        # Handle detection reports
        self._filter_detection(msg)
        if msg.error is not None:
            return  # Failed filter

        # Forward the message to any connected DMMs.
        logger.debug(
            f"Writing {msg.parsed.message_type} to {len(self.shared_data.dmm_writers)} DMMs"
        )
        for dmm_writer in self.shared_data.dmm_writers:
            dmm_writer(msg, msg.sapient_version)
        msg.forwarded_count = len(self.shared_data.dmm_writers)

    def handle_message(self, msg: MessageRecord, generator: IdGenerator):
        try:
            if self.registration is None:
                self._handle_registration(msg, generator)
            else:
                self._handle_other(msg, generator)
            self.shared_data.send_to_parent(msg, high_level=False)
        except Exception as e:
            msg.error = FatalError(f"{type(e).__name__}: {e}")
        if self.registration is not None:
            connection_description = "Child {}: {}".format(
                self.registration.parsed.node_id,
                self.registration.registration.node_name,
            )
        else:
            connection_description = "Child: ?"
        _send_error_reply_if_necessary(
            self.writer,
            connection_description,
            msg,
            self.message_format,
            self.shared_data.middleware_node_id,
            self.node_id,
        )

    def handle_closed(self):
        is_registered = (
            self.node_id is not None
            and self.node_id in self.shared_data.registered_sensors
            and self.shared_data.registered_sensors[self.node_id].writer is self.writer
        )
        if is_registered:
            del self.shared_data.registered_sensors[self.node_id]


class PeerConnection:
    """Connection from an DMM.

    All messages from ASMs are forwarded to this connection. Messages from this connection with a
    node ID (not set to 0) are forwarded to appropriate ASM.
    """

    def __init__(
        self,
        shared_data: SharedData,
        writer: WriterType,
        connection_config: dict,
        message_format: MessageFormat,
    ):
        self.shared_data = shared_data
        self.writer = writer

        self.dmm_id = None
        self.message_format = message_format

        self.shared_data.dmm_writers.append(writer)

        # Let DMM know about current status of nodes that connected before it.
        for node_info in self.shared_data.registered_sensors.values():
            assert isinstance(node_info, SensorInfo)
            self.writer(node_info.registration, node_info.registration.sapient_version)
            if node_info.recent_status_new is not None:
                self.writer(
                    node_info.recent_status_new, node_info.recent_status_new.sapient_version
                )
            if node_info.recent_status_unchanged is not None:
                self.writer(
                    node_info.recent_status_unchanged,
                    node_info.recent_status_unchanged.sapient_version,
                )

    def _handle_registration(self, msg: MessageRecord, generator: IdGenerator):
        if not self.shared_data.config.get("allowPeerRegistration"):
            msg.error = NoisyError("Peer should not send registration")
            return

        if msg.parsed.node_id is None:
            msg.error = FatalError("Peer sent registration message with no ID")
            return

        if self.dmm_id is not None and msg.parsed.node_id != self.dmm_id:
            msg.error = FatalError(
                "Peer sent registration with inconsistent ID "
                + f"({self.dmm_id} -> {msg.parsed.node_id}"
            )
            return

        # If we got past all the above checks then we record the source ID
        self.dmm_id = msg.parsed.node_id

        # For the DMM send the Ack irrespective of middleware's sendRegistrationAck setting.
        self.shared_data.send_registration_ack(
            self.writer, self.dmm_id, self.message_format, generator
        )

    def _handle_message_inner(self, msg: MessageRecord, generator: IdGenerator):
        # Check for any errors that are specific to DMM messages.
        if msg.error is not None:
            return

        # Handle registration message
        if msg.registration is not None:
            self._handle_registration(msg, generator)
            if msg.error is not None:
                return

        # Verify source ID (if this DMM has registered)
        if self.dmm_id is not None and msg.parsed.node_id != self.dmm_id:
            msg.error = NoisyError(
                f"Expected node ID {self.dmm_id}, got node ID {msg.parsed.node_id}"
            )
            return

        # Forward to destination ASM (if any)
        if msg.parsed.destination_node_id is not None:
            if msg.parsed.destination_node_id not in self.shared_data.registered_sensors:
                msg.error = NoisyError(f"Unknown node ID {msg.parsed.destination_node_id}")
                return
            node_connection = self.shared_data.registered_sensors[msg.parsed.destination_node_id]
            _apply_timestamp_offset(
                self.shared_data.config,
                msg,
                node_connection.dmm_msg_offset,
                node_connection.message_format,
            )

            node_connection.writer(msg, msg.sapient_version)
            msg.forwarded_count = 1

        # Forward to any parent connections
        is_high_level_message = msg.parsed.destination_node_id is None
        self.shared_data.send_to_parent(msg, high_level=is_high_level_message)

    def handle_message(self, msg: MessageRecord, generator: IdGenerator):
        try:
            self._handle_message_inner(msg, generator)
        except Exception as e:
            msg.error = FatalError(f"{type(e).__name__}: {e}")
        _send_error_reply_if_necessary(
            self.writer,
            "Peer",
            msg,
            self.message_format,
            self.shared_data.middleware_node_id,
            self.dmm_id,
        )

    def handle_closed(self):
        self.shared_data.dmm_writers.remove(self.writer)


class ParentConnection:
    """Connection from an application listening for high-level SAPIENT messages.

    Fused tracks and alerts from the DMM are forwarded to this connection. No incoming messages
    are expected from this connection. The forward_all flag enables forwarding of all messages to
    connection, not just high-level messages
    """

    def __init__(
        self,
        shared_data: SharedData,
        writer: WriterType,
        connection_config: dict,
        message_format: MessageFormat,
    ):
        self.shared_data = shared_data
        self.writer = writer
        self.message_format = message_format
        self.forward_all = connection_config.get("forwardAll", False)
        self.parent_writer = ParentWriter(writer, self.message_format)
        if self.forward_all:
            self.shared_data.parent_all_writers.append(self.parent_writer)
            # Let "forward-all" enabled parents know about current status of nodes that
            # connected before it
            for node_info in self.shared_data.registered_sensors.values():
                assert isinstance(node_info, SensorInfo)
                self.writer(node_info.registration, node_info.registration.sapient_version)
                if node_info.recent_status_new is not None:
                    self.writer(
                        node_info.recent_status_new, node_info.recent_status_new.sapient_version
                    )
                if node_info.recent_status_unchanged is not None:
                    self.writer(
                        node_info.recent_status_unchanged,
                        node_info.recent_status_unchanged.sapient_version,
                    )
        else:
            self.shared_data.parent_high_level_writers.append(self.parent_writer)

    def handle_message(self, msg: MessageRecord, generator: IdGenerator):
        msg.updated_data_bytes = msg.received.data_bytes
        if msg.error is None:
            for writer in self.shared_data.dmm_writers:
                writer(msg, msg.sapient_version)
            msg.forwarded_count = len(self.shared_data.dmm_writers)

            self.shared_data.send_to_parent(msg, high_level=False, except_writer=self.writer)

        _send_error_reply_if_necessary(
            self.writer,
            "Parent",
            msg,
            self.message_format,
            self.shared_data.middleware_node_id,
            None,
        )

    def handle_closed(self):
        if self.forward_all:
            self.shared_data.parent_all_writers.remove(self.parent_writer)
        else:
            self.shared_data.parent_high_level_writers.remove(self.parent_writer)


class RecorderConnection:
    """All incoming messages from this connection are ignored.

    The messages are still stored in the SQLite database, so this type of connection is useful for
    messages that should be recorded but not handled in any other way.
    """

    def __init__(
        self,
        shared_data: SharedData,
        writer: WriterType,
        connection_config: dict,
        message_format: MessageFormat,
    ):
        self.shared_data = shared_data
        self.message_format = message_format

    def handle_message(self, msg: MessageRecord, generator: IdGenerator):
        msg.updated_data_bytes = msg.received.data_bytes
        self.shared_data.send_to_parent(msg, high_level=False)

    def handle_closed(self):
        pass


_CONNECTION_TYPES = {
    "Peer": PeerConnection,  # Connections at the same level, example: Fusion Nodes / DMMs
    "Child": ChildConnection,  # Connections at a lower level, example: Edge Nodes / ASMs
    "Parent": ParentConnection,  # Connection at a higher level, example: Another Apex
    "Recorder": RecorderConnection,
}


class ConnectionCreator:
    def __init__(self, config: dict):
        reg_id = config.get("autoAssignSensorIDInRegistration", {}).get("startingID", 1000001)
        dmm_message_format = MessageFormat.PROTO
        parent_message_format = MessageFormat.PROTO
        if config.get("enableMessageConversion", True):
            for connection in config.get("connections", []):
                if connection.get("type", "") == "Peer":
                    dmm_message_format = MessageFormat[connection.get("format", "XML")]
            for connection in config.get("connections", []):
                if connection.get("type", "") == "Parent":
                    parent_message_format = MessageFormat[connection.get("format", "PROTO")]

        self.shared_data = SharedData(
            config,
            str(config.get("middlewareId", uuid.uuid4())),
            {},
            reg_id,
            dmm_message_format,
            [],
            [],
            [],
            parent_message_format,
        )
        self.previous_connection_id = 0

    def create(self, connection_config: dict, writer: WriterType):
        self.previous_connection_id += 1
        message_format = connection_config["format"]
        connection_type = _CONNECTION_TYPES[connection_config["type"]]
        new_connection = connection_type(
            self.shared_data, writer, connection_config, message_format
        )
        return self.previous_connection_id, new_connection
