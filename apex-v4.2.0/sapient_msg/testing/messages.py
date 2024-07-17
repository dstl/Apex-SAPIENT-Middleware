import json
from collections.abc import Mapping
from datetime import datetime
from functools import reduce
from uuid import uuid4

import ulid
from google.protobuf.json_format import Parse as MessageFromJson

from sapient_apex_server.structures import SapientVersion
from sapient_msg.latest.sapient_message_pb2 import SapientMessage


def deepmerge(prior: dict, update: dict, _trace: str = "") -> dict:
    """Merges dictionary deeply.

    Lists in `update` replace equivalent items in `prior`. They are not concatenated together.
    """
    result = {}
    for key in set(prior).intersection(update):
        prior_is_map = isinstance(prior[key], Mapping)
        update_is_map = isinstance(update[key], Mapping)
        if prior_is_map and not update_is_map:
            raise ValueError(f"key {_trace}{key} ought to be a map")
        elif update_is_map and not prior_is_map:
            raise ValueError(f"key {_trace}{key} should not be a map")
        elif update_is_map and prior_is_map:
            result[key] = deepmerge(
                prior[key], update[key], _trace=f"{_trace}.{key}" if _trace else f"{key}"
            )
        else:
            result[key] = update[key]
    for key in set(prior) - set(update):
        result[key] = prior[key]
    for key in set(update) - set(prior):
        result[key] = update[key]
    return result


def deepsplit(**kwargs) -> dict:
    """Split keywords `a__b__c=1` into `{"a": {"b": {"c": 1}}}"""

    def folder(left: dict, kv: tuple) -> dict:
        def inside(x: dict, y: str):
            return {y: x}

        initial_key, *other_keys = kv[0].split("__")[::-1]
        right = reduce(inside, other_keys, {initial_key: kv[1]})

        return deepmerge(left, right)

    return reduce(folder, kwargs.items(), {})


def registration_message(**kwargs):
    """Registration message in latest standard.

    The keyword arguments are merged deeply with a template.
    Keywords with format `a__b__c` are first broken up into nested dictionaries.
    This makes it easier to modify a single deeply nested entry.
    """
    to_split, kwargs = (
        {k: v for k, v in kwargs.items() if "__" in k},
        {k: v for k, v in kwargs.items() if "__" not in k},
    )

    message = {
        "timestamp": datetime.utcnow().astimezone().isoformat(),
        "node_id": str(uuid4()),
        "registration": {
            "node_definition": [{"node_type": "NODE_TYPE_OTHER"}],
            "icd_version": SapientVersion.LATEST.protocol_name,
            "name": "Supported ICD Version Test Node",
            "short_name": "Test Node",
            "capabilities": [{"category": "", "type": ""}],
            "status_definition": {"status_interval": {"units": "TIME_UNITS_SECONDS", "value": 5}},
            "mode_definition": [
                {
                    "mode_name": "default",
                    "mode_type": "MODE_TYPE_PERMANENT",
                    "settle_time": {"units": "TIME_UNITS_SECONDS", "value": 1},
                    "detection_definition": [
                        {
                            "location_type": {
                                "location_units": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                                "location_datum": "LOCATION_DATUM_WGS84_E",
                            }
                        }
                    ],
                    "task": {
                        "region_definition": {
                            "region_type": ["REGION_TYPE_BOUNDARY"],
                            "region_area": [
                                {
                                    "location_units": "LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                                    "location_datum": "LOCATION_DATUM_WGS84_E",
                                }
                            ],
                        }
                    },
                }
            ],
            "config_data": [{"manufacturer": "DummyManufacturer", "model": "v0.0.0"}],
        },
    }
    message = deepmerge(message, kwargs)
    message = deepmerge(message, deepsplit(**to_split))
    result = SapientMessage()
    MessageFromJson(json.dumps(message), result)
    return result


def status_message(**kwargs):
    """Status message in latest standard.

    The keyword arguments are merged deeply with a template.
    Keywords with format `a__b__c` are first broken up into nested dictionaries.
    This makes it easier to modify a single deeply nested entry.
    """
    to_split, kwargs = (
        {k: v for k, v in kwargs.items() if "__" in k},
        {k: v for k, v in kwargs.items() if "__" not in k},
    )

    message = {
        "timestamp": datetime.utcnow().astimezone().isoformat(),
        "node_id": str(uuid4()),
        "status_report": {
            "report_id": ulid.new().str,
            "system": "SYSTEM_OK",
            "info": "INFO_NEW",
            "mode": "dummy mode",
        },
    }
    message = deepmerge(message, kwargs)
    message = deepmerge(message, deepsplit(**to_split))
    result = SapientMessage()
    MessageFromJson(json.dumps(message), result)
    return result
