#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#
import logging
import re
import struct
from collections.abc import Container
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from numbers import Real
from uuid import UUID

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message
from google.protobuf.unknown_fields import UnknownFieldSet

from sapient_msg import proto_options_pb2

logger = logging.getLogger("apex")


class ValidationType(Enum):
    # All mandatory fields are present
    MANDATORY_FIELDS_PRESENT = 1
    # All mandatory Oneof has at least one of its elements present
    MANDATORY_ONEOF_PRESENT = 2
    # All mandatory repeated has at least one element present
    MANDATORY_REPEATED_PRESENT = 3
    # No unknown fields have been included
    NO_UNKNOWN_FIELDS = 4
    # No unknown numeric enum values
    NO_UNKNOWN_ENUM_VALUES = 5
    # UUID and ULID fields are in their correct respective formats
    ID_FORMAT_VALID = 6
    # Message timestamp within reasonable time from current time
    MESSAGE_TIMESTAMP_REASONABLE = 7
    # Detection timestamp with reasonable time between detection and current time
    DETECTION_TIMESTAMP_REASONABLE = 8
    # Message ICD version is within the supported list
    SUPPORTED_ICD_VERSION = 9


@dataclass
class ValidationOptions:
    # What types of validation to perform
    types: Container[ValidationType] = ()
    # If true (and ID_FORMAT_VALID is enabled) then UUID must be UID v4, lower case,
    # with correct dashes, and no braces or URN prefix; ULID must be upper case
    strict_id_format: bool = True
    # Minimum and maximum relative times for message timestamp validation
    message_timestamp_range: tuple[timedelta, timedelta] = (
        timedelta(seconds=-0.9),
        timedelta(seconds=0.1),
    )
    # Minimum time between detection messages to not appear as suspicious scan time mistake
    detection_minimum_gap: timedelta = timedelta(seconds=0.08)
    # List of ICD versions supported
    supported_icd_versions: Container[str] = ()

    @staticmethod
    def from_config_dict(validation_config: dict):
        result = ValidationOptions()
        types_config = validation_config.get("validationTypes", [])
        try:
            result.types = set(ValidationType[str(t).upper()] for t in types_config)
        except KeyError as e:
            raise RuntimeError(f"Invalid validation type provided: {e}") from e
        if "strictIdFormat" in validation_config:
            if not isinstance(validation_config["strictIdFormat"], bool):
                raise RuntimeError("strictIdFormat validation config must be Boolean")
            result.strict_id_format = validation_config["strictIdFormat"]
        if "messageTimestampRange" in validation_config:
            ts_config = validation_config["messageTimestampRange"]
            if not isinstance(ts_config, list) or len(ts_config) != 2:
                raise RuntimeError("Validation messageTimestampRange config must have two items")
            if not all(isinstance(entry, Real) for entry in ts_config):
                raise RuntimeError("Values in messageTimestampRange must be numbers")
            result.message_timestamp_range = tuple(timedelta(seconds=s) for s in ts_config)
        if "detectionMinimumGap" in validation_config:
            result.detection_minimum_gap = timedelta(
                seconds=validation_config["detectionMinimumGap"]
            )
        if "supportedIcdVersions" in validation_config:
            result.supported_icd_versions = validation_config["supportedIcdVersions"]
        return result


@dataclass
class ValidationError:
    type: ValidationType
    message: str
    path: tuple

    def full_str(self) -> str:
        path_str = ".".join(self.path) if self.path else "(root)"
        type_str = self.type.name.lower().replace("_", " ")
        return f"{path_str} ({type_str}): {self.message}"


def _td_str(td: timedelta):
    if td < timedelta():
        return "-" + str(-td)
    else:
        return str(td)


def _format_unknown_field(field) -> str:
    """Formats an unknown field into a string for display.

    Formats numeric types into all possible values that the data could represent. For variable
    length data, hex and ascii representations are shown, which is all that can reasonably be shown
    for those. For a group field, only partial information is shown (list of child tags), but it is
    astronomically unlikely to encounter one in reality, so it is not worth the complexity of doing
    more.

    The wire type names are slightly odd (e.g. "i32" suggests an integer but it could be a float)
    but they are the official names e.g. as used in protoscope.
    """

    data = field.data
    if field.wire_type == 0:
        type_str = "varint"
        value_str = str(data)
        if data >= 0x8000000000000000:
            value_str += f" or {data - 0x10000000000000000}"
        if data & 1 == 0:
            value_zigzag = data // 2
        else:
            value_zigzag = -(data - 1) // 2
        value_str += f" or zigzag {value_zigzag})"

    elif field.wire_type == 1:
        type_str = "i64"
        value_str = str(data)
        if data >= 0x8000000000000000:
            value_str += f" or {data - 0x10000000000000000}"
        value_bytes = struct.pack("<Q", data)
        (value_float,) = struct.unpack("<d", value_bytes)
        value_str += f" or float {value_float}"

    elif field.wire_type == 5:
        type_str = "i32"
        value_str = str(data)
        if data >= 0x80000000:
            value_str += f" or {data - 0x100000000}"
        value_bytes = struct.pack("<I", data)
        (value_float,) = struct.unpack("<f", value_bytes)
        value_str += f" or float {value_float}"

    elif field.wire_type == 2:
        type_str = "len"
        value_str = f"({len(data)} bytes) {data[:20].hex(sep=' ')}"
        if len(data) > 20:
            value_str += " ..."
        value_str += '; ascii "'
        value_str += "".join(chr(b) if 32 <= b < 128 else "_" for b in data[:20]) + '"'
        if len(data) > 20:
            value_str += " ..."

    elif field.wire_type == 4:
        type_str = "group"
        numbers = [str(x.field_number) for x in data][:20]
        numbers_str = ", ".join(numbers)
        if len(numbers) > 20:
            numbers_str += ", ..."
        value_str = f"{len(data)} fields (field numbers: {numbers_str})"

    else:
        # Should be impossible as the above conditions are exhaustive
        type_str = "??"
        value_str = "??"

    return f"number: {field.field_number}, type: {field.wire_type} ({type_str}), data: {value_str}"


_valid_ulid_re = re.compile("[0-7][0-9A-HJKMNP-TV-Z]{25}")
_valid_ulid_ignorecase_re = re.compile(_valid_ulid_re.pattern, flags=re.IGNORECASE)
_valid_uuid4_re = re.compile("[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")


class Validator:
    def __init__(self, options: ValidationOptions):
        self.options = options
        self.previous_detection_time = None

    def _check_ulid_format_valid(self, value: object, errors: list[ValidationError], path: tuple):
        if isinstance(value, str):
            if self.options.strict_id_format:
                is_valid = _valid_ulid_re.fullmatch(value)
            else:
                is_valid = _valid_ulid_ignorecase_re.fullmatch(value)
            if not is_valid:
                errors.append(
                    ValidationError(ValidationType.ID_FORMAT_VALID, f"Invalid ULID: {value}", path)
                )

    def _check_uuid_format_valid(self, value: object, errors: list[ValidationError], path: tuple):
        if isinstance(value, str):
            if self.options.strict_id_format:
                is_valid = _valid_uuid4_re.fullmatch(value)
            else:
                try:
                    UUID(value)
                    is_valid = True
                except ValueError:
                    is_valid = False
            if not is_valid:
                errors.append(
                    ValidationError(ValidationType.ID_FORMAT_VALID, f"Invalid UUID: {value}", path)
                )

    def _check_enum_values_known(
        self,
        value: object,
        desc: FieldDescriptor,
        errors: list[ValidationError],
        path: tuple,
    ):
        if isinstance(value, int) and value not in desc.enum_type.values_by_number:
            errors.append(
                ValidationError(
                    ValidationType.NO_UNKNOWN_ENUM_VALUES,
                    f"Unknown enum value: {value}",
                    path,
                )
            )

    def _check_mandatory_oneof_fields(
        self, message: Message, errors: list[ValidationError], path: tuple
    ):
        for desc in message.DESCRIPTOR.oneofs:
            is_mandatory = (
                desc.GetOptions().Extensions[proto_options_pb2.oneof_options].is_mandatory
            )
            if is_mandatory and message.WhichOneof(desc.name) is None:
                errors.append(
                    ValidationError(
                        ValidationType.MANDATORY_ONEOF_PRESENT,
                        f"Missing mandatory OneOf field: {desc.name}",
                        path,
                    )
                )

    def _check_message_timestamp_reasonable(
        self, message: Message, received_time: datetime, errors: list[ValidationError]
    ):
        message_datetime = message.timestamp.ToDatetime()
        message_timedelta = message_datetime - received_time
        min_timedelta, max_timedelta = self.options.message_timestamp_range
        if message_timedelta < min_timedelta:
            errors.append(
                ValidationError(
                    ValidationType.MESSAGE_TIMESTAMP_REASONABLE,
                    f"Timestamp delta {_td_str(message_timedelta)} < {_td_str(min_timedelta)}",
                    (),
                )
            )
        if message_timedelta > max_timedelta:
            errors.append(
                ValidationError(
                    ValidationType.MESSAGE_TIMESTAMP_REASONABLE,
                    f"Timestamp delta {_td_str(message_timedelta)} > {_td_str(max_timedelta)}",
                    (),
                )
            )

    def _check_detection_timestamp_reasonable(
        self, message: Message, errors: list[ValidationError]
    ):
        message_datetime = message.timestamp.ToDatetime()
        if self.previous_detection_time is not None:
            detection_timedelta = message_datetime - self.previous_detection_time
            if timedelta() < detection_timedelta < self.options.detection_minimum_gap:
                errors.append(
                    ValidationError(
                        ValidationType.DETECTION_TIMESTAMP_REASONABLE,
                        f"Detection time delta {detection_timedelta} too small",
                        (),
                    )
                )
            if detection_timedelta < timedelta():
                errors.append(
                    ValidationError(
                        ValidationType.DETECTION_TIMESTAMP_REASONABLE,
                        f"Detection time {message_datetime} earlier than previous "
                        f"{self.previous_detection_time}",
                        (),
                    )
                )
        self.previous_detection_time = message_datetime

    def _check_no_unknown_fields(
        self, message: Message, errors: list[ValidationError], path: tuple
    ):
        unknown_fields = UnknownFieldSet(message)
        for f in unknown_fields:
            errors.append(
                ValidationError(
                    ValidationType.NO_UNKNOWN_FIELDS,
                    "Unknown field " + _format_unknown_field(f),
                    path,
                )
            )

    def validate_field(
        self,
        desc: FieldDescriptor,
        value: object,
        errors: list[ValidationError],
        path: tuple,
    ):
        is_repeated = desc.label == FieldDescriptor.LABEL_REPEATED

        if (
            ValidationType.MANDATORY_FIELDS_PRESENT in self.options.types
            and desc.GetOptions().Extensions[proto_options_pb2.field_options].is_mandatory
            and not is_repeated
        ):
            if value is None:
                errors.append(
                    ValidationError(
                        ValidationType.MANDATORY_FIELDS_PRESENT,
                        f"Missing mandatory field: {desc.name}",
                        path,
                    )
                )
        if ValidationType.SUPPORTED_ICD_VERSION in self.options.types:
            if desc.type == FieldDescriptor.TYPE_STRING and "icd_version" in desc.name:
                # Allow existing nodes which used "_" for icd_version i.e
                # "BSI_Flex_335_v1.0" instead of "BSI Flex 335 v1.0"
                adjusted_value = value.replace("_", " ")
                if adjusted_value not in self.options.supported_icd_versions:
                    errors.append(
                        ValidationError(
                            ValidationType.SUPPORTED_ICD_VERSION,
                            f"Unsupported ICD version: {desc.name}: {value}",
                            path,
                        )
                    )
        if (
            ValidationType.MANDATORY_REPEATED_PRESENT in self.options.types
            and desc.GetOptions().Extensions[proto_options_pb2.field_options].is_mandatory
            and is_repeated
        ):
            if value is None:
                errors.append(
                    ValidationError(
                        ValidationType.MANDATORY_REPEATED_PRESENT,
                        f"Missing mandatory repeated field: {desc.name}",
                        path,
                    )
                )

        if (
            ValidationType.ID_FORMAT_VALID in self.options.types
            and desc.GetOptions().Extensions[proto_options_pb2.field_options].is_ulid
        ):
            self._check_ulid_format_valid(value, errors, path)

        if (
            ValidationType.ID_FORMAT_VALID in self.options.types
            and desc.GetOptions().Extensions[proto_options_pb2.field_options].is_uuid
        ):
            self._check_uuid_format_valid(value, errors, path)

        if (
            ValidationType.NO_UNKNOWN_ENUM_VALUES in self.options.types
            and desc.type == FieldDescriptor.TYPE_ENUM
        ):
            self._check_enum_values_known(value, desc, errors, path)

        # If this field is a nested message, check its component fields
        if desc.type == FieldDescriptor.TYPE_MESSAGE and value is not None:
            if desc.message_type.full_name.startswith("sapient_msg."):
                if is_repeated:
                    for i, msg in enumerate(value):
                        self.validate_message(msg, errors, (*path, str(i)))
                else:
                    self.validate_message(value, errors, path)

    def validate_message(self, message: Message, errors: list[ValidationError], path: list = ()):
        if ValidationType.NO_UNKNOWN_FIELDS in self.options.types:
            self._check_no_unknown_fields(message, errors, path)

        if ValidationType.MANDATORY_ONEOF_PRESENT in self.options.types:
            self._check_mandatory_oneof_fields(message, errors, path)

        # Check individual fields in the message
        present_fields_by_descriptor = dict(message.ListFields())
        for field_desc in message.DESCRIPTOR.fields:
            value = present_fields_by_descriptor.get(field_desc)
            self.validate_field(field_desc, value, errors, path + (field_desc.name,))

    def validate_sapient_message(
        self,
        message: Message,
        received_time: datetime,
        errors: list[ValidationError],
        validate_contents: bool = True,
    ):
        if ValidationType.MESSAGE_TIMESTAMP_REASONABLE in self.options.types:
            self._check_message_timestamp_reasonable(message, received_time, errors)
        if (
            ValidationType.DETECTION_TIMESTAMP_REASONABLE in self.options.types
            and message.HasField("detection_report")
        ):
            self._check_detection_timestamp_reasonable(message, errors)

        if validate_contents:
            self.validate_message(message, errors)

    def is_validation_required(self) -> bool:
        return len(self.options.types) > 0
