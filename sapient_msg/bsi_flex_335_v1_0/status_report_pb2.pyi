from sapient_msg.bsi_flex_335_v1_0 import location_pb2 as _location_pb2
from sapient_msg.bsi_flex_335_v1_0 import range_bearing_pb2 as _range_bearing_pb2
from sapient_msg import proto_options_pb2 as _proto_options_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class StatusReport(_message.Message):
    __slots__ = ("report_id", "system", "info", "active_task_id", "mode", "power", "node_location", "field_of_view", "coverage", "obscuration", "status")
    class System(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        SYSTEM_UNSPECIFIED: _ClassVar[StatusReport.System]
        SYSTEM_OK: _ClassVar[StatusReport.System]
        SYSTEM_WARNING: _ClassVar[StatusReport.System]
        SYSTEM_ERROR: _ClassVar[StatusReport.System]
        SYSTEM_GOODBYE: _ClassVar[StatusReport.System]
    SYSTEM_UNSPECIFIED: StatusReport.System
    SYSTEM_OK: StatusReport.System
    SYSTEM_WARNING: StatusReport.System
    SYSTEM_ERROR: StatusReport.System
    SYSTEM_GOODBYE: StatusReport.System
    class Info(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        INFO_UNSPECIFIED: _ClassVar[StatusReport.Info]
        INFO_NEW: _ClassVar[StatusReport.Info]
        INFO_UNCHANGED: _ClassVar[StatusReport.Info]
    INFO_UNSPECIFIED: StatusReport.Info
    INFO_NEW: StatusReport.Info
    INFO_UNCHANGED: StatusReport.Info
    class StatusLevel(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
        __slots__ = ()
        STATUS_LEVEL_UNSPECIFIED: _ClassVar[StatusReport.StatusLevel]
        STATUS_LEVEL_SENSOR_STATUS: _ClassVar[StatusReport.StatusLevel]
        STATUS_LEVEL_INFORMATION_STATUS: _ClassVar[StatusReport.StatusLevel]
        STATUS_LEVEL_WARNING_STATUS: _ClassVar[StatusReport.StatusLevel]
        STATUS_LEVEL_ERROR_STATUS: _ClassVar[StatusReport.StatusLevel]
    STATUS_LEVEL_UNSPECIFIED: StatusReport.StatusLevel
    STATUS_LEVEL_SENSOR_STATUS: StatusReport.StatusLevel
    STATUS_LEVEL_INFORMATION_STATUS: StatusReport.StatusLevel
    STATUS_LEVEL_WARNING_STATUS: StatusReport.StatusLevel
    STATUS_LEVEL_ERROR_STATUS: StatusReport.StatusLevel
    class Power(_message.Message):
        __slots__ = ("source", "status", "level")
        SOURCE_FIELD_NUMBER: _ClassVar[int]
        STATUS_FIELD_NUMBER: _ClassVar[int]
        LEVEL_FIELD_NUMBER: _ClassVar[int]
        source: str
        status: str
        level: int
        def __init__(self, source: _Optional[str] = ..., status: _Optional[str] = ..., level: _Optional[int] = ...) -> None: ...
    class LocationOrRangeBearing(_message.Message):
        __slots__ = ("range_bearing", "location_list")
        RANGE_BEARING_FIELD_NUMBER: _ClassVar[int]
        LOCATION_LIST_FIELD_NUMBER: _ClassVar[int]
        range_bearing: _range_bearing_pb2.RangeBearingCone
        location_list: _location_pb2.LocationList
        def __init__(self, range_bearing: _Optional[_Union[_range_bearing_pb2.RangeBearingCone, _Mapping]] = ..., location_list: _Optional[_Union[_location_pb2.LocationList, _Mapping]] = ...) -> None: ...
    class Status(_message.Message):
        __slots__ = ("status_level", "status_type", "status_value")
        STATUS_LEVEL_FIELD_NUMBER: _ClassVar[int]
        STATUS_TYPE_FIELD_NUMBER: _ClassVar[int]
        STATUS_VALUE_FIELD_NUMBER: _ClassVar[int]
        status_level: StatusReport.StatusLevel
        status_type: str
        status_value: str
        def __init__(self, status_level: _Optional[_Union[StatusReport.StatusLevel, str]] = ..., status_type: _Optional[str] = ..., status_value: _Optional[str] = ...) -> None: ...
    REPORT_ID_FIELD_NUMBER: _ClassVar[int]
    SYSTEM_FIELD_NUMBER: _ClassVar[int]
    INFO_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_TASK_ID_FIELD_NUMBER: _ClassVar[int]
    MODE_FIELD_NUMBER: _ClassVar[int]
    POWER_FIELD_NUMBER: _ClassVar[int]
    NODE_LOCATION_FIELD_NUMBER: _ClassVar[int]
    FIELD_OF_VIEW_FIELD_NUMBER: _ClassVar[int]
    COVERAGE_FIELD_NUMBER: _ClassVar[int]
    OBSCURATION_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    report_id: str
    system: StatusReport.System
    info: StatusReport.Info
    active_task_id: str
    mode: str
    power: StatusReport.Power
    node_location: _location_pb2.Location
    field_of_view: StatusReport.LocationOrRangeBearing
    coverage: StatusReport.LocationOrRangeBearing
    obscuration: _containers.RepeatedCompositeFieldContainer[StatusReport.LocationOrRangeBearing]
    status: _containers.RepeatedCompositeFieldContainer[StatusReport.Status]
    def __init__(self, report_id: _Optional[str] = ..., system: _Optional[_Union[StatusReport.System, str]] = ..., info: _Optional[_Union[StatusReport.Info, str]] = ..., active_task_id: _Optional[str] = ..., mode: _Optional[str] = ..., power: _Optional[_Union[StatusReport.Power, _Mapping]] = ..., node_location: _Optional[_Union[_location_pb2.Location, _Mapping]] = ..., field_of_view: _Optional[_Union[StatusReport.LocationOrRangeBearing, _Mapping]] = ..., coverage: _Optional[_Union[StatusReport.LocationOrRangeBearing, _Mapping]] = ..., obscuration: _Optional[_Iterable[_Union[StatusReport.LocationOrRangeBearing, _Mapping]]] = ..., status: _Optional[_Iterable[_Union[StatusReport.Status, _Mapping]]] = ...) -> None: ...
