#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""With the changes in Sapient V7 came the need to use ULIDs instead of integers for ids.
To support this, this class has been created so that ULIDs coming from protobuf sensors can
be mapped to an integer ID that DMM will recognise (and vise versa).

Additionally, certain IDs will only be unique per sensor (for example, sensor with ID 1 could
send an object detection with objectID 1, while sensor with ID 2 could also send an object
detection with objectID 1. These two sensors are referring to different objects). This file
contains multiple classes to support the idea discussed above. The basic structure of these
classes is as follows:
- IdGenerator - the base class that contains ID mappings for globally unique IDs
- SensorIdMapping - the mapping of IDs that are unique per sensor
"""
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, Union

import ulid


@dataclass
class SensorIdMapping:
    xml_id: int
    task_id_map: Dict[str, int]
    report_id_map: Dict[str, int]
    object_id_map: Dict[str, int]

    def __init__(self, xml_id):
        self.xml_id = xml_id
        self.task_id_map = {}
        self.report_id_map = {}
        self.object_id_map = {}
        self.map_registry = {
            "node_id": self,
            "destination_id": self,
            "task_id": self.task_id_map,
            "report_id": self.report_id_map,
            "object_id": self.object_id_map,
            "active_task_id": self.task_id_map,
        }


class IdGenerator:
    node_id_map: Dict[str, SensorIdMapping]
    region_id_map: Dict[str, int]
    alert_id_map: Dict[str, int]
    all_ids_map: Dict[str, int]

    def __init__(self, config: dict):
        self.node_id_map: Dict[str, SensorIdMapping] = {}
        # initialise all of the static node ids
        for node_uuid, node_id in (
            config.get("autoAssignSensorIDInRegistration", {}).get("staticNodeIds", {}).items()
        ):
            self.node_id_map[node_uuid] = SensorIdMapping(node_id)

        self.region_id_map = {}
        self.alert_id_map = {}
        self.all_ids_map = {}
        self.enabled = config.get("autoAssignSensorIDInRegistration", {}).get("enabled", False)
        self.next_id = (
            config.get("autoAssignSensorIDInRegistration", {}).get("startingID", 1000001) - 1
        )
        self.next_report_id = (
            config.get("autoAssignSensorIDInRegistration", {}).get("startingID", 1000001) - 1
        )
        self.next_object_id = (
            config.get("autoAssignSensorIDInRegistration", {}).get("startingID", 1000001) - 1
        )
        self.id_map_registry: Dict[str, Union[Dict[str, SensorIdMapping], Dict[str, int]]] = {
            "node_id": self.node_id_map,
            "task_id": self.node_id_map,
            "region_id": self.region_id_map,
            "report_id": self.node_id_map,
            "object_id": self.node_id_map,
            "alert_id": self.alert_id_map,
            "active_task_id": self.node_id_map,
            "destination_id": self.node_id_map,
        }

    def get_next_id(self) -> int:
        self.next_id += 1
        return self.next_id

    def get_id_ulid_pair(self) -> Tuple[str, int]:
        self.next_id += 1
        sensor_ulid = ulid.new().str
        self.node_id_map[sensor_ulid] = SensorIdMapping(self.next_id)
        return sensor_ulid, self.next_id

    @staticmethod
    def get_ulid_from_id(
        id_map: Union[Dict[str, SensorIdMapping], Dict[str, int]], node_id: int
    ) -> Optional[str]:
        found_node_ulid = None
        if isinstance(list(id_map.values())[0], int):
            get_id_field = lambda x: x  # noqa E731
        else:
            get_id_field = lambda x: x.xml_id  # noqa E731
        for node_ulid in id_map.keys():
            if get_id_field(id_map[node_ulid]) == node_id:
                found_node_ulid = node_ulid
                break
        try:
            return found_node_ulid
        except IndexError:
            return None

    @staticmethod
    def is_node_id_map(map_name: str):
        return map_name in [
            "node_id",
            "task_id",
            "report_id",
            "object_id",
            "active_task_id",
        ]

    def insert_new_ulid_id_pair(
        self,
        node_ulid: str,
        node_id: int,
        id_map: Dict[str, Union[SensorIdMapping, int]],
        is_node_id_map: bool,
    ):
        if is_node_id_map:
            id_mapping = SensorIdMapping(node_id)
        else:
            id_mapping = node_id
        id_map[node_ulid] = id_mapping
        self.all_ids_map[node_ulid] = node_id
