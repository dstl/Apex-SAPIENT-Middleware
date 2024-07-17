#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Cache of mapping from XML field names and enum value names to protobuf descriptors.

This is used internally in the from_xml module, and is unlikely to be useful elsewhere.

When from_xml_impl encounters an XML element or enum value, it needs to find what protobuf field
that corresponds to. Iterating through the fields of the protobuf message descriptor would work, but
would result in an algorithm that is quadratic in the number of fields (because every field in the
XML requires iterating every field in the protobuf message). This class solves that by precomputing
the XML field names and storing the mapping from that to the FieldDescriptor in a dictionary for
each message. Enum values are also cached by name.
"""

from dataclasses import dataclass
from typing import Dict, Optional

from google.protobuf.descriptor import (
    Descriptor,
    FieldDescriptor,
    EnumDescriptor,
    EnumValueDescriptor,
)

from sapient_apex_server.xml_conversion.naming import (
    get_enum_value_xml_name,
    get_field_xml_name,
)
from sapient_msg import proto_options_pb2


@dataclass
class MessageFieldsMap:
    text_field: Optional[FieldDescriptor]  # Field stored directly in element text
    attribute_fields: Dict[str, FieldDescriptor]
    element_fields: Dict[str, FieldDescriptor]


@dataclass
class DescriptorCache:
    message_fields_map_cache: Dict[Descriptor, MessageFieldsMap]
    enum_values_cache: Dict[EnumDescriptor, Dict[str, int]]

    @staticmethod
    def _get_message_fields_map(desc: Descriptor):
        field_map = MessageFieldsMap(None, {}, {})
        for field_desc in desc.fields:
            field_name = get_field_xml_name(field_desc)
            field_options = field_desc.GetOptions()
            if field_options.Extensions[proto_options_pb2.field_options].xml_is_parent_value:
                if field_map.text_field is not None:
                    raise RuntimeError(f"Multiple parent text fields in {desc.name}")
                if field_desc.type == FieldDescriptor.TYPE_MESSAGE:
                    raise RuntimeError(
                        f"Invalid option 'parent value' for message field: {field_desc.name}"
                    )
                field_map.text_field = field_desc
            elif field_options.Extensions[proto_options_pb2.field_options].xml_is_attribute:
                if (
                    field_desc.type == FieldDescriptor.TYPE_MESSAGE
                    and not field_options.Extensions[proto_options_pb2.field_options].is_proto_time
                ):
                    raise RuntimeError(
                        f"Invalid option 'is attribute' for message field: {field_desc.name}"
                    )
                if field_name in field_map.attribute_fields:
                    raise RuntimeError(f"Attribute name '{field_name}' used for multiple fields")
                field_map.attribute_fields[field_name] = field_desc
            else:
                if field_name in field_map.element_fields:
                    raise RuntimeError(f"Element name '{field_name}' used for multiple fields")
                field_map.element_fields[field_name] = field_desc
        return field_map

    @staticmethod
    def _get_enum_values_map(field_desc: FieldDescriptor):
        enum_desc = field_desc.enum_type
        enum_values_map = {}
        for value_desc in enum_desc.values:
            assert isinstance(value_desc, EnumValueDescriptor)
            value_name = get_enum_value_xml_name(value_desc)
            normalised_value_name = value_name.replace(" ", "").upper()
            if normalised_value_name in enum_values_map:
                raise RuntimeError(
                    f"In enum {enum_desc.name}, ambiguous value {normalised_value_name}"
                )
            enum_values_map[normalised_value_name] = value_desc.number
        return enum_values_map

    def populate(self, desc: Descriptor):
        if desc in self.message_fields_map_cache:
            return

        # Set the fields map for this message
        self.message_fields_map_cache[desc] = DescriptorCache._get_message_fields_map(desc)

        # Set the enum values maps for any enums used by this message
        for field_desc in desc.fields:
            enum_desc = field_desc.enum_type
            if enum_desc is not None and enum_desc not in self.enum_values_cache:
                self.enum_values_cache[enum_desc] = DescriptorCache._get_enum_values_map(field_desc)

        # Set the fields maps for any message types used in fields
        for field_desc in desc.fields:
            if field_desc.type == FieldDescriptor.TYPE_MESSAGE:
                self.populate(field_desc.message_type)
