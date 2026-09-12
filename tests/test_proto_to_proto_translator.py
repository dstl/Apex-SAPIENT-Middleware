#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from google.protobuf.json_format import MessageToDict, ParseDict

from sapient_apex_server.translator.proto_to_proto_translator import translate_v2_to_v1
from sapient_msg.bsi_flex_335_v2_0.sapient_message_pb2 import SapientMessage


def test_v2_registration_downgrade_omits_v2_only_taxonomy_and_commands():
    message = ParseDict(
        {
            "registration": {
                "icd_version": "BSI Flex 335 v2.0",
                "mode_definition": [
                    {
                        "detection_definition": [
                            {
                                "detection_class_definition": [
                                    {
                                        "taxonomy_dock_definition": [
                                            {
                                                "Dock_class_namespace": "sapient_core",
                                                "Dock_class": "Land Vehicle.2 Wheels.Other",
                                            }
                                        ]
                                    }
                                ]
                            }
                        ],
                        "task": {
                            "region_definition": {
                                "region_type": [
                                    "REGION_TYPE_AREA_OF_INTEREST",
                                    "REGION_TYPE_MOBILE_NODE_NO_GO_AREA",
                                    "REGION_TYPE_MOBILE_NODE_GO_AREA",
                                ]
                            },
                            "command": [
                                {"type": "COMMAND_TYPE_MOVE_TO"},
                                {"type": "COMMAND_TYPE_PATROL"},
                                {"type": "COMMAND_TYPE_FOLLOW"},
                                {"type": "COMMAND_TYPE_LOOK_AT"},
                            ]
                        },
                    }
                ],
            }
        },
        SapientMessage(),
    )

    downgraded = translate_v2_to_v1(message)
    registration = MessageToDict(downgraded, preserving_proto_field_name=True)["registration"]

    assert registration["icd_version"] == "BSI Flex 335 v1.0"
    detection_definition = registration["mode_definition"][0]["detection_definition"]
    detection_class = detection_definition["detection_class_definition"][0]
    assert "taxonomy_dock_definition" not in detection_class

    task = registration["mode_definition"][0]["task"][0]
    assert task["region_definition"]["region_type"] == ["REGION_TYPE_AREA_OF_INTEREST"]

    commands = task["command"]
    assert [command["type"] for command in commands] == ["COMMAND_TYPE_LOOK_AT"]
    assert commands[0]["name"] == "LookAt"
