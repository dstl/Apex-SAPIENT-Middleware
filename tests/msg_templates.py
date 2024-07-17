#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#
import os
import sys
from typing import Optional
from datetime import datetime
from google.protobuf.message import Message
from google.protobuf.json_format import ParseDict

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)
sys.path.append(ROOT_DIR)

from sapient_apex_server.time_util import datetime_to_str


def json_to_proto(message_class: type, json_dict: dict) -> Message:
    msg = message_class()
    ParseDict(json_dict, msg)
    return msg


def get_register_template(node_id: str) -> dict:
    return {
        "timestamp": datetime_to_str(datetime.utcnow()),
        "node_id": str(node_id),
        "registration": {
            "icd_version": "BSI Flex 335 v2.0",
            "node_definition": [{"node_type": "NODE_TYPE_OTHER", "node_sub_type": ["Test Radar"]}],
            "name": "Test Radar",
            "short_name": "Test Sensor",
            "capabilities": [{"category": "other", "type": "test capability"}],
            "status_definition": {
                "status_interval": {"units": "TIME_UNITS_SECONDS", "value": 5.0},
                "location_definition": {
                    "location_units": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                    "location_datum": "LOCATION_DATUM_WGS84_E",
                    "zone": "30N",
                },
                "status_report": [{"category": "STATUS_REPORT_CATEGORY_STATUS", "type": "Status"}],
            },
            "mode_definition": [
                {
                    "mode_name": "test",
                    "mode_type": "MODE_TYPE_PERMANENT",
                    "settle_time": {"units": "TIME_UNITS_SECONDS", "value": 5.0},
                    "scan_type": "SCAN_TYPE_STEERABLE",
                    "tracking_type": "TRACKING_TYPE_TRACK",
                    "detection_definition": [
                        {
                            "location_type": {
                                "location_units": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                                "location_datum": "LOCATION_DATUM_WGS84_E",
                                "zone": "30N",
                            },
                            "detection_class_definition": [
                                {
                                    "confidence_definition": "CONFIDENCE_DEFINITION_SINGLE_CLASS",
                                    "class_definition": [{"type": "Human", "units": "Probability"}],
                                }
                            ],
                        }
                    ],
                    "task": {
                        "concurrent_tasks": 2,
                        "region_definition": {
                            "region_type": ["REGION_TYPE_AREA_OF_INTEREST"],
                            "settle_time": {
                                "units": "TIME_UNITS_SECONDS",
                                "value": 5.0,
                            },
                            "region_area": [
                                {
                                    "location_units": (  # noqa: E501
                                        "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M"
                                    ),
                                    "location_datum": "LOCATION_DATUM_WGS84_E",
                                    "zone": "30N",
                                }
                            ],
                        },
                        "command": [
                            {
                                "type": "COMMAND_TYPE_REQUEST",
                                "units": "Start, Stop, Reset, Heartbeat",
                                "completion_time": {
                                    "units": "TIME_UNITS_SECONDS",
                                    "value": 5.0,
                                },
                            }
                        ],
                    },
                }
            ],
            "config_data": [{"manufacturer": "manufacturer", "model": "model"}],
        },
    }


def get_register_ack_message_template(node_id: str) -> dict:
    return {
        "timestamp": datetime_to_str(datetime.utcnow()),
        "node_id": str(node_id),
        "registration_ack": {"acceptance": True, "ack_response_reason": ["Success"]},
    }


def get_status_message_template(node_id: str, report_id: str) -> dict:
    return {
        "timestamp": datetime_to_str(datetime.utcnow()),
        "node_id": str(node_id),
        "status_report": {
            "report_id": str(report_id),
            "system": "SYSTEM_OK",
            "info": "INFO_NEW",
            "node_location": {
                "x": 0.1,
                "y": 0.1,
                "coordinate_system": "LOCATION_COORDINATE_SYSTEM_UTM_M",
                "datum": "LOCATION_DATUM_WGS84_G",
            },
            "field_of_view": {
                "range_bearing": {
                    "range": 300,
                    "azimuth": 0,
                    "horizontal_extent": 360,
                    "coordinate_system": "RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_M",
                    "datum": "RANGE_BEARING_DATUM_TRUE",
                }
            },
            "coverage": [
                {
                    "location_list": {
                        "locations": [
                            {
                                "x": 0.1,
                                "y": 0.1,
                                "coordinate_system": "LOCATION_COORDINATE_SYSTEM_UTM_M",
                                "datum": "LOCATION_DATUM_WGS84_G",
                            },
                            {
                                "x": 0.1,
                                "y": 0.1,
                                "coordinate_system": "LOCATION_COORDINATE_SYSTEM_UTM_M",
                                "datum": "LOCATION_DATUM_WGS84_G",
                            },
                        ]
                    }
                }
            ],
        },
    }


def get_detection_message_template(node_id: str, report_id: str, object_id: str) -> dict:
    return {
        "timestamp": datetime_to_str(datetime.utcnow()),
        "node_id": str(node_id),
        "detection_report": {
            "report_id": str(report_id),
            "object_id": str(object_id),
            "range_bearing": {
                "elevation": 1.0,
                "azimuth": 2.0,
                "range": 3.0,
                "elevation_error": 1.0,
                "azimuth_error": 1.0,
                "range_error": 2.0,
                "coordinate_system": "RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_M",
                "datum": "RANGE_BEARING_DATUM_TRUE",
            },
            "detection_confidence": 0.9,
            "colour": "blue",
            "classification": [
                {
                    "type": "Air Vehicle",
                    "confidence": 0.8,
                },
                {
                    "type": "Unknown",
                    "confidence": 0.2,
                },
            ],
        },
    }


def get_task_message_template(
    node_id: str, task_id: str, region_id: str, destination_id: Optional[str] = None
) -> dict:
    return {
        "timestamp": datetime_to_str(datetime.utcnow()),
        "node_id": str(node_id),
        **({"destination_id": str(destination_id)} if destination_id is not None else {}),
        "task": {
            "task_id": str(task_id),
            "task_name": "RIC AREA",
            "task_description": "Testing the sensor tasking messages",
            "control": "CONTROL_START",
            "region": [
                {
                    "type": "REGION_TYPE_AREA_OF_INTEREST",
                    "region_id": str(region_id),
                    "region_name": "Some Building",
                    "region_area": {
                        "location_list": {
                            "locations": [
                                {
                                    "x": 0.1,
                                    "y": 0.1,
                                    "coordinate_system": "LOCATION_COORDINATE_SYSTEM_UTM_M",
                                    "datum": "LOCATION_DATUM_WGS84_G",
                                },
                                {
                                    "x": 0.1,
                                    "y": 0.1,
                                    "coordinate_system": "LOCATION_COORDINATE_SYSTEM_UTM_M",
                                    "datum": "LOCATION_DATUM_WGS84_G",
                                },
                                {
                                    "x": 0.1,
                                    "y": 0.1,
                                    "coordinate_system": "LOCATION_COORDINATE_SYSTEM_UTM_M",
                                    "datum": "LOCATION_DATUM_WGS84_G",
                                },
                                {
                                    "x": 0.1,
                                    "y": 0.1,
                                    "coordinate_system": "LOCATION_COORDINATE_SYSTEM_UTM_M",
                                    "datum": "LOCATION_DATUM_WGS84_G",
                                },
                            ]
                        }
                    },
                }
            ],
        },
    }


def get_task_ack_message_template(node_id: str, task_id: str) -> dict:
    return {
        "timestamp": datetime_to_str(datetime.utcnow()),
        "node_id": str(node_id),
        "task_ack": {"task_id": str(task_id), "task_status": "TASK_STATUS_ACCEPTED"},
    }


def get_alert_message_template(node_id: str, alert_id: str) -> dict:
    return {
        "timestamp": datetime_to_str(datetime.utcnow()),
        "node_id": str(node_id),
        "alert": {
            "alert_id": str(alert_id),
            "alert_type": "ALERT_TYPE_WARNING",
            "status": "ALERT_STATUS_ACTIVE",
            "description": "This is a test warming alert",
            "range_bearing": {
                "elevation": 1.0,
                "azimuth": 2.0,
                "range": 3.0,
                "elevation_error": 1.0,
                "azimuth_error": 1.0,
                "range_error": 2.0,
                "coordinate_system": "RANGE_BEARING_COORDINATE_SYSTEM_DEGREES_M",
                "datum": "RANGE_BEARING_DATUM_TRUE",
            },
        },
    }


def get_alert_ack_message_template(node_id: str, alert_id: str) -> dict:
    return {
        "timestamp": datetime_to_str(datetime.utcnow()),
        "node_id": str(node_id),
        "alert_ack": {
            "alert_id": str(alert_id),
            "alert_ack_status": "ALERT_ACK_STATUS_ACCEPTED",
        },
    }


def get_error_message_template(node_id: str, dest_id: str) -> dict:
    return {
        "timestamp": datetime_to_str(datetime.utcnow()),
        "node_id": str(node_id),
        "destination_id": str(dest_id),
        "error": {
            "packet": "VGVzdCBwYWNrZXQ=",
            "error_message": [
                (  # noqa: E501
                    "Expected node ID 01H5M3TWD0C47QPV0F2C9XT9CC, got node ID"
                    " 01H5M3TWD0C47QPV0F2C9XT9CD"
                )
            ],
        },
    }


def get_invalid_status_message_template(node_id: str, report_id: str) -> dict:
    return {
        "nodeId": str(node_id),
        "timestamp": datetime_to_str(datetime.utcnow()),
        "statusReport": {
            "reportId": str(report_id),
            "system": "SYSTEM_OK",
            "info": "INFO_UNSPECIFIED",
        },
    }
