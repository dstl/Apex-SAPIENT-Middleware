#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import json

from google.protobuf.json_format import Parse as MessageFromJson
from pytest import fixture

from sapient_apex_server.message_io import to_version
from sapient_apex_server.structures import SapientVersion
from sapient_msg.bsi_flex_335_v1_0.sapient_message_pb2 import (
    SapientMessage as OldestSapientMessage,
)
from sapient_msg.latest.sapient_message_pb2 import (
    SapientMessage as NewestSapientMessage,
)


def test_upgrade(proto_registration_v1: dict):
    oldest = OldestSapientMessage()
    MessageFromJson(json.dumps(proto_registration_v1), oldest)
    newest = to_version(oldest, SapientVersion.BSI_FLEX_335_V1_0, SapientVersion.LATEST)
    assert isinstance(newest, NewestSapientMessage)
    assert newest.registration is not None
    assert newest.registration.icd_version == "BSI Flex 335 v2.0"


def test_downgrade(proto_registration_latest: dict):
    newest = NewestSapientMessage()
    MessageFromJson(json.dumps(proto_registration_latest), newest)
    oldest = to_version(newest, SapientVersion.LATEST, SapientVersion.BSI_FLEX_335_V1_0)
    assert isinstance(oldest, OldestSapientMessage)
    assert oldest.registration is not None
    assert oldest.registration.icd_version == "BSI Flex 335 v1.0"


def test_noopgrades(proto_registration_v1: dict, proto_registration_latest: dict):
    oldest = OldestSapientMessage()
    MessageFromJson(json.dumps(proto_registration_v1), oldest)
    assert oldest is to_version(
        oldest, SapientVersion.BSI_FLEX_335_V1_0, SapientVersion.BSI_FLEX_335_V1_0
    )

    newest = NewestSapientMessage()
    MessageFromJson(json.dumps(proto_registration_latest), newest)
    assert newest is to_version(newest, SapientVersion.LATEST, SapientVersion.LATEST)


@fixture
def proto_registration_v1() -> dict:
    return {
        "timestamp": "2024-02-09T16:17:27.521839Z",
        "nodeId": "8cb1d098-74ba-4ddc-ab37-6bfbca14d582",
        "registration": {
            "nodeDefinition": [{"nodeType": "NODE_TYPE_OTHER"}],
            "icdVersion": "BSI Flex 335 v1.0",
            "name": "Silverfish : UGV",
            "shortName": "DUMMY_ASM",
            "capabilities": [
                {
                    "category": "Wifi_interface",
                    "type": "NODE_TYPE_CYBER",
                    "value": "20",
                    "units": "dBm",
                }
            ],
            "statusDefinition": {
                "statusInterval": {"units": "TIME_UNITS_SECONDS", "value": 5.0},
                "locationDefinition": {
                    "locationUnits": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                    "locationDatum": "LOCATION_DATUM_WGS84_E",
                    "zone": "30n",
                },
            },
            "modeDefinition": [
                {
                    "modeName": "Default",
                    "modeType": "MODE_TYPE_PERMANENT",
                    "settleTime": {"units": "TIME_UNITS_SECONDS", "value": 1.0},
                    "scanType": "SCAN_TYPE_STEERABLE",
                    "detectionDefinition": {
                        "locationType": {
                            "locationUnits": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                            "locationDatum": "LOCATION_DATUM_WGS84_E",
                            "zone": "30n",
                        },
                        "detectionReport": [
                            {
                                "category": "DETECTION_REPORT_CATEGORY_DETECTION",
                                "type": "confidence",
                                "units": "probability",
                                "onChange": False,
                            }
                        ],
                        "detectionClassDefinition": [
                            {
                                "confidenceDefinition": "CONFIDENCE_DEFINITION_MULTI_CLASS",
                                "classPerformance": [
                                    {
                                        "type": "FAR",
                                        "units": "Per Period",
                                        "unitValue": "1",
                                        "variationType": "Linear with Range",
                                    }
                                ],
                                "classDefinition": [
                                    {"type": "Human", "units": "probability"},
                                    {"type": "Vehicle", "units": "probability"},
                                ],
                            }
                        ],
                        "behaviourDefinition": [{"type": "Walking", "units": "probability"}],
                        "geometricError": {
                            "type": "Standard Deviation",
                            "units": "meters",
                            "variationType": "Linear with Range",
                            "performanceValue": [
                                {"type": "eRmin", "units": "eRmin", "unitValue": "0.1"},
                                {"type": "eRmax", "units": "eRmax", "unitValue": "0.5"},
                            ],
                        },
                    },
                    "task": [
                        {
                            "regionDefinition": {
                                "regionType": ["REGION_TYPE_AREA_OF_INTEREST"],
                                "regionArea": [
                                    {
                                        "locationUnits": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                                        "locationDatum": "LOCATION_DATUM_WGS84_E",
                                        "zone": "30n",
                                    }
                                ],
                            },
                            "command": [
                                {
                                    "name": "Request",
                                    "units": "Registration, Reset, Heartbeat, Stop, Start",
                                    "completionTime": {
                                        "units": "TIME_UNITS_SECONDS",
                                        "value": 10.0,
                                    },
                                    "type": "COMMAND_TYPE_REQUEST",
                                },
                                {
                                    "name": "LookAt",
                                    "units": "RangeBearing",
                                    "completionTime": {
                                        "units": "TIME_UNITS_SECONDS",
                                        "value": 10.0,
                                    },
                                    "type": "COMMAND_TYPE_LOOK_AT",
                                },
                                {
                                    "name": "GoTo",
                                    "units": "Location",
                                    "completionTime": {"units": "TIME_UNITS_SECONDS", "value": 0.0},
                                    "type": "COMMAND_TYPE_REQUEST",
                                },
                                {
                                    "name": "NetSurv",
                                    "units": "surveyTask",
                                    "completionTime": {
                                        "units": "TIME_UNITS_SECONDS",
                                        "value": 30.0,
                                    },
                                    "type": "COMMAND_TYPE_REQUEST",
                                },
                            ],
                        }
                    ],
                }
            ],
        },
    }


@fixture
def proto_registration_latest() -> dict:
    return {
        "timestamp": "2024-02-09T16:17:27.521839Z",
        "nodeId": "8cb1d098-74ba-4ddc-ab37-6bfbca14d582",
        "registration": {
            "nodeDefinition": [{"nodeType": "NODE_TYPE_OTHER"}],
            "icdVersion": "BSI Flex 335 v2.0",
            "name": "Silverfish : UGV",
            "shortName": "DUMMY_ASM",
            "capabilities": [
                {
                    "category": "Wifi_interface",
                    "type": "NODE_TYPE_CYBER",
                    "value": "20",
                    "units": "dBm",
                }
            ],
            "statusDefinition": {
                "statusInterval": {"units": "TIME_UNITS_SECONDS", "value": 5.0},
                "locationDefinition": {
                    "locationUnits": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                    "locationDatum": "LOCATION_DATUM_WGS84_E",
                    "zone": "30n",
                },
            },
            "modeDefinition": [
                {
                    "modeName": "Default",
                    "modeType": "MODE_TYPE_PERMANENT",
                    "settleTime": {"units": "TIME_UNITS_SECONDS", "value": 1.0},
                    "scanType": "SCAN_TYPE_STEERABLE",
                    "detectionDefinition": [
                        {
                            "locationType": {
                                "locationUnits": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                                "locationDatum": "LOCATION_DATUM_WGS84_E",
                                "zone": "30n",
                            },
                            "detectionReport": [
                                {
                                    "category": "DETECTION_REPORT_CATEGORY_DETECTION",
                                    "type": "confidence",
                                    "units": "probability",
                                    "onChange": False,
                                }
                            ],
                            "detectionClassDefinition": [
                                {
                                    "confidenceDefinition": "CONFIDENCE_DEFINITION_MULTI_CLASS",
                                    "classPerformance": [
                                        {
                                            "type": "FAR",
                                            "units": "Per Period",
                                            "unitValue": "1",
                                            "variationType": "Linear with Range",
                                        }
                                    ],
                                    "classDefinition": [
                                        {"type": "Human", "units": "probability"},
                                        {"type": "Vehicle", "units": "probability"},
                                    ],
                                }
                            ],
                            "behaviourDefinition": [{"type": "Walking", "units": "probability"}],
                            "geometricError": {
                                "type": "Standard Deviation",
                                "units": "meters",
                                "variationType": "Linear with Range",
                                "performanceValue": [
                                    {"type": "eRmin", "units": "eRmin", "unitValue": "0.1"},
                                    {"type": "eRmax", "units": "eRmax", "unitValue": "0.5"},
                                ],
                            },
                        }
                    ],
                    "task": {
                        "regionDefinition": {
                            "regionType": ["REGION_TYPE_AREA_OF_INTEREST"],
                            "regionArea": [
                                {
                                    "locationUnits": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                                    "locationDatum": "LOCATION_DATUM_WGS84_E",
                                    "zone": "30n",
                                }
                            ],
                        },
                        "command": [
                            {
                                "units": "Registration, Reset, Heartbeat, Stop, Start",
                                "completionTime": {
                                    "units": "TIME_UNITS_SECONDS",
                                    "value": 10.0,
                                },
                                "type": "COMMAND_TYPE_REQUEST",
                            },
                            {
                                "units": "RangeBearing",
                                "completionTime": {
                                    "units": "TIME_UNITS_SECONDS",
                                    "value": 10.0,
                                },
                                "type": "COMMAND_TYPE_LOOK_AT",
                            },
                            {
                                "units": "Location",
                                "completionTime": {"units": "TIME_UNITS_SECONDS", "value": 0.0},
                                "type": "COMMAND_TYPE_REQUEST",
                            },
                            {
                                "units": "surveyTask",
                                "completionTime": {
                                    "units": "TIME_UNITS_SECONDS",
                                    "value": 30.0,
                                },
                                "type": "COMMAND_TYPE_REQUEST",
                            },
                        ],
                    },
                }
            ],
        },
    }
