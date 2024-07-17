from sapient_msg import proto_options_pb2 as _proto_options_pb2
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class AlertAck(_message.Message):
    __slots__ = ("alert_id", "alert_status", "reason")
    class AlertStatus(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ALERT_STATUS_UNSPECIFIED: _ClassVar[AlertAck.AlertStatus]
        ALERT_STATUS_ACCEPTED: _ClassVar[AlertAck.AlertStatus]
        ALERT_STATUS_REJECTED: _ClassVar[AlertAck.AlertStatus]
        ALERT_STATUS_CANCELLED: _ClassVar[AlertAck.AlertStatus]
    ALERT_STATUS_UNSPECIFIED: AlertAck.AlertStatus
    ALERT_STATUS_ACCEPTED: AlertAck.AlertStatus
    ALERT_STATUS_REJECTED: AlertAck.AlertStatus
    ALERT_STATUS_CANCELLED: AlertAck.AlertStatus
    ALERT_ID_FIELD_NUMBER: _ClassVar[int]
    ALERT_STATUS_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    alert_id: str
    alert_status: AlertAck.AlertStatus
    reason: str
    def __init__(self, alert_id: _Optional[str] = ..., alert_status: _Optional[_Union[AlertAck.AlertStatus, str]] = ..., reason: _Optional[str] = ...) -> None: ...
