#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import logging
import xml.etree.ElementTree as ET
from datetime import datetime

from google.protobuf.json_format import MessageToJson

from sapient_apex_server.structures import (
    MessageRecord,
    NoisyError,
    ParsedRecord,
    ReceivedDataRecord,
    RegistrationRecord,
    SapientVersion,
    SilentError,
    StatusReportRecord,
)
from sapient_apex_server.time_util import str_to_datetime
from sapient_apex_server.translator.id_generator import IdGenerator
from sapient_apex_server.translator.xml_to_bsi_flex_v1 import ToProtoTranslator
from sapient_apex_server.validate_proto import Validator

logger = logging.getLogger(__name__)
xml_to_bsi_flex_v1 = ToProtoTranslator()


def _get_xml_children(root: ET.Element, allow_missing_sensor_id_in_registration: bool):
    """Gets relevant children elements from XML message."""
    missing = {"timestamp"}
    optional_missing = set()
    if allow_missing_sensor_id_in_registration and root.tag == "SensorRegistration":
        optional_missing.update({"sensorID"})
    else:
        missing.update({"sensorID"})
    if root.tag == "StatusReport":
        missing.update({"system", "info"})
    elif root.tag == "SensorRegistration":
        missing.update({"sensorType"})
    elif root.tag == "DetectionReport":
        optional_missing.update({"detectionConfidence"})

    children = {}
    for elem in root:
        elem_tag = elem.tag
        if elem_tag == "sourceID":
            elem_tag = "sensorID"  # Treat these two fields as equivalent
        if elem_tag in missing:
            children[elem_tag] = elem.text
            missing.remove(elem_tag)
        elif elem_tag in optional_missing:
            children[elem_tag] = elem.text
            optional_missing.remove(elem_tag)
        if not missing and not optional_missing:
            # We have all the information we need, return immediately.
            return children

    # If we get here then a child element must have been missing
    if not missing:
        # The only fields still missing were optional anyway
        return children
    if "sensorID" in missing:
        # Clarify error message to show that either would do
        missing.remove("sensorID")
        missing.add("sensorID/sourceID")
    raise ValueError(f"Missing element(s) [{','.join(sorted(missing))}] in {root.tag}")


def parse_xml(
    msg_data: ReceivedDataRecord,
    validator: Validator,
    generator: IdGenerator,
    enable_sensor_id_auto: bool,
) -> MessageRecord:
    """Reads one message, decodes it to XML, and handles common errors."""
    record = MessageRecord(
        received=msg_data,
        data_decoded_xml="",
        data_binary_proto=None,
        decoded_timestamp=datetime.utcnow(),
        sapient_version=SapientVersion.VERSION6,
        error=None,
    )
    # Attempt to decode the bytes; data_decoded is always filled in.
    assert len(msg_data.data_bytes) > 0 and msg_data.data_bytes[-1] == 0
    try:
        data_decoded = msg_data.data_bytes[:-1].decode("utf8")
        error = None
    except UnicodeDecodeError as e:
        data_decoded = repr(msg_data.data_bytes)[2:-5]  # trim "b'foo\\x00'" to "foo"
        error = NoisyError(str(e))

    if error is not None:
        return record

    record.data_decoded_xml = data_decoded
    record.error = error

    # Information extracted from the contents of the message
    try:
        # Parse the XML
        root = ET.fromstring(data_decoded.strip())
        # To reduce the chance of an infinite inter-process loop, silence errors about errors
        # Must be done before getting children elements because Error does not include sensorID
        if root.tag == "Error":
            record.error = SilentError('Received "Error" message')
            return record

        # Get relevant information from parsed XML
        children = _get_xml_children(root, enable_sensor_id_auto)

        # Assign sensor ID if necessary, this used to happen when
        # while handling the registration message, but now we need to
        # do this pre-emptively before the xml->bsi upgrade &
        # before the uuid <->sensorID mappings.
        if (
            root.tag == "SensorRegistration"
            and "sensorID" not in children
            and enable_sensor_id_auto
        ):
            internal_sensor_id = generator.get_next_id()
            insert_sensor_id(root, internal_sensor_id)
            children["sensorID"] = str(internal_sensor_id)

        # Record results in ReceivedDataRecord
        record.parsed = ParsedRecord(
            message_type=None,
            node_id=None,
            destination_node_id=None,
            internal_sensor_id=int(children["sensorID"]) if "sensorID" in children else None,
            message_timestamp=str_to_datetime(children["timestamp"]),
            detection_confidence=(
                float(children["detectionConfidence"])
                if "detectionConfidence" in children
                else None
            ),
            parsed_xml=root,
            parsed_proto=None,
        )
        message_and_errors = xml_to_bsi_flex_v1.translate(root, generator)
        record.parsed.parsed_proto = message_and_errors[0]
        if len(message_and_errors[1]) > 0:
            logger.error(
                "Errors encountered while parsing XML to proto: ["
                + "\n".join(message_and_errors[1])
                + "]"
            )
        record.parsed.message_type = record.parsed.parsed_proto.WhichOneof("content")

        # Be more forgiving for XML V6 ASMs which have been upgraded to BSI V1 above
        # As some ASM have incomplete/incorrect implementations and validation errors may
        # flagged when its not possible to fix the (legacy) ASM easily.
        # Ideally the validation should be against the V6 XSD & not BSI V1
        errors = []
        validator.validate_sapient_message(
            message=record.parsed.parsed_proto,
            received_time=record.received.timestamp,
            errors=errors,
            validate_contents=False,
        )
        if errors:
            error_str = "\n".join(e.full_str() for e in errors)
            record.error = NoisyError(f"Validation {len(errors)} errors:\n{error_str}")
            return record

        if root.tag == "SensorRegistration":
            record.registration = RegistrationRecord(node_name=children["sensorType"])
        elif root.tag == "StatusReport":
            info = children["info"].lower()
            if info == "new":
                is_unchanged = False
            elif info == "unchanged":
                is_unchanged = True
            else:
                raise ValueError('Field "info" of StatusReport must be "New" or "Unchanged"')
            record.status_report = StatusReportRecord(
                system=children["system"],
                is_unchanged=is_unchanged,
            )
        if record.parsed.parsed_proto is not None:
            record.data_binary_proto = record.parsed.parsed_proto.SerializeToString()
            record.data_json = MessageToJson(
                record.parsed.parsed_proto,
                preserving_proto_field_name=True,
                indent=2,
            )
            record.data_json = record.data_json[0]
            record.parsed.node_id = record.parsed.parsed_proto.node_id
            record.parsed.destination_node_id = record.parsed.parsed_proto.destination_id or None
    except Exception as e:
        record.error = NoisyError(str(e))
    return record


def insert_sensor_id(root: ET.Element, sensor_id: int):
    """Inserts sensor ID into a parsed XML message.

    Puts the new element after the timestamp (which is guaranteed to exist by the time this routine
    is called) and carefully (/frivolously) matches surrounding spacing.
    """
    prev_tail = root.text
    for i, elem in enumerate(root):
        if elem.tag == "timestamp":
            sensor_id_elem = ET.Element("sensorID")
            sensor_id_elem.text = str(sensor_id)
            root.insert(i + 1, sensor_id_elem)
            sensor_id_comment = ET.Comment("Added by Apex")
            root.insert(i + 2, sensor_id_comment)
            # Fix up spacing / indentation
            sensor_id_comment.tail = elem.tail
            elem.tail = prev_tail
            return
        prev_tail = elem.tail
    raise RuntimeError("timestamp element not found")
