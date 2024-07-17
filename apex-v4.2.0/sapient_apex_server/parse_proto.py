#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import xml.etree.ElementTree as ET
from datetime import datetime

from google.protobuf.json_format import MessageToJson
from google.protobuf.message import DecodeError

from sapient_apex_server.message_io import to_version
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
from sapient_apex_server.translator.bsi_flex_v1_to_xml import (
    translate as bsi_flex_v1_to_xml,
)
from sapient_apex_server.translator.id_generator import IdGenerator
from sapient_apex_server.validate_proto import Validator
from sapient_msg.latest.status_report_pb2 import StatusReport
from sapient_apex_server.translator.proto_to_proto_translator import (
    empty_sapient_message,
)
import logging

logger = logging.getLogger(__name__)


def parse_proto(
    msg_data: ReceivedDataRecord,
    validator: Validator,
    generator: IdGenerator,
    enable_message_conversion: bool,
    sapient_version: SapientVersion = SapientVersion.LATEST,  # Connection's SapientVersion
) -> MessageRecord:
    result = MessageRecord(
        received=msg_data,
        data_decoded_xml="",
        data_binary_proto=bytes(msg_data.data_bytes),
        decoded_timestamp=datetime.utcnow(),
        sapient_version=sapient_version,
        error=None,
    )

    try:
        # Note: We need match the concrete SapientVersion to
        # the format of the incoming message. And not SapientVersion.LATEST
        # Otherwise, the validator will pick up spurious unknown/mandatory fields
        # This sapient_version should be setup via the connection_config["icd_version"]
        msg_parsed = empty_sapient_message(sapient_version)
        msg_parsed.ParseFromString(bytes(msg_data.data_bytes))
        result.data_json = MessageToJson(msg_parsed, preserving_proto_field_name=True)
    except DecodeError as e:
        result.error = NoisyError(f"DecodeError: {e}")
        return result

    if validator.is_validation_required():
        errors = []
        validator.validate_sapient_message(msg_parsed, result.received.timestamp, errors)
        if errors:
            error_str = "\n".join(e.full_str() for e in errors)
            result.error = NoisyError(f"Validation {len(errors)} errors:\n{error_str}")
            return result

        validate_message_with_all_sapient_versions = False
        # Enable flag to do more robust Message Conversion/validation Testing, with
        # Real/Simulated ASMs even if there are no configured ports needing that particular format.
        # Done by by intercepting all messages and trying to convert them. Errors are
        # only logged to the console for a ASM/Middleware developer to investigate further.
        if validate_message_with_all_sapient_versions:
            for final_version in [SapientVersion.LOWEST_PROTO, SapientVersion.LATEST]:
                if sapient_version != final_version:
                    msg_parsed_temp = empty_sapient_message(sapient_version)
                    msg_parsed_temp.ParseFromString(bytes(msg_data.data_bytes))
                    translated_message = to_version(
                        message=msg_parsed_temp,
                        version=sapient_version,
                        final_version=final_version,
                    )
                    translation_errors = []
                    validator.validate_sapient_message(
                        translated_message, result.received.timestamp, translation_errors
                    )
                    if translation_errors:
                        error_str = "\n".join(e.full_str() for e in errors)
                        logger.error(
                            f"Validation Errors with Version {sapient_version}"
                            + f"after translation to {final_version}: {error_str}"
                        )

    # Obtain the XML version of the message
    sensor_ulid = msg_parsed.node_id
    sensor_id = ""
    if enable_message_conversion:
        try:
            result.data_decoded_xml = ET.tostring(
                bsi_flex_v1_to_xml(
                    # xml translator built for bsi flex 335 version 1
                    to_version(msg_parsed, sapient_version, SapientVersion.BSI_FLEX_335_V1_0),
                    generator,
                ),
                encoding="utf-8",
                xml_declaration=True,
            )
        except Exception as e:
            result.error = NoisyError(f"TranslationError: {e}")
            return result

        if msg_parsed.node_id:
            sensor_id = generator.node_id_map[msg_parsed.node_id].xml_id
        else:
            sensor_ulid, sensor_id = generator.get_id_ulid_pair()

    if msg_parsed.HasField("registration"):
        if sensor_ulid == "":
            result.error = NoisyError("Registration missing node ID")
            return result
        result.registration = RegistrationRecord(msg_parsed.registration.short_name)
    elif msg_parsed.HasField("status_report"):
        if msg_parsed.status_report.info not in (
            StatusReport.INFO_NEW,
            StatusReport.INFO_UNCHANGED,
        ):
            result.error = NoisyError(
                "Unknown status info: " + StatusReport.System.Name(msg_parsed.status_report.info)
            )
            return result
        result.status_report = StatusReportRecord(
            system=StatusReport.System.Name(msg_parsed.status_report.system)[len("SYSTEM_") :],
            is_unchanged=msg_parsed.status_report.info == StatusReport.INFO_UNCHANGED,
        )
    elif msg_parsed.HasField("error"):
        result.error = SilentError(desc=",".join(msg_parsed.error.error_message))

    result.parsed = ParsedRecord(
        message_type=msg_parsed.WhichOneof("content"),
        node_id=sensor_ulid or None,
        internal_sensor_id=sensor_id or None,
        destination_node_id=msg_parsed.destination_id or None,
        message_timestamp=msg_parsed.timestamp.ToDatetime(),
        detection_confidence=msg_parsed.detection_report.detection_confidence or None,
        parsed_proto=msg_parsed,
        parsed_xml=(
            ET.fromstring(result.data_decoded_xml.strip()) if result.data_decoded_xml else None
        ),
    )

    return result
