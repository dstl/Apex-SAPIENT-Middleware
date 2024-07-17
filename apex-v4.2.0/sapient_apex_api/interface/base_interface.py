#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, Optional

from sapient_apex_api.response_models import (
    AssociatedFilesResponse,
    DetectionResponse,
    DetectionSource,
    NodeDefinitionResponse,
    NodeFieldOfViewResponse,
    NodeLocationResponse,
)


class BaseInterface(ABC):
    @abstractmethod
    def insert_into(
        self,
        index: str,
        data: dict,
    ):
        pass

    @abstractmethod
    def scan(
        self,
        index: str,
        query: dict,
    ) -> Iterable[Dict[str, Any]]:
        pass

    @abstractmethod
    def search(
        self,
        index: str,
        query: dict,
        sort: Any = None,
        size: Optional[int] = None,
    ) -> Any:
        pass

    @abstractmethod
    def get_registered_node_ids() -> list[str]:
        pass

    @abstractmethod
    def get_locations(self, node_ids: list[str]) -> list[NodeLocationResponse]:
        pass

    @abstractmethod
    def get_field_of_views(self, node_ids: list[str]) -> list[NodeFieldOfViewResponse]:
        pass

    @abstractmethod
    def get_detections(
        self,
        node_ids: list[str],
        detection_source: DetectionSource,
        detection_confidence: float,
        detection_classification: str,
        detection_from: datetime,
        detection_to: datetime,
        detection_interval: timedelta,
        detection_count: int,
    ) -> list[DetectionResponse]:
        pass

    @abstractmethod
    def get_detections_locations(
        self,
        node_ids: list[str],
        detection_source: DetectionSource,
        detection_confidence: float,
        detection_classification: str,
        detection_from: datetime,
        detection_to: datetime,
        detection_interval: timedelta,
        detection_count: int,
    ) -> list[NodeLocationResponse]:
        pass

    @abstractmethod
    def get_node_definitions(self) -> list[NodeDefinitionResponse]:
        pass

    @abstractmethod
    def get_detections_associated_files(
        self,
        node_ids: list[str],
        detection_source: DetectionSource,
        detection_confidence: float,
        detection_classification: str,
        detection_from: datetime,
        detection_to: datetime,
        detection_interval: timedelta,
        detection_count: int,
    ) -> list[AssociatedFilesResponse]:
        pass
