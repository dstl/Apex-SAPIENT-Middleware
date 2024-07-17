#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from google.protobuf.json_format import MessageToDict, ParseDict
from google.protobuf.message import Message
from sapient_apex_server.structures import SapientVersion
from typing import Dict, Union

import logging
import string

from sapient_msg.bsi_flex_335_v1_0.sapient_message_pb2 import (
    SapientMessage as BsiFlexV1SapientMessage,
)
from sapient_msg.bsi_flex_335_v2_0.sapient_message_pb2 import (
    SapientMessage as BsiFlexV2SapientMessage,
)

SapientMessage = Union[BsiFlexV1SapientMessage, BsiFlexV2SapientMessage]

logger = logging.getLogger(__name__)


def _convert_single_to_repeated(
    process_dict: Dict,
    key_name: str,
):
    current_item = process_dict.get(key_name)
    if current_item:
        process_dict[key_name] = [current_item]


def _convert_repeated_to_single(
    process_dict: Dict,
    key_name: str,
):
    # Attempt to get all the repeated items & flatten into a
    # single longer item. For non string types, its just
    # the 1st item which will be used.
    current_items = process_dict.get(key_name, [])
    if current_items:
        single_item = None
        if isinstance(current_items[0], str):
            single_item = ",".join(current_items)
        else:
            single_item = current_items[0]

        # Replace existing repeated item with the single item
        process_dict[key_name] = single_item


def _convert_string_to_enum(
    process_dict: Dict,
    key_name: str,
    enum_prefix: str,
    replace_value: bool = True,
):
    """
    Converts a string value ito an enum value with the enum_prefix
    LookAt => COMMAND_TYPE_LOOK_AT
    Mains or MAINS or mains => POWERSOURCE_MAINS
    """
    enum_value = process_dict.get(key_name, "")
    if enum_value:
        enum_value_snake_case = ""
        for char_index, char_value in enumerate(enum_value):
            # Add a '_' to the calculated enum value for every
            # upper case character, except for the 1st one and
            # and not if the previous character was already uppercase
            if char_index and char_value.isupper() and not enum_value[char_index - 1].isupper():
                enum_value_snake_case += "_"

            enum_value_snake_case += char_value

        enum_value = enum_prefix + enum_value_snake_case.upper()
        if replace_value:
            process_dict[key_name] = enum_value

    return enum_value


def _convert_enum_to_string(
    process_dict: Dict,
    key_name: str,
    enum_prefix: str,
    replace_value: bool = True,
):
    """
    Converts a enum value string in a normal string
    COMMAND_TYPE_LOOK_AT => LookAt
    """
    enum_value = process_dict.get(key_name, "")
    if enum_value:
        enum_value = enum_value.replace(enum_prefix, "")

        if enum_value != "OK":
            enum_value = string.capwords(enum_value, sep="_").replace("_", "")

        if replace_value:
            process_dict[key_name] = enum_value

    return enum_value


def _remove_fields(message_dict: dict, field_names: list[str]):
    for key_name in field_names:
        if key_name in message_dict:
            message_dict.pop(key_name)


def _registration_translate_v1_to_v2(message_dict: dict) -> bool:
    registration_dict = message_dict.get("registration", {})
    if not registration_dict:
        logger.error("Expected registration data is missing")
        return False

    registration_dict["icd_version"] = "BSI Flex 335 v2.0"

    # 3 New fields
    # dependent_nodes, reporting_region & config_data
    # Only config_data is mandatory
    registration_dict["config_data"] = [{"manufacturer": "manufacturer", "model": "model"}]

    mode_definitions = registration_dict.get("mode_definition", [])

    # In message “Command”
    # Removed “name” field because it is a duplicate
    for mode_definition in mode_definitions:
        # BSI V1 protos for detection_definition & task were inconsistent to the ICD.
        # This is now corrected in BSI V2
        _convert_single_to_repeated(mode_definition, "detection_definition")
        _convert_repeated_to_single(mode_definition, "task")

        task = mode_definition.get("task", {})
        if task:
            commands = task.get("command", [])
            for command in commands:
                if "name" in command:
                    command.pop("name")

    return True


def _registration_translate_v2_to_v1(message_dict: dict) -> bool:
    registration_dict = message_dict.get("registration", {})
    if not registration_dict:
        logger.error("Expected registration data is missing")
        return False

    # Inverse of upgrade

    registration_dict["icd_version"] = "BSI Flex 335 v1.0"

    # Remove newer V2 fields
    _remove_fields(
        registration_dict,
        [
            "dependent_nodes",
            "reporting_region",
            "config_data",
        ],
    )

    # name was a mandatory field in V1, so need to reconstruct its
    # value back from CommandType enum instead
    mode_definitions = registration_dict.get("mode_definition", [])

    for mode_definition in mode_definitions:
        _convert_repeated_to_single(mode_definition, "detection_definition")
        _convert_single_to_repeated(mode_definition, "task")

        tasks = mode_definition.get("task", [])
        for task in tasks:
            commands = task.get("command", [])
            for command in commands:
                if "type" in command:
                    # Get the string representation of the type enum
                    command_name = _convert_enum_to_string(
                        process_dict=command,
                        key_name="type",
                        enum_prefix="COMMAND_TYPE_",
                        replace_value=False,
                    )
                    if command_name:
                        command["name"] = command_name

    return True


def _registration_ack_translate_v1_to_v2(message_dict: dict) -> bool:
    registation_ack_dict = message_dict.get("registration_ack", {})
    if not registation_ack_dict:
        logger.error("Expected registration_ack data is missing")
        return False

    # ack_response_reason now ‘repeated’ to allow for a list of reasons
    _convert_single_to_repeated(
        process_dict=registation_ack_dict,
        key_name="ack_response_reason",
    )

    return True


def _registration_ack_translate_v2_to_v1(message_dict: dict) -> bool:
    registation_ack_dict = message_dict.get("registration_ack", {})
    if not registation_ack_dict:
        logger.error("Expected registration_ack data is missing")
        return False

    # Inverse of upgrade

    _convert_repeated_to_single(
        process_dict=registation_ack_dict,
        key_name="ack_response_reason",
    )

    return True


def _status_report_translate_v1_to_v2(message_dict: dict) -> bool:
    status_report_dict = message_dict.get("status_report", {})
    if not status_report_dict:
        logger.error("Expected status_report data is missing")
        return False

    # The coverage field has been made repeated
    _convert_single_to_repeated(
        process_dict=status_report_dict,
        key_name="coverage",
    )

    # source & status are now enums
    power_dict = status_report_dict.get("power", {})
    if power_dict:
        _convert_string_to_enum(
            process_dict=power_dict,
            key_name="source",
            enum_prefix="POWERSOURCE_",
        )
        _convert_string_to_enum(
            process_dict=power_dict,
            key_name="status",
            enum_prefix="POWERSTATUS_",
        )

    # StatusLevel.STATUS_LEVEL_SENSOR_STATUS is removed
    statuses = status_report_dict.get("status", [])
    for status in statuses:
        if "status_level" in status and status["status_level"] == "STATUS_LEVEL_SENSOR_STATUS":
            status["status_level"] == "STATUS_LEVEL_UNSPECIFIED"

        # status_type change to an enumeration
        _convert_string_to_enum(
            process_dict=status,
            key_name="status_type",
            enum_prefix="STATUS_TYPE_",
        )

    return True


def _status_report_translate_v2_to_v1(message_dict: dict) -> bool:
    status_report_dict = message_dict.get("status_report", {})
    if not status_report_dict:
        logger.error("Expected status_report data is missing")
        return False

    # Inverse of upgrade

    _convert_repeated_to_single(
        process_dict=status_report_dict,
        key_name="coverage",
    )

    # change source & status enums back to strings
    power_dict = status_report_dict.get("power", {})
    if power_dict:
        _convert_enum_to_string(
            process_dict=power_dict,
            key_name="source",
            enum_prefix="POWERSOURCE_",
        )
        _convert_enum_to_string(
            process_dict=power_dict,
            key_name="status",
            enum_prefix="POWERSTATUS_",
        )

    # StatusLevel.STATUS_LEVEL_SENSOR_STATUS is removed, nothing to restore here
    statuses = status_report_dict.get("status", [])
    for status in statuses:
        # status_type change to an enumeration
        _convert_enum_to_string(
            process_dict=status,
            key_name="status_type",
            enum_prefix="STATUS_TYPE_",
        )

    return True


def _task_translate_v1_to_v2(message_dict: dict) -> bool:
    task_dict = message_dict.get("task", {})
    if not task_dict:
        logger.error("Expected task data is missing")
        return False

    if "control" in task_dict:
        # Default task has been removed in v2 as it is not possible to define
        if task_dict["control"] == "CONTROL_DEFAULT":
            # Set to unspecified (this will be considered by validation as not set & may error)
            task_dict["control"] = "CONTROL_UNSPECIFIED"

    return True


def _task_translate_v2_to_v1(message_dict: dict) -> bool:
    task_dict = message_dict.get("task", {})
    if not task_dict:
        logger.error("Expected task data is missing")
        return False

    # CONTROL_DEFAULT was been removed in v2 so we treat it as an unrequired
    # value for all standards and not try to add it back.
    if "control" in task_dict:
        pass

    return True


def _task_ack_translate_v1_to_v2(message_dict: dict) -> bool:
    task_ack_dict = message_dict.get("task_ack", {})
    if not task_ack_dict:
        logger.error("Expected task_ack data is missing")
        return False

    # the reason field is now ‘repeated’ to allow a list of reasons
    _convert_single_to_repeated(
        process_dict=task_ack_dict,
        key_name="reason",
    )

    return True


def _task_ack_translate_v2_to_v1(message_dict: dict) -> bool:
    task_ack_dict = message_dict.get("task_ack", {})
    if not task_ack_dict:
        logger.error("Expected task_ack data is missing")
        return False

    # Inverse of upgrade

    _convert_repeated_to_single(
        process_dict=task_ack_dict,
        key_name="reason",
    )

    return True


def _alert_ack_translate_v1_to_v2(message_dict: dict) -> bool:
    alert_ack_dict = message_dict.get("alert_ack", {})
    if not alert_ack_dict:
        logger.error("Expected alert_ack data is missing")
        return False

    # the reason field is now ‘repeated’ to allow a list of reasons
    _convert_single_to_repeated(
        process_dict=alert_ack_dict,
        key_name="reason",
    )

    # ‘alert_status’ renamed to ‘alert_ack_status’
    if "alert_status" in alert_ack_dict:
        alert_ack_dict["alert_ack_status"] = alert_ack_dict.pop("alert_status").replace(
            "ALERT_STATUS_", "ALERT_ACK_STATUS_"
        )

    return True


def _alert_ack_translate_v2_to_v1(message_dict: dict) -> bool:
    alert_ack_dict = message_dict.get("alert_ack", {})
    if not alert_ack_dict:
        logger.error("Expected alert_ack data is missing")
        return False

    # Inverse of upgrade

    _convert_repeated_to_single(
        process_dict=alert_ack_dict,
        key_name="reason",
    )

    if "alert_ack_status" in alert_ack_dict:
        alert_ack_dict["alert_status"] = alert_ack_dict.pop("alert_ack_status").replace(
            "ALERT_ACK_STATUS_", "ALERT_STATUS_"
        )

    return True


def _error_translate_v1_to_v2(message_dict: dict) -> bool:
    error_dict = message_dict.get("error", {})
    if not error_dict:
        return False

    # the error_message field is now ‘repeated’ to allow a list of error messages
    _convert_single_to_repeated(
        process_dict=error_dict,
        key_name="error_message",
    )

    return True


def _error_translate_v2_to_v1(message_dict: dict) -> bool:
    error_dict = message_dict.get("error", {})
    if not error_dict:
        return False

    # Inverse of upgrade
    _convert_repeated_to_single(
        process_dict=error_dict,
        key_name="error_message",
    )

    return True


def translate_v1_to_v2(message: Message) -> Message:
    """
    Upgrade a V1 SapientMessage to V2

    Args:
        message (Message): A BSI V1 Sapient Message

    Returns:
        Message: A BSI V2 Sapient Message
    """
    message_dict = MessageToDict(message, preserving_proto_field_name=True)
    translated_message = empty_sapient_message(version=SapientVersion.BSI_FLEX_335_V2_0)

    try:
        translation_result = False
        if "registration" in message_dict:
            translation_result = _registration_translate_v1_to_v2(message_dict)
        elif "registration_ack" in message_dict:
            translation_result = _registration_ack_translate_v1_to_v2(message_dict)
        elif "status_report" in message_dict:
            translation_result = _status_report_translate_v1_to_v2(message_dict)
        elif "task" in message_dict:
            translation_result = _task_translate_v1_to_v2(message_dict)
        elif "task_ack" in message_dict:
            translation_result = _task_ack_translate_v1_to_v2(message_dict)
        elif "alert_ack" in message_dict:
            translation_result = _alert_ack_translate_v1_to_v2(message_dict)
        elif "error" in message_dict:
            translation_result = _error_translate_v1_to_v2(message_dict)
        else:
            # v1 Message not requiring translation to v2
            translation_result = True

        if translation_result:
            # Now convert the translated dict with the concrete sapient message type
            # which should succeed provided it passes the proto schema for this
            # sapient version.
            translated_message = ParseDict(message_dict, translated_message)
        else:
            logger.warning("translate_v2_to_v1 incomplete translation or unexpected input data")
    except Exception as e:
        logger.error(f"translate_v1_to_v2 failed, got error: {e}")

    return translated_message


def translate_v2_to_v1(message: Message) -> Message:
    """
    Downgrade a V2 SapientMessage to V1

    Args:
        message (Message): A BSI V2 Sapient Message

    Returns:
        Message: A BSI V1 Sapient Message
    """
    message_dict = MessageToDict(message, preserving_proto_field_name=True)
    translated_message = empty_sapient_message(version=SapientVersion.BSI_FLEX_335_V1_0)

    try:
        translation_result = False
        if "registration" in message_dict:
            translation_result = _registration_translate_v2_to_v1(message_dict)
        elif "registration_ack" in message_dict:
            translation_result = _registration_ack_translate_v2_to_v1(message_dict)
        elif "status_report" in message_dict:
            translation_result = _status_report_translate_v2_to_v1(message_dict)
        elif "task" in message_dict:
            translation_result = _task_translate_v2_to_v1(message_dict)
        elif "task_ack" in message_dict:
            translation_result = _task_ack_translate_v2_to_v1(message_dict)
        elif "alert_ack" in message_dict:
            translation_result = _alert_ack_translate_v2_to_v1(message_dict)
        elif "error" in message_dict:
            translation_result = _error_translate_v2_to_v1(message_dict)
        else:
            # v2 Message not requiring translation to v1
            translation_result = True

        if translation_result:
            # Now convert the translated dict with the concrete sapient message type
            # which should succeed provided it passes the proto schema for this
            # sapient version.
            translated_message = ParseDict(message_dict, translated_message)
        else:
            logger.warning("translate_v2_to_v1 incomplete translation or unexpected input data")
    except Exception as e:
        logger.error(f"translate_v2_to_v1 failed, got error: {e}")

    return translated_message


def empty_sapient_message(version: SapientVersion) -> SapientMessage:
    if version == SapientVersion.VERSION6:
        raise ValueError("Sapient Version 6 is not protobuf")

    return {
        SapientVersion.BSI_FLEX_335_V1_0: BsiFlexV1SapientMessage,
        SapientVersion.BSI_FLEX_335_V2_0: BsiFlexV2SapientMessage,
    }[version]()
