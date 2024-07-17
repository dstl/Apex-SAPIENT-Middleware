#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from __future__ import annotations, with_statement

from enum import Enum
from typing import ClassVar, Iterable, List, Type, TypeVar

from pydantic import BaseModel, Field, field_validator

from sapient_msg.latest import location_pb2, range_bearing_pb2, registration_pb2

T = TypeVar("T")


def _create_enum_by_name_or_index(enum_cls: Type[T], value: int | str | T) -> T | str:
    if isinstance(value, enum_cls):
        return value
    assert isinstance(enum_cls, Iterable)
    if isinstance(value, int):
        return list(enum_cls)[value]
    assert isinstance(value, str)
    try:
        return enum_cls[value]
    except ValueError:
        pass
    return value


# Pydantic representation of sapient_msg protos are
# done using using protobuf2pydantic, which uses
# the already generated *pb2.py files as the inputs.
# Usage Example:
# `pb2py sapient_msg\location_pb2.py > temp_file.py`
# and Extract interesting parts/generated class(es)


# Note on protobuf2pydantic, this also installs
# typer, which causes pytests to fail
# See https://github.com/tiangolo/typer/issues/413
# So install it temporarily to generate the pydantic
# parts, but do not include in poetry/requirements.txt


class Location(BaseModel):
    LocationCoordinateSystem: ClassVar[Type] = Enum(
        "LocationCoordinateSystem", [(a, a) for a in location_pb2.LocationCoordinateSystem.keys()]
    )
    LocationDatum: ClassVar[Type] = Enum(
        "LocationDatum", [(a, a) for a in location_pb2.LocationDatum.keys()]
    )
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    x_error: float = 0.0
    y_error: float = 0.0
    z_error: float = 0.0

    coordinate_system: Location.LocationCoordinateSystem = (
        LocationCoordinateSystem.LOCATION_COORDINATE_SYSTEM_UNSPECIFIED
    )
    datum: Location.LocationDatum = LocationDatum.LOCATION_DATUM_UNSPECIFIED
    utm_zone: str = ""

    @field_validator("coordinate_system", mode="before")
    @staticmethod
    def _enum_validator_coordinate_system(value):
        return _create_enum_by_name_or_index(Location.LocationCoordinateSystem, value)

    @field_validator("datum", mode="before")
    @staticmethod
    def _enum_validator_datum(value):
        return _create_enum_by_name_or_index(Location.LocationDatum, value)


class LocationList(BaseModel):
    locations: List[Location] = Field(default_factory=list)


class RangeBearingCone(BaseModel):
    RangeBearingCoordinateSystem: ClassVar[Type] = Enum(
        "RangeBearingCoordinateSystem",
        [(a, a) for a in range_bearing_pb2.RangeBearingCoordinateSystem.keys()],
    )
    RangeBearingDatum: ClassVar[Type] = Enum(
        "RangeBearingDatum", [(a, a) for a in range_bearing_pb2.RangeBearingDatum.keys()]
    )

    elevation: float = 0.0
    azimuth: float = 0.0
    range: float = 0.0
    horizontal_extent: float = 0.0
    vertical_extent: float = 0.0
    horizontal_extent_error: float = 0.0
    vertical_extent_error: float = 0.0
    elevation_error: float = 0.0
    azimuth_error: float = 0.0
    range_error: float = 0.0
    coordinate_system: RangeBearingCone.RangeBearingCoordinateSystem = (
        RangeBearingCoordinateSystem.RANGE_BEARING_COORDINATE_SYSTEM_UNSPECIFIED
    )
    datum: RangeBearingCone.RangeBearingDatum = RangeBearingDatum.RANGE_BEARING_DATUM_UNSPECIFIED

    @field_validator("coordinate_system", mode="before")
    @staticmethod
    def _enum_validator_coordinate_system(value):
        return _create_enum_by_name_or_index(RangeBearingCone.RangeBearingCoordinateSystem, value)

    @field_validator("datum", mode="before")
    @staticmethod
    def _enum_validator_datum(value):
        return _create_enum_by_name_or_index(RangeBearingCone.RangeBearingDatum, value)


class LocationOrRangeBearing(BaseModel):
    location_list: LocationList = Field(default_factory=LocationList)
    range_bearing: RangeBearingCone = Field(default_factory=RangeBearingCone)


class NodeDefinition(BaseModel):
    NodeType: ClassVar[Type] = Enum(
        "NodeType", [(a, a) for a in registration_pb2.Registration.NodeType.keys()]
    )

    node_type: NodeDefinition.NodeType = NodeType.NODE_TYPE_UNSPECIFIED
    node_sub_type: List[str] = Field(default_factory=list)

    @field_validator("node_type", mode="before")
    @staticmethod
    def _enum_validator(value):
        return _create_enum_by_name_or_index(NodeDefinition.NodeType, value)


def setattr_all(obj: object, attrs: dict) -> object:
    """Recursively converts the supplied dictionary to a
    (BaseModel derived) class object. Its implied that both have the
    same structure and have been created using the same schema.

    Args:
        obj (Any): object, derived from BaseModel
        attrs (dict): dictionary with the same class members
    """

    # Delete all existing attributes in the target object as
    # we want to only use the attributes which are in the source
    existing_attrs = list(obj.__dict__.keys())
    for existing_attr in existing_attrs:
        if existing_attr not in attrs:
            delattr(obj, existing_attr)

    for key, value in attrs.items():
        current_attr = None
        if hasattr(obj, key):
            current_attr = getattr(obj, key)

        if current_attr and isinstance(current_attr, object) and isinstance(value, dict):
            # When dealing with nested/sub-objects, attempt to recursively
            # set the attributes. While setattr appears to work for these too,
            # it generates a warning from pydantic for serialisation.
            setattr_all(obj=current_attr, attrs=value)
        else:
            setattr(obj, key, value)
