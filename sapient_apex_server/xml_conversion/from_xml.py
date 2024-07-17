#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Converts from XML to protobuf.

It is perfectly possible to use the routines in from_xml_impl and from_xml_descriptor_cache
directly, but the Converter class in this module combine those in the typical usage. It would be
used like so:

    from_xml_converter = from_xml.Converter(AnyMessage)
    # ... later ...
    msg, errors = from_xml_converter.from_string(xml)

Note that the relevant proto class (not an instance) is passed to the constructor of the Converter.
Instances of Converter should be reused as much as possible to avoid it rebuilding its internal
descriptor cache. The from_elem() method can be used instead of from_string if the xml has already
been parsed into an ET.Element instance.

The above usage assumes that the message type passed in has one field for each possible type of
message that could be received. The root element name is compared against the message names of these
fields to determine which should be set. If there is only one type of message that can be received
then pass nested_field=False to the constructor. In that case, the name of the root element is
ignored.
"""

from typing import ByteString, List, Tuple, Union
import xml.etree.ElementTree as ET

from google.protobuf.message import Message
from sapient_apex_server.translator.id_generator import IdGenerator

from sapient_apex_server.xml_conversion.from_xml_descriptor_cache import DescriptorCache
from sapient_apex_server.xml_conversion.from_xml_impl import (
    populate_message,
    populate_message_field,
)
from sapient_msg import proto_options_pb2


class Converter:
    def __init__(self, message_class: type, nested_field: bool = True):
        assert issubclass(message_class, Message)
        self.message_class = message_class
        self.descriptor_cache = DescriptorCache({}, {})
        self.descriptor_cache.populate(message_class.DESCRIPTOR)
        self.nested_field = nested_field

    def from_elem(
        self, elem: ET.Element, generator: IdGenerator, node_id: str
    ) -> Tuple[Message, List[str]]:
        result = self.message_class()
        errors = []
        is_sapient_message = (
            self.message_class.DESCRIPTOR.GetOptions()
            .Extensions[proto_options_pb2.message_options]
            .is_sapient_message
        )
        if self.nested_field:
            populate_message_field(
                self.descriptor_cache,
                result,
                elem,
                errors,
                generator,
                is_sapient_message,
                node_id,
            )
        else:
            populate_message(
                self.descriptor_cache,
                result,
                elem,
                errors,
                generator,
                is_sapient_message,
                node_id,
            )
        return result, errors

    def from_string(
        self, xml: Union[str, ByteString], generator: IdGenerator, node_id: str
    ) -> Tuple[Message, List[str]]:
        try:
            elem = ET.fromstring(xml)
        except Exception as e:
            return self.message_class(), [f"Parsing XML failed: {e}"]
        return self.from_elem(elem, generator, node_id)
