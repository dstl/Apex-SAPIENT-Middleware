#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from queue import Queue
from typing import Optional
import sys
import os
from datetime import datetime
from unittest.mock import Mock
import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.append(ROOT_DIR)

from sapient_apex_api.interface.elastic_interface import ElasticInterface
from sapient_apex_server.time_util import datetime_to_str
from sapient_apex_server.structures import MessageRecord, ParsedRecord
from sapient_apex_api.manager import Manager
from sapient_msg.latest.sapient_message_pb2 import SapientMessage

from tests.msg_templates import get_register_template, json_to_proto


class TestManager:
    manager: Manager
    database_queue: Queue

    @pytest.fixture(autouse=True)
    def before_each(self):
        self.database_queue = Queue()
        self.mock_interface = Mock(ElasticInterface)
        self.manager = Manager(self.mock_interface)

    def _get_expected_message(
        self,
        sapient_dict: dict,
        destination_id: str,
        message_type: str,
    ) -> dict:
        sapient_dict["destination_id"] = destination_id
        sapient_dict["message"] = sapient_dict[message_type]
        del sapient_dict[message_type]
        sapient_dict["message_type"] = message_type
        return sapient_dict

    def _get_message_record(
        self,
        message_type: Optional[str],
        node_id: Optional[str],
        destination_id: Optional[str],
        message_timestamp: Optional[datetime],
        proto_message: Optional[SapientMessage],
    ) -> MessageRecord:
        dummy_message = MessageRecord(None, "", None, None)
        dummy_message.parsed = ParsedRecord(
            message_type,
            node_id,
            None,
            destination_id,
            message_timestamp,
            None,
            proto_message,
            None,
        )
        return dummy_message

    def test_add_message(self, before_each):
        message_timestamp = datetime.utcnow()
        registration_dict = get_register_template("1234")
        registration_dict["timestamp"] = datetime_to_str(message_timestamp)
        dummy_message = self._get_message_record(
            "registration",
            "1234",
            None,
            message_timestamp,
            json_to_proto(SapientMessage, registration_dict),
        )

        self.manager.add_sapient_message(dummy_message)
        self.mock_interface.insert_into.assert_called_once_with(
            "messages", self._get_expected_message(registration_dict, "", "registration")
        )

    def test_add_message_no_proto_message(self, before_each):
        self.manager.add_sapient_message(self._get_message_record(None, None, None, None, None))
        self.mock_interface.insert_into.assert_not_called()


if __name__ == "__main__":
    pytest.main(
        # Use the -k flag to specify a test to run (helpful for debugging)
        # ["-k", "test_add_message"],
    )
