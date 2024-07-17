#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Contains the implementation of XML to protobuf conversion.

Most users will want to use from_xml.Converter, which is implemented with the routines in this
module, rather than using these functions directly.

These functions rely on protobuf reflection: Each XML element (and attribute and text value) is
compared against the list of fields in the protobuf object, and the matching one is filled in. The
DescriptorCache class is used to speed up this lookup.

These routines do not throw exceptions (at least, they are expected not to). Instead, they report
any problems with the XML by appending an error message to the errors list argument, and continuing
to parse the rest of the XML if possible.
"""
import xml.etree.ElementTree as ET
from base64 import b64decode
from typing import Dict, List

import ulid
from google.protobuf.descriptor import FieldDescriptor
from google.protobuf.message import Message
from google.protobuf.timestamp_pb2 import Timestamp

from sapient_apex_server.time_util import datetime_str_to_int, str_to_datetime
from sapient_apex_server.translator.id_generator import IdGenerator, SensorIdMapping
from sapient_apex_server.xml_conversion.from_xml_descriptor_cache import DescriptorCache
from sapient_apex_server.xml_conversion.naming import get_message_xml_name
from sapient_msg import proto_options_pb2


def _is_sapient_ignore_field(
    child: ET.Element,
    element_fields: Dict[str, FieldDescriptor],
    is_sapient_message: bool,
):
    is_ignore = False
    if is_sapient_message:
        if child.tag in ["sourceID", "timestamp", "sensorID"]:
            is_ignore = True
        if "region" in element_fields.keys():
            is_ignore = True
        if "regionArea" in element_fields.keys():
            is_ignore = True
    return is_ignore


def _get_id_map(generator: IdGenerator, map_name: str, node_id: str = None) -> Dict[str, int]:
    registry_mapping = generator.id_map_registry[map_name]
    if generator.is_node_id_map(map_name):
        registry_mapping = registry_mapping[node_id].map_registry[map_name]
    return registry_mapping


def populate_message_field(
    descriptor_cache: DescriptorCache,
    message: Message,
    elem: ET.Element,
    errors: List[str],
    generator: IdGenerator,
    is_sapient_message: bool,
    node_id: str,
):
    """Populates a single field of a message from the given XML element.

    This covers the case that the message passed in actually represents a choice of several possible
    messages; each field in the message represents a different conceptual message. This routine
    uses the name of the root element to determine which of those fields to fill in.
    """
    for field in message.DESCRIPTOR.fields:
        if (
            field.type == FieldDescriptor.TYPE_MESSAGE
            and field.label != FieldDescriptor.LABEL_REPEATED
            and get_message_xml_name(field.message_type) == elem.tag
        ):
            child_message = getattr(message, field.name)
            populate_message(
                descriptor_cache,
                child_message,
                elem,
                errors,
                generator,
                is_sapient_message,
                node_id,
            )
            return

    errors.append(f"Message type {elem.tag} not recognised")


def populate_message(
    descriptor_cache: DescriptorCache,
    message: Message,
    elem: ET.Element,
    errors: List[str],
    generator: IdGenerator,
    is_sapient_message: bool,
    node_id: str,
):
    """Populates a protobuf message with the contents of the given XML element."""

    # A little setup
    descriptor_cache.populate(message.DESCRIPTOR)
    fields_map = descriptor_cache.message_fields_map_cache[message.DESCRIPTOR]
    message_name = message.DESCRIPTOR.name

    # Text
    text = elem.text.strip() if elem.text else None
    if text:
        if fields_map.text_field is None:
            errors.append(f"In message {message_name}, unexpected text in element")
        else:
            populate_basic_field(
                descriptor_cache,
                message,
                fields_map.text_field,
                text,
                errors,
                generator,
                node_id,
            )

    # Attributes
    for attrib_name, attrib_value in elem.attrib.items():
        field = fields_map.attribute_fields.get(attrib_name)
        if field is None:
            pass
        else:
            populate_basic_field(
                descriptor_cache,
                message,
                field,
                attrib_value,
                errors,
                generator,
                node_id,
            )

    # Elements
    for child in elem:
        field = fields_map.element_fields.get(child.tag)
        if field is None:
            if not _is_sapient_ignore_field(child, fields_map.element_fields, is_sapient_message):
                errors.append(f"In message {message_name}, unknown element {child.tag}")
            continue
        if field.type == FieldDescriptor.TYPE_MESSAGE:
            singly_nested_name = (
                field.GetOptions().Extensions[proto_options_pb2.field_options].xml_singly_nested
            )
            if singly_nested_name:
                populate_singly_nested(
                    descriptor_cache,
                    message,
                    field,
                    singly_nested_name,
                    child,
                    errors,
                    generator,
                    is_sapient_message,
                    node_id,
                )
            elif field.GetOptions().Extensions[proto_options_pb2.field_options].is_proto_time:
                populate_basic_field(
                    descriptor_cache,
                    message,
                    field,
                    child.text,
                    errors,
                    generator,
                    node_id,
                )
            else:
                if field.label == FieldDescriptor.LABEL_REPEATED:
                    child_message = getattr(message, field.name).add()
                else:
                    if message.HasField(field.name):
                        errors.append(
                            f"In message {message_name}, got duplicated element {child.tag}"
                        )
                    child_message = getattr(message, field.name)
                populate_message(
                    descriptor_cache,
                    child_message,
                    child,
                    errors,
                    generator,
                    is_sapient_message,
                    node_id,
                )
        else:
            value = child.text.strip() if child.text is not None else None
            if value:
                populate_basic_field(
                    descriptor_cache, message, field, value, errors, generator, node_id
                )


def populate_singly_nested(
    descriptor_cache: DescriptorCache,
    message: Message,
    field: FieldDescriptor,
    element_name: str,
    elem: ET.Element,
    errors: List[str],
    generator: IdGenerator,
    is_sapient_message: bool,
    node_id: str,
):
    """Used in the implementation of populate_message for singly nested fields."""
    for child in elem:
        if child.tag != element_name:
            errors.append(f"In singly-nested field {field.name} got unexpected element {child.tag}")
            continue
        if field.label == FieldDescriptor.LABEL_REPEATED:
            child_message = getattr(message, field.name).add()
        else:
            if message.HasField(field.name):
                errors.append(
                    f"In message {message.DESCRIPTOR.name}, got duplicated element {child.tag}"
                )
            child_message = getattr(message, field.name)
        populate_message(
            descriptor_cache,
            child_message,
            child,
            errors,
            generator,
            is_sapient_message,
            node_id,
        )


FIELD_INT_TYPES = (
    FieldDescriptor.TYPE_FIXED32,
    FieldDescriptor.TYPE_FIXED64,
    FieldDescriptor.TYPE_SFIXED32,
    FieldDescriptor.TYPE_SFIXED64,
    FieldDescriptor.TYPE_UINT32,
    FieldDescriptor.TYPE_UINT64,
    FieldDescriptor.TYPE_SINT32,
    FieldDescriptor.TYPE_SINT64,
    FieldDescriptor.TYPE_INT32,
    FieldDescriptor.TYPE_INT64,
)


def populate_basic_field(
    descriptor_cache: DescriptorCache,
    message: Message,
    field_desc: FieldDescriptor,
    value: str,
    errors: List[str],
    generator: IdGenerator,
    node_id: str,
):
    """Used in the implementation of populate_message for basic (i.e. non-message) fields."""
    try:
        value_parsed = None
        if field_desc.GetOptions().Extensions[proto_options_pb2.field_options].is_proto_time:
            value_parsed = Timestamp()
            value_parsed.FromDatetime(str_to_datetime(value))
        elif field_desc.type == FieldDescriptor.TYPE_BOOL:
            value_parsed = value.strip().lower() == "true"
        elif field_desc.type in (
            FieldDescriptor.TYPE_FLOAT,
            FieldDescriptor.TYPE_DOUBLE,
        ):
            value_parsed = float(value)
        elif field_desc.type in FIELD_INT_TYPES:
            if field_desc.GetOptions().Extensions[proto_options_pb2.field_options].is_time:
                value_parsed = datetime_str_to_int(value)
            else:
                value_parsed = int(value)
        elif field_desc.type == FieldDescriptor.TYPE_ENUM:
            values_cache = descriptor_cache.enum_values_cache[field_desc.enum_type]
            value_normalised = value.replace(" ", "").upper()
            if value_normalised in values_cache:
                value_parsed = values_cache[value_normalised]
            else:
                errors.append(
                    f"Unknown enum value {value}, expected one of {','.join(values_cache.keys())}"
                )
        elif field_desc.type == FieldDescriptor.TYPE_STRING:
            if field_desc.GetOptions().Extensions[proto_options_pb2.field_options].is_ulid:
                id_map = _get_id_map(generator, field_desc.name, node_id)
                if len(id_map.values()) > 0 and isinstance(
                    list(id_map.values())[0], SensorIdMapping
                ):
                    mapping_fn = lambda x: x.xml_id  # noqa E731
                else:
                    mapping_fn = lambda x: x  # noqa E731
                if int(value) in map(mapping_fn, id_map.values()):
                    value_parsed = generator.get_ulid_from_id(id_map, int(value))
                else:
                    value_parsed = ulid.new().str
                    generator.insert_new_ulid_id_pair(
                        value_parsed,
                        int(value),
                        id_map,
                        generator.is_node_id_map(field_desc.name),
                    )
            else:
                value_parsed = value
        elif field_desc.type == FieldDescriptor.TYPE_BYTES:
            value_parsed = b64decode(value)
        else:
            errors.append(f"Unknown field type {field_desc.type}")

        if field_desc.label == FieldDescriptor.LABEL_REPEATED:
            getattr(message, field_desc.name).append(value_parsed)
        else:
            try:
                field_already_set = message.HasField(field_desc.name)
            except ValueError:
                all_fields = set([field[0].name for field in message.ListFields()])
                field_already_set = field_desc.name in all_fields
            if field_already_set:
                errors.append(f"Got duplicated element for {field_desc.name}")
            if isinstance(value_parsed, Timestamp):
                getattr(message, field_desc.name).CopyFrom(value_parsed)
            else:
                setattr(message, field_desc.name, value_parsed)

    except Exception as e:
        errors.append(
            f'In message {message.DESCRIPTOR.name} field {field_desc.name} with value "{value}" '
            f"got error: {e}"
        )
