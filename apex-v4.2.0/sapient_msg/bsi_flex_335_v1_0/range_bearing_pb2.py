# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: sapient_msg/bsi_flex_335_v1_0/range_bearing.proto
# Protobuf Python Version: 4.25.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from sapient_msg import proto_options_pb2 as sapient__msg_dot_proto__options__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n1sapient_msg/bsi_flex_335_v1_0/range_bearing.proto\x12\x1dsapient_msg.bsi_flex_335_v1_0\x1a\x1fsapient_msg/proto_options.proto\"\x94\x04\n\x0cRangeBearing\x12!\n\televation\x18\x01 \x01(\x01\x42\t\x8a\xb5\x18\x05\"\x03\x45leH\x00\x88\x01\x01\x12\x1e\n\x07\x61zimuth\x18\x02 \x01(\x01\x42\x08\x8a\xb5\x18\x04\"\x02\x41zH\x01\x88\x01\x01\x12\x1b\n\x05range\x18\x03 \x01(\x01\x42\x07\x8a\xb5\x18\x03\"\x01RH\x02\x88\x01\x01\x12(\n\x0f\x65levation_error\x18\x04 \x01(\x01\x42\n\x8a\xb5\x18\x06\"\x04\x65\x45leH\x03\x88\x01\x01\x12%\n\razimuth_error\x18\x05 \x01(\x01\x42\t\x8a\xb5\x18\x05\"\x03\x65\x41zH\x04\x88\x01\x01\x12\"\n\x0brange_error\x18\x06 \x01(\x01\x42\x08\x8a\xb5\x18\x04\"\x02\x65RH\x05\x88\x01\x01\x12\x65\n\x11\x63oordinate_system\x18\x07 \x01(\x0e\x32;.sapient_msg.bsi_flex_335_v1_0.RangeBearingCoordinateSystemB\x08\x8a\xb5\x18\x04\x08\x01\x30\x01H\x06\x88\x01\x01\x12N\n\x05\x64\x61tum\x18\x08 \x01(\x0e\x32\x30.sapient_msg.bsi_flex_335_v1_0.RangeBearingDatumB\x08\x8a\xb5\x18\x04\x08\x01\x30\x01H\x07\x88\x01\x01\x42\x0c\n\n_elevationB\n\n\x08_azimuthB\x08\n\x06_rangeB\x12\n\x10_elevation_errorB\x10\n\x0e_azimuth_errorB\x0e\n\x0c_range_errorB\x14\n\x12_coordinate_systemB\x08\n\x06_datum\"\xbe\x06\n\x10RangeBearingCone\x12!\n\televation\x18\x01 \x01(\x01\x42\t\x8a\xb5\x18\x05\"\x03\x45leH\x00\x88\x01\x01\x12\x1e\n\x07\x61zimuth\x18\x02 \x01(\x01\x42\x08\x8a\xb5\x18\x04\"\x02\x41zH\x01\x88\x01\x01\x12\x1b\n\x05range\x18\x03 \x01(\x01\x42\x07\x8a\xb5\x18\x03\"\x01RH\x02\x88\x01\x01\x12-\n\x11horizontal_extent\x18\x04 \x01(\x01\x42\r\x8a\xb5\x18\t\"\x07hExtentH\x03\x88\x01\x01\x12+\n\x0fvertical_extent\x18\x05 \x01(\x01\x42\r\x8a\xb5\x18\t\"\x07vExtentH\x04\x88\x01\x01\x12\x34\n\x17horizontal_extent_error\x18\x06 \x01(\x01\x42\x0e\x8a\xb5\x18\n\"\x08\x65hExtentH\x05\x88\x01\x01\x12\x32\n\x15vertical_extent_error\x18\x07 \x01(\x01\x42\x0e\x8a\xb5\x18\n\"\x08\x65vExtentH\x06\x88\x01\x01\x12(\n\x0f\x65levation_error\x18\x08 \x01(\x01\x42\n\x8a\xb5\x18\x06\"\x04\x65\x45leH\x07\x88\x01\x01\x12%\n\razimuth_error\x18\t \x01(\x01\x42\t\x8a\xb5\x18\x05\"\x03\x65\x41zH\x08\x88\x01\x01\x12\"\n\x0brange_error\x18\n \x01(\x01\x42\x08\x8a\xb5\x18\x04\"\x02\x65RH\t\x88\x01\x01\x12\x65\n\x11\x63oordinate_system\x18\x0b \x01(\x0e\x32;.sapient_msg.bsi_flex_335_v1_0.RangeBearingCoordinateSystemB\x08\x8a\xb5\x18\x04\x08\x01\x30\x01H\n\x88\x01\x01\x12N\n\x05\x64\x61tum\x18\x0c \x01(\x0e\x32\x30.sapient_msg.bsi_flex_335_v1_0.RangeBearingDatumB\x08\x8a\xb5\x18\x04\x08\x01\x30\x01H\x0b\x88\x01\x01\x42\x0c\n\n_elevationB\n\n\x08_azimuthB\x08\n\x06_rangeB\x14\n\x12_horizontal_extentB\x12\n\x10_vertical_extentB\x1a\n\x18_horizontal_extent_errorB\x18\n\x16_vertical_extent_errorB\x12\n\x10_elevation_errorB\x10\n\x0e_azimuth_errorB\x0e\n\x0c_range_errorB\x14\n\x12_coordinate_systemB\x08\n\x06_datum*\x89\x03\n\x1cRangeBearingCoordinateSystem\x12/\n+RANGE_BEARING_COORDINATE_SYSTEM_UNSPECIFIED\x10\x00\x12K\n)RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_M\x10\x01\x1a\x1c\x8a\xb5\x18\x18J\x16\x64\x65\x63imal degrees-meters\x12\x43\n)RANGE_BEARING_COORDINATE_SYSTEM_RADIANS_M\x10\x02\x1a\x14\x8a\xb5\x18\x10J\x0eradians-meters\x12P\n*RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_KM\x10\x03\x1a \x8a\xb5\x18\x1cJ\x1a\x64\x65\x63imal degrees-kilometers\x12H\n*RANGE_BEARING_COORDINATE_SYSTEM_RADIANS_KM\x10\x04\x1a\x18\x8a\xb5\x18\x14J\x12radians-kilometers\"\x04\x08\x05\x10\x05\"\x04\x08\x06\x10\x06*\xb8\x01\n\x11RangeBearingDatum\x12#\n\x1fRANGE_BEARING_DATUM_UNSPECIFIED\x10\x00\x12\x1c\n\x18RANGE_BEARING_DATUM_TRUE\x10\x01\x12 \n\x1cRANGE_BEARING_DATUM_MAGNETIC\x10\x02\x12\x1c\n\x18RANGE_BEARING_DATUM_GRID\x10\x03\x12 \n\x1cRANGE_BEARING_DATUM_PLATFORM\x10\x04\x42-\n\x16uk.gov.dstl.sapientmsgB\x11RangeBearingProtoP\x01\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'sapient_msg.bsi_flex_335_v1_0.range_bearing_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  _globals['DESCRIPTOR']._options = None
  _globals['DESCRIPTOR']._serialized_options = b'\n\026uk.gov.dstl.sapientmsgB\021RangeBearingProtoP\001'
  _globals['_RANGEBEARINGCOORDINATESYSTEM'].values_by_name["RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_M"]._options = None
  _globals['_RANGEBEARINGCOORDINATESYSTEM'].values_by_name["RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_M"]._serialized_options = b'\212\265\030\030J\026decimal degrees-meters'
  _globals['_RANGEBEARINGCOORDINATESYSTEM'].values_by_name["RANGE_BEARING_COORDINATE_SYSTEM_RADIANS_M"]._options = None
  _globals['_RANGEBEARINGCOORDINATESYSTEM'].values_by_name["RANGE_BEARING_COORDINATE_SYSTEM_RADIANS_M"]._serialized_options = b'\212\265\030\020J\016radians-meters'
  _globals['_RANGEBEARINGCOORDINATESYSTEM'].values_by_name["RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_KM"]._options = None
  _globals['_RANGEBEARINGCOORDINATESYSTEM'].values_by_name["RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_KM"]._serialized_options = b'\212\265\030\034J\032decimal degrees-kilometers'
  _globals['_RANGEBEARINGCOORDINATESYSTEM'].values_by_name["RANGE_BEARING_COORDINATE_SYSTEM_RADIANS_KM"]._options = None
  _globals['_RANGEBEARINGCOORDINATESYSTEM'].values_by_name["RANGE_BEARING_COORDINATE_SYSTEM_RADIANS_KM"]._serialized_options = b'\212\265\030\024J\022radians-kilometers'
  _globals['_RANGEBEARING'].fields_by_name['elevation']._options = None
  _globals['_RANGEBEARING'].fields_by_name['elevation']._serialized_options = b'\212\265\030\005\"\003Ele'
  _globals['_RANGEBEARING'].fields_by_name['azimuth']._options = None
  _globals['_RANGEBEARING'].fields_by_name['azimuth']._serialized_options = b'\212\265\030\004\"\002Az'
  _globals['_RANGEBEARING'].fields_by_name['range']._options = None
  _globals['_RANGEBEARING'].fields_by_name['range']._serialized_options = b'\212\265\030\003\"\001R'
  _globals['_RANGEBEARING'].fields_by_name['elevation_error']._options = None
  _globals['_RANGEBEARING'].fields_by_name['elevation_error']._serialized_options = b'\212\265\030\006\"\004eEle'
  _globals['_RANGEBEARING'].fields_by_name['azimuth_error']._options = None
  _globals['_RANGEBEARING'].fields_by_name['azimuth_error']._serialized_options = b'\212\265\030\005\"\003eAz'
  _globals['_RANGEBEARING'].fields_by_name['range_error']._options = None
  _globals['_RANGEBEARING'].fields_by_name['range_error']._serialized_options = b'\212\265\030\004\"\002eR'
  _globals['_RANGEBEARING'].fields_by_name['coordinate_system']._options = None
  _globals['_RANGEBEARING'].fields_by_name['coordinate_system']._serialized_options = b'\212\265\030\004\010\0010\001'
  _globals['_RANGEBEARING'].fields_by_name['datum']._options = None
  _globals['_RANGEBEARING'].fields_by_name['datum']._serialized_options = b'\212\265\030\004\010\0010\001'
  _globals['_RANGEBEARINGCONE'].fields_by_name['elevation']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['elevation']._serialized_options = b'\212\265\030\005\"\003Ele'
  _globals['_RANGEBEARINGCONE'].fields_by_name['azimuth']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['azimuth']._serialized_options = b'\212\265\030\004\"\002Az'
  _globals['_RANGEBEARINGCONE'].fields_by_name['range']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['range']._serialized_options = b'\212\265\030\003\"\001R'
  _globals['_RANGEBEARINGCONE'].fields_by_name['horizontal_extent']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['horizontal_extent']._serialized_options = b'\212\265\030\t\"\007hExtent'
  _globals['_RANGEBEARINGCONE'].fields_by_name['vertical_extent']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['vertical_extent']._serialized_options = b'\212\265\030\t\"\007vExtent'
  _globals['_RANGEBEARINGCONE'].fields_by_name['horizontal_extent_error']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['horizontal_extent_error']._serialized_options = b'\212\265\030\n\"\010ehExtent'
  _globals['_RANGEBEARINGCONE'].fields_by_name['vertical_extent_error']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['vertical_extent_error']._serialized_options = b'\212\265\030\n\"\010evExtent'
  _globals['_RANGEBEARINGCONE'].fields_by_name['elevation_error']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['elevation_error']._serialized_options = b'\212\265\030\006\"\004eEle'
  _globals['_RANGEBEARINGCONE'].fields_by_name['azimuth_error']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['azimuth_error']._serialized_options = b'\212\265\030\005\"\003eAz'
  _globals['_RANGEBEARINGCONE'].fields_by_name['range_error']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['range_error']._serialized_options = b'\212\265\030\004\"\002eR'
  _globals['_RANGEBEARINGCONE'].fields_by_name['coordinate_system']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['coordinate_system']._serialized_options = b'\212\265\030\004\010\0010\001'
  _globals['_RANGEBEARINGCONE'].fields_by_name['datum']._options = None
  _globals['_RANGEBEARINGCONE'].fields_by_name['datum']._serialized_options = b'\212\265\030\004\010\0010\001'
  _globals['_RANGEBEARINGCOORDINATESYSTEM']._serialized_start=1486
  _globals['_RANGEBEARINGCOORDINATESYSTEM']._serialized_end=1879
  _globals['_RANGEBEARINGDATUM']._serialized_start=1882
  _globals['_RANGEBEARINGDATUM']._serialized_end=2066
  _globals['_RANGEBEARING']._serialized_start=118
  _globals['_RANGEBEARING']._serialized_end=650
  _globals['_RANGEBEARINGCONE']._serialized_start=653
  _globals['_RANGEBEARINGCONE']._serialized_end=1483
# @@protoc_insertion_point(module_scope)
