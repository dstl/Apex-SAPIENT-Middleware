#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Some utility functions for getting XML names of messages, fields and values."""

from google.protobuf.descriptor import Descriptor, FieldDescriptor, EnumValueDescriptor

from sapient_msg import proto_options_pb2


def get_message_xml_name(descriptor: Descriptor):
    """Gets XML element name of a message; usually PascalCase."""

    if (
        descriptor.GetOptions().HasExtension(proto_options_pb2.message_options)
        and descriptor.GetOptions().Extensions[proto_options_pb2.message_options].xml_message_name
        != ""
    ):
        return (
            descriptor.GetOptions().Extensions[proto_options_pb2.message_options].xml_message_name
        )
    else:
        return descriptor.name


def get_field_xml_name(field_descriptor: FieldDescriptor):
    """Gets XML element name of a field; usually camelCase."""
    if (
        field_descriptor.GetOptions().HasExtension(proto_options_pb2.field_options)
        and field_descriptor.GetOptions().Extensions[proto_options_pb2.field_options].xml_name != ""
    ):
        return field_descriptor.GetOptions().Extensions[proto_options_pb2.field_options].xml_name
    else:
        return field_descriptor.camelcase_name


def get_enum_value_xml_name(enum_value_desc: EnumValueDescriptor):
    """Gets XML text value for an enum value; usually Title Case.

    It is expected that the programmatic names of enum values include the enum types (mainly for
    compatibility with C++, where classic enum names go directly into the enclosing namespace). For
    example, an enum ItemColor might have values ITEM_COLOR_GREEN and ITEM_COLOR_DARK_BLUE rather
    then just GREEN and DARK_BLUE. This routine strips the prefix out (if it is present) before
    converting to title case."""
    if enum_value_desc.GetOptions().HasExtension(proto_options_pb2.enum_options):
        return enum_value_desc.GetOptions().Extensions[proto_options_pb2.enum_options].enum_name
    else:
        result = enum_value_desc.name
        prefix = _upper_snake_case_from_camel_case(enum_value_desc.type.name) + "_"
        if result.startswith(prefix):
            result = result[len(prefix) :]
        return result.replace("_", " ").title()


def _upper_snake_case_from_camel_case(camel_case_name: str):
    """Converts e.g. "HelloWorld" or "helloWorld" to "HELLO_WORLD"."""
    return camel_case_name[0].upper() + "".join(
        "_" + c if c.isupper() else c.upper() for c in camel_case_name[1:]
    )
