#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from sapient_apex_api.response_protos import (
    Location,
    LocationOrRangeBearing,
    NodeDefinition,
)


class StatusCode(Enum):
    ok = "OK"
    error = "Error"


class StatusResponse(BaseModel):
    """Status Response with optional detail."""

    status: StatusCode = Field(StatusCode.ok, description="Status of the call")
    detail: Optional[str] = Field(None, description="Reason for error (if applicable)")


class RootResponse(BaseModel):
    info: str = Field(description="Information")
    version: str = Field(description="Version Number")


class BaseNodeResponse(BaseModel):
    node_id: str = Field(description="Node ID in UUID format")
    timestamp: str = Field(description="Timestamp")


class NodeLocationResponse(BaseNodeResponse):
    node_location: Location


class NodeFieldOfViewResponse(BaseNodeResponse):
    field_of_view: LocationOrRangeBearing


class DetectionSource(Enum):
    all = "all"  # All Detections
    edge = "edge"  # Detections from Edge Nodes
    fused = "fused"  # Fused detections from the DMM


class AssociatedFile(BaseModel):
    type: str = Field(default_factory=str)
    url: str = Field(default_factory=str)


class AssociatedFilesResponse(BaseNodeResponse):
    associated_files: list[AssociatedFile] = Field(default_factory=list[AssociatedFile])


class DetectionResponse(BaseNodeResponse):
    detection_report: dict = Field(default_factory=dict)
    # It was not possible to fully generate/specify the pydantic
    # schema for detection_report due to its nested subclasses


class NodeDefinitionResponse(BaseNodeResponse):
    node_definition: list[NodeDefinition] = Field(default_factory=list)
