# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: tests/testing_proto.proto
# Protobuf Python Version: 4.25.0
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import timestamp_pb2 as google_dot_protobuf_dot_timestamp__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x19tests/testing_proto.proto\x12\x10sapient_msg_test\x1a\x1fgoogle/protobuf/timestamp.proto\"\xe2\x04\n\x12SapientMessageTest\x12-\n\ttimestamp\x18\x01 \x01(\x0b\x32\x1a.google.protobuf.Timestamp\x12\x0f\n\x07node_id\x18\x02 \x01(\t\x12\x1b\n\x0e\x64\x65stination_id\x18\x03 \x01(\tH\x01\x88\x01\x01\x12\x36\n\x0cregistration\x18\x04 \x01(\x0b\x32\x1e.sapient_msg_test.RegistrationH\x00\x12\x41\n\x10registration_ack\x18\x05 \x01(\x0b\x32%.sapient_msg_test.RegistrationAckTestH\x00\x12\x37\n\rstatus_report\x18\x06 \x01(\x0b\x32\x1e.sapient_msg_test.StatusReportH\x00\x12=\n\x10\x64\x65tection_report\x18\x07 \x01(\x0b\x32!.sapient_msg_test.DetectionReportH\x00\x12&\n\x04task\x18\x08 \x01(\x0b\x32\x16.sapient_msg_test.TaskH\x00\x12-\n\x08task_ack\x18\t \x01(\x0b\x32\x19.sapient_msg_test.TaskAckH\x00\x12(\n\x05\x61lert\x18\n \x01(\x0b\x32\x17.sapient_msg_test.AlertH\x00\x12\x33\n\talert_ack\x18\x0b \x01(\x0b\x32\x1e.sapient_msg_test.AlertAckTestH\x00\x12(\n\x05\x65rror\x18\x0c \x01(\x0b\x32\x17.sapient_msg_test.ErrorH\x00\x42\t\n\x07\x63ontentB\x11\n\x0f_destination_id\"\x1d\n\x0cRegistration\x12\r\n\x05\x64ummy\x18\x01 \x01(\x08\"g\n\x13RegistrationAckTest\x12\x12\n\nacceptance\x18\x01 \x01(\x08\x12\x1b\n\x13\x61\x63k_response_reason\x18\x03 \x03(\t\x12\x19\n\x11new_field_example\x18\x04 \x01(\tJ\x04\x08\x02\x10\x03\"\x1d\n\x0cStatusReport\x12\r\n\x05\x64ummy\x18\x01 \x01(\x08\" \n\x0f\x44\x65tectionReport\x12\r\n\x05\x64ummy\x18\x01 \x01(\x08\"\x15\n\x04Task\x12\r\n\x05\x64ummy\x18\x01 \x01(\x08\"$\n\x07TaskAck\x12\r\n\x05\x64ummy\x18\x01 \x01(\x08J\x04\x08\x02\x10\x03J\x04\x08\x03\x10\x04\"\x16\n\x05\x41lert\x12\r\n\x05\x64ummy\x18\x01 \x01(\x08\"\xcc\x02\n\x0c\x41lertAckTest\x12\x10\n\x08\x61lert_id\x18\x01 \x01(\t\x12\x0e\n\x06reason\x18\x04 \x03(\t\x12P\n\x10\x61lert_ack_status\x18\x05 \x01(\x0e\x32\x31.sapient_msg_test.AlertAckTest.AlertAckStatusTestH\x00\x88\x01\x01\"\xa6\x01\n\x12\x41lertAckStatusTest\x12 \n\x1c\x41LERT_ACK_STATUS_UNSPECIFIED\x10\x00\x12\x1d\n\x19\x41LERT_ACK_STATUS_ACCEPTED\x10\x01\x12\x1d\n\x19\x41LERT_ACK_STATUS_REJECTED\x10\x02\x12\x1e\n\x1a\x41LERT_ACK_STATUS_CANCELLED\x10\x03\x12\x10\n\x0cUNKNOWN_ENUM\x10\x04\x42\x13\n\x11_alert_ack_statusJ\x04\x08\x02\x10\x03J\x04\x08\x03\x10\x04\"\x16\n\x05\x45rror\x12\r\n\x05\x64ummy\x18\x01 \x01(\x08\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'tests.testing_proto_pb2', _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
  DESCRIPTOR._options = None
  _globals['_SAPIENTMESSAGETEST']._serialized_start=81
  _globals['_SAPIENTMESSAGETEST']._serialized_end=691
  _globals['_REGISTRATION']._serialized_start=693
  _globals['_REGISTRATION']._serialized_end=722
  _globals['_REGISTRATIONACKTEST']._serialized_start=724
  _globals['_REGISTRATIONACKTEST']._serialized_end=827
  _globals['_STATUSREPORT']._serialized_start=829
  _globals['_STATUSREPORT']._serialized_end=858
  _globals['_DETECTIONREPORT']._serialized_start=860
  _globals['_DETECTIONREPORT']._serialized_end=892
  _globals['_TASK']._serialized_start=894
  _globals['_TASK']._serialized_end=915
  _globals['_TASKACK']._serialized_start=917
  _globals['_TASKACK']._serialized_end=953
  _globals['_ALERT']._serialized_start=955
  _globals['_ALERT']._serialized_end=977
  _globals['_ALERTACKTEST']._serialized_start=980
  _globals['_ALERTACKTEST']._serialized_end=1312
  _globals['_ALERTACKTEST_ALERTACKSTATUSTEST']._serialized_start=1113
  _globals['_ALERTACKTEST_ALERTACKSTATUSTEST']._serialized_end=1279
  _globals['_ERROR']._serialized_start=1314
  _globals['_ERROR']._serialized_end=1336
# @@protoc_insertion_point(module_scope)
