#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import struct
import xml.etree.ElementTree as ET
from collections.abc import Callable
from typing import Union

from google.protobuf.message import Message

from sapient_apex_server.structures import MessageFormat, MessageRecord, SapientVersion
from sapient_apex_server.translator.bsi_flex_v1_to_xml import (
    translate as bsi_flex_v1_to_xml,
)
from sapient_apex_server.translator.id_generator import IdGenerator
from sapient_apex_server.translator.proto_to_proto_translator import (
    translate_v1_to_v2,
    translate_v2_to_v1,
)
from sapient_msg.bsi_flex_335_v1_0.sapient_message_pb2 import (
    SapientMessage as SapientMessageV1,
)

WriterType = Callable[[Union[Message, ET.Element, MessageRecord], SapientVersion], None]


class ConnectionWriter:
    def __init__(
        self,
        writer: Callable[[bytes], None],
        generator: IdGenerator,
        encoding: MessageFormat = MessageFormat.PROTO,
        version: SapientVersion = SapientVersion.LATEST,
    ):
        self.writer = writer
        self.generator = generator
        self.encoding = encoding
        self.version = version

    def __call__(
        self,
        message: Union[Message, ET.Element, MessageRecord],
        version: SapientVersion = SapientVersion.LATEST,
    ) -> None:
        data = message_to_bytes(
            message,
            self.generator,
            encoding=self.encoding,
            in_version=version,
            out_version=self.version,
        )
        self.writer(data)


def message_to_bytes(
    message: Union[Message, ET.Element, MessageRecord],
    generator: IdGenerator,
    *,
    encoding: MessageFormat = MessageFormat.PROTO,
    in_version: SapientVersion = SapientVersion.LATEST,
    out_version: SapientVersion = SapientVersion.LATEST,
) -> bytes:
    if encoding == MessageFormat.XML and out_version != SapientVersion.VERSION6:
        raise NotImplementedError("XML is only implemented for version 6")
    if isinstance(message, MessageRecord):
        message = pick_message_record_component(message, encoding, out_version)

    # ET.Element is for XMLv6 format only
    assert isinstance(message, (ET.Element, Message))
    if isinstance(message, ET.Element) != (encoding == MessageFormat.XML):
        raise NotImplementedError("XML and ET.Element should be synonymous")
    if (encoding == MessageFormat.XML) != (out_version == SapientVersion.VERSION6):
        raise NotImplementedError("XML is only implemented for version 6")
    if isinstance(message, Message):
        message = to_version(message, in_version, out_version)
    return encode(message, generator, encoding)


def pick_message_record_component(
    message: MessageRecord, encoding: MessageFormat, out_version: SapientVersion
) -> Union[ET.Element, Message]:
    assert message.parsed is not None
    if encoding == MessageFormat.XML:
        if out_version not in (SapientVersion.VERSION6, SapientVersion.BSI_FLEX_335_V1_0):
            # For the most part, XML and VERSION6 are synonymous, except that VERSION6 is not
            # really implemented per se. So converting from anything else is half-backed
            raise RuntimeError(f"No conversion to XML implemented for version {out_version}")
        assert message.parsed.parsed_xml is not None
        return message.parsed.parsed_xml
    # XML + version > VERSION6 provided on a best effort basis
    assert message.parsed.parsed_proto is not None
    return message.parsed.parsed_proto


def to_version(message: Message, version: SapientVersion, final_version: SapientVersion) -> Message:
    """Upgrade or downgrade a message, as required."""
    if version == SapientVersion.VERSION6:
        # VERSION6 is different since it's both a protocol version and an encoding.
        # It predates the current protocol versioning setup
        version = SapientVersion.BSI_FLEX_335_V1_0
    if final_version == SapientVersion.VERSION6:
        final_version = SapientVersion.BSI_FLEX_335_V1_0
    is_upgrade = version.value < final_version.value
    while version != final_version:
        version = SapientVersion(version.value + (1 if is_upgrade else -1))
        message = get_schema_mutater(version, is_upgrade)(message)
    return message


def encode(
    message: Union[Message, ET.Element],
    generator: IdGenerator,
    format: MessageFormat = MessageFormat.DEFAULT,
) -> bytes:
    if isinstance(message, ET.Element):
        return encode_xml(message)
    if format == MessageFormat.XML:
        assert isinstance(message, SapientMessageV1)
        return encode_xml(bsi_flex_v1_to_xml(message, generator))
    elif format == MessageFormat.PROTO:
        return encode_binary(message)
    raise NotImplementedError(f"Format {format.name} has not yet been implemented.")


def encode_xml(message: ET.Element) -> bytes:
    return ET.tostring(message, encoding="utf-8", xml_declaration=True) + b"\0"


def encode_binary(message: Message) -> bytes:
    as_bytes = message.SerializePartialToString()
    return struct.pack("<I", len(as_bytes)) + as_bytes


def change_schema(
    message: Message, version: SapientVersion, final_version: SapientVersion
) -> Message:
    is_upgrade = version.value < final_version.value
    while version != final_version:
        version = SapientVersion(version.value + 1)
        message = get_schema_mutater(version, is_upgrade)(message)
    return message


def get_schema_mutater(version: SapientVersion, is_upgrade: bool) -> Callable[[Message], Message]:
    def oldest_protocol(message: Message) -> Message:
        return message

    def newest_protocol(message: Message) -> Message:
        return message

    def not_implemented(_: Message) -> Message:
        raise NotImplementedError()

    if is_upgrade:
        mutaters = {
            SapientVersion.VERSION6: oldest_protocol,
            SapientVersion.BSI_FLEX_335_V1_0: not_implemented,
            SapientVersion.BSI_FLEX_335_V2_0: translate_v1_to_v2,
        }
    else:
        mutaters = {
            SapientVersion.BSI_FLEX_335_V2_0: newest_protocol,
            SapientVersion.BSI_FLEX_335_V1_0: translate_v2_to_v1,
            SapientVersion.VERSION6: not_implemented,
        }
    return mutaters[version]
