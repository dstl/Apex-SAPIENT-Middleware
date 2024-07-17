#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

# Unit tests to verify Apex can successfully serialize proto messages and parse back into JSON
import functools
import json
import os
import sys
import uuid
from datetime import datetime
from unittest import TestCase, main

import ulid
from google.protobuf.json_format import ParseDict

from sapient_apex_server.parse_proto import parse_proto
from sapient_apex_server.translator.id_generator import IdGenerator
from tests.msg_templates import (
    get_alert_ack_message_template,
    get_alert_message_template,
    get_detection_message_template,
    get_error_message_template,
    get_register_ack_message_template,
    get_register_template,
    get_status_message_template,
    get_task_ack_message_template,
    get_task_message_template,
)

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.append(ROOT_DIR)

from sapient_apex_server.structures import ReceivedDataRecord
from sapient_apex_server.validate_proto import ValidationOptions, Validator
from sapient_msg.latest.sapient_message_pb2 import SapientMessage

parse_proto_partial = functools.partial(parse_proto, enable_message_conversion=False)


def parse_message(msg_bytes, id_generator: IdGenerator):
    raw_message = ReceivedDataRecord(
        connection_id=1,
        message_id=1,
        timestamp=datetime.utcnow(),
        data_bytes=msg_bytes,
    )

    validation_options = ValidationOptions.from_config_dict(
        {
            "validationOptions": {
                "validationTypes": [
                    "mandatory_fields_present",
                    "mandatory_oneof_present",
                    "mandatory_repeated_present",
                    "no_unknown_fields",
                    "no_unknown_enum_values",
                    "id_format_valid",
                    "message_timestamp_reasonable",
                    "detection_timestamp_reasonable",
                ],
                "strictIdFormat": True,
                "messageTimestampRange": [-0.9, 0.1],
                "detectionMinimumGap": 0.08,
            },
        }
    )
    return parse_proto_partial(raw_message, Validator(validation_options), id_generator)


class MsgParsingTestCase(TestCase):
    def setUp(self):
        self.id_generator = IdGenerator({})
        self.node_id = str(uuid.uuid4())

    def add_node_id_to_map(self):
        self.id_generator.insert_new_ulid_id_pair(
            self.node_id, 1, self.id_generator.node_id_map, True
        )

    def test_registration_msg(self):
        msg = get_register_template(node_id=self.node_id)
        msg_bytes = ParseDict(msg, SapientMessage()).SerializeToString()

        msg_parsed = parse_message(msg_bytes, self.id_generator)
        msg_parsed_dict = json.loads(msg_parsed.data_json)
        self.assertDictEqual(msg_parsed_dict, msg)

    def test_registration_ack_msg(self):
        self.add_node_id_to_map()
        msg = get_register_ack_message_template(node_id=self.node_id)
        msg_bytes = ParseDict(msg, SapientMessage()).SerializeToString()

        msg_parsed = parse_message(msg_bytes, self.id_generator)
        msg_parsed_dict = json.loads(msg_parsed.data_json)
        self.assertDictEqual(msg_parsed_dict, msg)

    def test_status_msg(self):
        self.add_node_id_to_map()
        msg = get_status_message_template(node_id=self.node_id, report_id=ulid.new().str)
        msg_bytes = ParseDict(msg, SapientMessage()).SerializeToString()

        msg_parsed = parse_message(msg_bytes, self.id_generator)
        msg_parsed_dict = json.loads(msg_parsed.data_json)
        self.assertDictEqual(msg_parsed_dict, msg)

    def test_detection_msg(self):
        self.add_node_id_to_map()
        msg = get_detection_message_template(
            node_id=self.node_id,
            report_id=ulid.new().str,
            object_id=ulid.new().str,
        )
        msg_bytes = ParseDict(msg, SapientMessage()).SerializeToString()

        msg_parsed = parse_message(msg_bytes, self.id_generator)
        msg_parsed_dict = json.loads(msg_parsed.data_json)
        self.assertDictEqual(msg_parsed_dict, msg)

    def test_task_msg(self):
        self.add_node_id_to_map()
        msg = get_task_message_template(
            node_id=self.node_id, task_id=ulid.new().str, region_id=ulid.new().str
        )
        msg_bytes = ParseDict(msg, SapientMessage()).SerializeToString()

        msg_parsed = parse_message(msg_bytes, self.id_generator)
        msg_parsed_dict = json.loads(msg_parsed.data_json)
        self.assertDictEqual(msg_parsed_dict, msg)

    def test_task_ack_msg(self):
        self.add_node_id_to_map()
        msg = get_task_ack_message_template(node_id=self.node_id, task_id=ulid.new().str)
        msg_bytes = ParseDict(msg, SapientMessage()).SerializeToString()

        msg_parsed = parse_message(msg_bytes, self.id_generator)
        msg_parsed_dict = json.loads(msg_parsed.data_json)
        self.assertDictEqual(msg_parsed_dict, msg)

    def test_alert_msg(self):
        self.add_node_id_to_map()
        msg = get_alert_message_template(node_id=self.node_id, alert_id=ulid.new().str)
        msg_bytes = ParseDict(msg, SapientMessage()).SerializeToString()

        msg_parsed = parse_message(msg_bytes, self.id_generator)
        msg_parsed_dict = json.loads(msg_parsed.data_json)
        self.assertDictEqual(msg_parsed_dict, msg)

    def test_alert_ack_msg(self):
        self.add_node_id_to_map()
        msg = get_alert_ack_message_template(node_id=self.node_id, alert_id=ulid.new().str)
        msg_bytes = ParseDict(msg, SapientMessage()).SerializeToString()

        msg_parsed = parse_message(msg_bytes, self.id_generator)
        msg_parsed_dict = json.loads(msg_parsed.data_json)
        self.assertDictEqual(msg_parsed_dict, msg)

    def test_error_msg(self):
        self.add_node_id_to_map()
        msg = get_error_message_template(node_id=self.node_id, dest_id=str(uuid.uuid4()))
        msg_bytes = ParseDict(msg, SapientMessage()).SerializeToString()

        msg_parsed = parse_message(msg_bytes, self.id_generator)
        msg_parsed_dict = json.loads(msg_parsed.data_json)
        self.assertDictEqual(msg_parsed_dict, msg)


if __name__ == "__main__":
    main(
        defaultTest=[
            "MsgParsingTestCase.test_registration_msg",
            "MsgParsingTestCase.test_registration_ack_msg",
            "MsgParsingTestCase.test_status_msg",
            "MsgParsingTestCase.test_detection_msg",
            "MsgParsingTestCase.test_task_msg",
            "MsgParsingTestCase.test_task_ack_msg",
            "MsgParsingTestCase.test_alert_msg",
            "MsgParsingTestCase.test_alert_ack_msg",
            "MsgParsingTestCase.test_error_msg",
        ]
    )
