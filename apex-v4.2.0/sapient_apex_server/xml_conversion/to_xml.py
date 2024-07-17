#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Converts from protobuf to XML."""


import xml.etree.ElementTree as ET
from base64 import b64encode
from enum import Enum
from typing import Optional

from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message

from sapient_apex_server.time_util import datetime_int_to_str, datetime_to_str
from sapient_apex_server.translator.id_generator import IdGenerator
from sapient_apex_server.xml_conversion.naming import (
    get_enum_value_xml_name,
    get_field_xml_name,
    get_message_xml_name,
)
from sapient_msg import proto_options_pb2


class WhichFields(Enum):
    """Possible levels of detail to include in XML output."""

    OFFICIAL = 0  # Only fields in the official standard
    TENTATIVE = 1  # Also include tentative fields submitted for inclusion in the standard
    ALL = 2  # All fields, even xml_ignore


def message_to_element(
    message: Message,
    node_id: str,
    which_fields: WhichFields = WhichFields.ALL,
    generator: Optional[IdGenerator] = None,
) -> ET.Element:
    """Converts a message directly into XML."""
    result = ET.Element(get_message_xml_name(message.DESCRIPTOR))
    _populate_message(message, result, which_fields, generator, node_id)
    ET.indent(result)
    return result


def message_field_to_element(
    message: Message, node_id: str, which_fields: WhichFields = WhichFields.ALL
):
    """Converts a single field within a message to XML."""
    result = None
    for field_desc, value in message.ListFields():
        if field_desc.type != FieldDescriptor.TYPE_MESSAGE:
            raise ValueError("Non-message field populated")
        if result is not None:
            # This for loop should have precisely one iteration
            raise ValueError("Multiple fields populated in message")
        result = message_to_element(value, node_id, which_fields)
    if result is None:
        raise ValueError("No field populated")
    return result


def _populate_message(
    message: Message,
    elem: ET.Element,
    which_fields: WhichFields,
    generator: Optional[IdGenerator],
    node_id: str,
):
    """Converts all fields in a message to an XML element."""
    for field_desc, value in message.ListFields():
        field_name = get_field_xml_name(field_desc)
        singly_nested_name = (
            field_desc.GetOptions().Extensions[proto_options_pb2.field_options].xml_singly_nested
        )
        if singly_nested_name:
            field_parent = ET.SubElement(elem, field_name)
            field_name = singly_nested_name
        else:
            field_parent = elem
        if field_desc.label == FieldDescriptor.LABEL_REPEATED:
            for individual_value in value:
                _populate_field(
                    field_parent,
                    field_name,
                    field_desc,
                    individual_value,
                    which_fields,
                    generator,
                    node_id,
                )
        else:
            _populate_field(
                field_parent,
                field_name,
                field_desc,
                value,
                which_fields,
                generator,
                node_id,
            )


def _populate_field(
    parent_elem: ET.Element,
    field_name: str,
    field_desc: FieldDescriptor,
    value: object,
    which_fields: WhichFields,
    generator: Optional[IdGenerator],
    node_id: str,
):
    """Converts one field within a message into XML child element (or attribute or text)."""

    # Check if this field should be converted at all
    ignored = (
        which_fields in (WhichFields.OFFICIAL, WhichFields.TENTATIVE)
        and field_desc.GetOptions().Extensions[proto_options_pb2.field_options].xml_ignore
    ) or (
        which_fields == WhichFields.OFFICIAL
        and field_desc.GetOptions().Extensions[proto_options_pb2.field_options].xml_tentative
    )
    if ignored:
        return

    # If field is a message, defer back to populate_message
    if (
        field_desc.type == FieldDescriptor.TYPE_MESSAGE
        and not field_desc.GetOptions().Extensions[proto_options_pb2.field_options].is_proto_time
    ):
        _populate_message(
            value,
            ET.SubElement(parent_elem, field_name),
            which_fields,
            generator,
            node_id,
        )
        return

    # Otherwise, start by turning value to a string
    if (
        field_desc.GetOptions().Extensions[proto_options_pb2.field_options].is_ulid
        and generator is not None
    ):
        id_map = generator.id_map_registry[field_desc.name]
        if generator.is_node_id_map(field_desc.name):
            id_map = id_map[node_id].map_registry[field_desc.name]
        if value in id_map.keys():
            value_str = str(
                id_map[value] if isinstance(id_map[value], int) else id_map[value].xml_id
            )
        else:
            value_int = generator.get_next_id()
            id_map[value] = value_int
            value_str = str(value_int)
    elif field_desc.type == FieldDescriptor.TYPE_BOOL:
        value_str = "true" if value else "false"
    elif field_desc.GetOptions().Extensions[proto_options_pb2.field_options].is_proto_time:
        value_str = datetime_to_str(value.ToDatetime())
    elif field_desc.GetOptions().Extensions[proto_options_pb2.field_options].is_time:
        value_str = datetime_int_to_str(value)
    elif field_desc.type == FieldDescriptor.TYPE_ENUM:
        value_str = get_enum_value_xml_name(field_desc.enum_type.values_by_number[value])
    elif field_desc.type == FieldDescriptor.TYPE_BYTES:
        value_str = b64encode(value).decode("ascii")
    elif field_desc.type == FieldDescriptor.TYPE_STRING:
        value_str = value
    else:
        value_str = str(value)  # Python's standard conversion for float/int

    # Then put that string in the right place
    if field_desc.GetOptions().Extensions[proto_options_pb2.field_options].xml_is_parent_value:
        parent_elem.text = value_str
    elif field_desc.GetOptions().Extensions[proto_options_pb2.field_options].xml_is_attribute:
        parent_elem.attrib[field_name] = value_str
    else:
        ET.SubElement(parent_elem, field_name).text = value_str
