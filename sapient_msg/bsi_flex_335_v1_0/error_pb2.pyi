from sapient_msg import proto_options_pb2 as _proto_options_pb2
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional

DESCRIPTOR: _descriptor.FileDescriptor

class Error(_message.Message):
    __slots__ = ("packet", "error_message")
    PACKET_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    packet: bytes
    error_message: str
    def __init__(self, packet: _Optional[bytes] = ..., error_message: _Optional[str] = ...) -> None: ...
