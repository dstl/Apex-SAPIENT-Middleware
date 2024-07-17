from google.protobuf import timestamp_pb2 as _timestamp_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SapientMessageTest(_message.Message):
    __slots__ = ("timestamp", "node_id", "destination_id", "registration", "registration_ack", "status_report", "detection_report", "task", "task_ack", "alert", "alert_ack", "error")
    TIMESTAMP_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    DESTINATION_ID_FIELD_NUMBER: _ClassVar[int]
    REGISTRATION_FIELD_NUMBER: _ClassVar[int]
    REGISTRATION_ACK_FIELD_NUMBER: _ClassVar[int]
    STATUS_REPORT_FIELD_NUMBER: _ClassVar[int]
    DETECTION_REPORT_FIELD_NUMBER: _ClassVar[int]
    TASK_FIELD_NUMBER: _ClassVar[int]
    TASK_ACK_FIELD_NUMBER: _ClassVar[int]
    ALERT_FIELD_NUMBER: _ClassVar[int]
    ALERT_ACK_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    timestamp: _timestamp_pb2.Timestamp
    node_id: str
    destination_id: str
    registration: Registration
    registration_ack: RegistrationAckTest
    status_report: StatusReport
    detection_report: DetectionReport
    task: Task
    task_ack: TaskAck
    alert: Alert
    alert_ack: AlertAckTest
    error: Error
    def __init__(self, timestamp: _Optional[_Union[_timestamp_pb2.Timestamp, _Mapping]] = ..., node_id: _Optional[str] = ..., destination_id: _Optional[str] = ..., registration: _Optional[_Union[Registration, _Mapping]] = ..., registration_ack: _Optional[_Union[RegistrationAckTest, _Mapping]] = ..., status_report: _Optional[_Union[StatusReport, _Mapping]] = ..., detection_report: _Optional[_Union[DetectionReport, _Mapping]] = ..., task: _Optional[_Union[Task, _Mapping]] = ..., task_ack: _Optional[_Union[TaskAck, _Mapping]] = ..., alert: _Optional[_Union[Alert, _Mapping]] = ..., alert_ack: _Optional[_Union[AlertAckTest, _Mapping]] = ..., error: _Optional[_Union[Error, _Mapping]] = ...) -> None: ...

class Registration(_message.Message):
    __slots__ = ("dummy",)
    DUMMY_FIELD_NUMBER: _ClassVar[int]
    dummy: bool
    def __init__(self, dummy: bool = ...) -> None: ...

class RegistrationAckTest(_message.Message):
    __slots__ = ("acceptance", "ack_response_reason", "new_field_example")
    ACCEPTANCE_FIELD_NUMBER: _ClassVar[int]
    ACK_RESPONSE_REASON_FIELD_NUMBER: _ClassVar[int]
    NEW_FIELD_EXAMPLE_FIELD_NUMBER: _ClassVar[int]
    acceptance: bool
    ack_response_reason: _containers.RepeatedScalarFieldContainer[str]
    new_field_example: str
    def __init__(self, acceptance: bool = ..., ack_response_reason: _Optional[_Iterable[str]] = ..., new_field_example: _Optional[str] = ...) -> None: ...

class StatusReport(_message.Message):
    __slots__ = ("dummy",)
    DUMMY_FIELD_NUMBER: _ClassVar[int]
    dummy: bool
    def __init__(self, dummy: bool = ...) -> None: ...

class DetectionReport(_message.Message):
    __slots__ = ("dummy",)
    DUMMY_FIELD_NUMBER: _ClassVar[int]
    dummy: bool
    def __init__(self, dummy: bool = ...) -> None: ...

class Task(_message.Message):
    __slots__ = ("dummy",)
    DUMMY_FIELD_NUMBER: _ClassVar[int]
    dummy: bool
    def __init__(self, dummy: bool = ...) -> None: ...

class TaskAck(_message.Message):
    __slots__ = ("dummy",)
    DUMMY_FIELD_NUMBER: _ClassVar[int]
    dummy: bool
    def __init__(self, dummy: bool = ...) -> None: ...

class Alert(_message.Message):
    __slots__ = ("dummy",)
    DUMMY_FIELD_NUMBER: _ClassVar[int]
    dummy: bool
    def __init__(self, dummy: bool = ...) -> None: ...

class AlertAckTest(_message.Message):
    __slots__ = ("alert_id", "reason", "alert_ack_status")
    class AlertAckStatusTest(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        ALERT_ACK_STATUS_UNSPECIFIED: _ClassVar[AlertAckTest.AlertAckStatusTest]
        ALERT_ACK_STATUS_ACCEPTED: _ClassVar[AlertAckTest.AlertAckStatusTest]
        ALERT_ACK_STATUS_REJECTED: _ClassVar[AlertAckTest.AlertAckStatusTest]
        ALERT_ACK_STATUS_CANCELLED: _ClassVar[AlertAckTest.AlertAckStatusTest]
        UNKNOWN_ENUM: _ClassVar[AlertAckTest.AlertAckStatusTest]
    ALERT_ACK_STATUS_UNSPECIFIED: AlertAckTest.AlertAckStatusTest
    ALERT_ACK_STATUS_ACCEPTED: AlertAckTest.AlertAckStatusTest
    ALERT_ACK_STATUS_REJECTED: AlertAckTest.AlertAckStatusTest
    ALERT_ACK_STATUS_CANCELLED: AlertAckTest.AlertAckStatusTest
    UNKNOWN_ENUM: AlertAckTest.AlertAckStatusTest
    ALERT_ID_FIELD_NUMBER: _ClassVar[int]
    REASON_FIELD_NUMBER: _ClassVar[int]
    ALERT_ACK_STATUS_FIELD_NUMBER: _ClassVar[int]
    alert_id: str
    reason: _containers.RepeatedScalarFieldContainer[str]
    alert_ack_status: AlertAckTest.AlertAckStatusTest
    def __init__(self, alert_id: _Optional[str] = ..., reason: _Optional[_Iterable[str]] = ..., alert_ack_status: _Optional[_Union[AlertAckTest.AlertAckStatusTest, str]] = ...) -> None: ...

class Error(_message.Message):
    __slots__ = ("dummy",)
    DUMMY_FIELD_NUMBER: _ClassVar[int]
    dummy: bool
    def __init__(self, dummy: bool = ...) -> None: ...
