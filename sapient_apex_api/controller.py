#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from datetime import datetime, timedelta
from importlib.metadata import metadata
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from sapient_apex_api.interface.base_interface import BaseInterface
from sapient_apex_api.response_models import (
    AssociatedFilesResponse,
    DetectionResponse,
    DetectionSource,
    NodeDefinitionResponse,
    NodeFieldOfViewResponse,
    NodeLocationResponse,
    RootResponse,
)

# Re-usable User Hints for parameters
node_ids_query = Query(
    default=["all"],
    description="The node ID(s) of the sender(s) of the message",
)
detection_source_query = Query(
    default=DetectionSource.all,
    description="Source of the detection",
)
detection_confidence_query = Query(
    default=0.0,
    description="Detection's Confidence (Above this value)",
)
detection_classification_query = Query(
    default="",
    description="Detection's Classification to filter on",
)
detection_from_query = Query(
    default=datetime.min,
    description="Detections searched from this timestamp",
)
detection_to_query = Query(
    default=datetime.min,
    description="Detections searched to this timestamp",
)
detection_interval_query = Query(
    default=timedelta(0),
    description="Detections searched with a interval offset before current time",
)
detection_count_query = Query(
    default=10, description="Number of Detections to obtain for a node_id"
)


class APIRouterDB(APIRouter):
    def __init__(self):
        super().__init__()
        self.db_interface: Optional[BaseInterface] = None

    def set_db_interface(self, db_interface: BaseInterface) -> None:
        self.db_interface = db_interface


router = APIRouterDB()


@router.get("/", status_code=status.HTTP_200_OK)
async def root() -> RootResponse:
    """
    Returns some basic information about the REST/Service/API
    """

    return RootResponse(
        info=f"""REST API to the {metadata("apex")["summary"]}""",
        version=metadata("apex")["version"],
    )


@router.get(
    "/registered",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"detail": ""},
        status.HTTP_400_BAD_REQUEST: {"detail": ""},
    },
)
async def get_registered_node_ids() -> list[str]:
    if router.db_interface is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database Service Unavailable or not started.",
        )

    node_ids = router.db_interface.get_registered_node_ids()
    if len(node_ids) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No Registered Nodes found.",
        )

    return node_ids


@router.get(
    "/locations",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"detail": ""},
        status.HTTP_400_BAD_REQUEST: {"detail": ""},
    },
)
async def get_locations(
    node_ids: list[str] = node_ids_query,
) -> list[NodeLocationResponse]:
    """
    Returns the list of nodes which are currently registered
    along with their last reported locations.
    Defaults to all registered nodes, if node_id is 'all', else the found one.
    """
    if router.db_interface is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database Service Unavailable or not started.",
        )

    locations = router.db_interface.get_locations(node_ids=node_ids)

    if "all" not in node_ids and len(locations) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"node_ids {','.join(node_ids)} could not be found",
        )

    return locations


@router.get(
    "/field_of_views",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"detail": ""},
        status.HTTP_400_BAD_REQUEST: {"detail": ""},
    },
)
async def get_field_of_views(
    node_ids: list[str] = node_ids_query,
) -> list[NodeFieldOfViewResponse]:
    """
    Returns the list of nodes which are currently registered
    along with their last reported fields of view.
    Defaults to all registered nodes, if node_id is 'all', else the found one.
    """
    if router.db_interface is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database Service Unavailable or not started.",
        )

    field_of_views = router.db_interface.get_field_of_views(node_ids=node_ids)
    if "all" not in node_ids and len(field_of_views) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"node_ids {','.join(node_ids)} could not be found",
        )

    return field_of_views


@router.get(
    "/detections",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"detail": ""},
    },
)
async def get_detections(
    node_ids: list[str] = node_ids_query,
    detection_source: DetectionSource = detection_source_query,
    detection_confidence: float = detection_confidence_query,
    detection_classification: str = detection_classification_query,
    detection_from: datetime = detection_from_query,
    detection_to: datetime = detection_to_query,
    detection_interval: timedelta = detection_interval_query,
    detection_count: int = detection_count_query,
) -> list[DetectionResponse]:
    if router.db_interface is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database Service Unavailable or not started.",
        )

    detections = router.db_interface.get_detections(
        node_ids=node_ids,
        detection_source=detection_source,
        detection_confidence=detection_confidence,
        detection_classification=detection_classification,
        detection_from=detection_from,
        detection_to=detection_to,
        detection_interval=detection_interval,
        detection_count=detection_count,
    )

    return detections


@router.get(
    "/detections/locations",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"detail": ""},
    },
)
async def get_detections_locations(
    node_ids: list[str] = node_ids_query,
    detection_source: DetectionSource = detection_source_query,
    detection_confidence: float = detection_confidence_query,
    detection_classification: str = detection_classification_query,
    detection_from: datetime = detection_from_query,
    detection_to: datetime = detection_to_query,
    detection_interval: timedelta = detection_interval_query,
    detection_count: int = detection_count_query,
) -> list[NodeLocationResponse]:
    if router.db_interface is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database Service Unavailable or not started.",
        )

    detections_locations = router.db_interface.get_detections_locations(
        node_ids=node_ids,
        detection_source=detection_source,
        detection_confidence=detection_confidence,
        detection_classification=detection_classification,
        detection_from=detection_from,
        detection_to=detection_to,
        detection_interval=detection_interval,
        detection_count=detection_count,
    )

    return detections_locations


@router.get(
    "/detections/associated_files",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"detail": ""},
    },
)
async def get_detections_associated_files(
    node_ids: list[str] = node_ids_query,
    detection_source: DetectionSource = detection_source_query,
    detection_confidence: float = detection_confidence_query,
    detection_classification: str = detection_classification_query,
    detection_from: datetime = detection_from_query,
    detection_to: datetime = detection_to_query,
    detection_interval: timedelta = detection_interval_query,
    detection_count: int = detection_count_query,
) -> list[AssociatedFilesResponse]:
    if router.db_interface is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database Service Unavailable or not started.",
        )

    detections_associated_files = router.db_interface.get_detections_associated_files(
        node_ids=node_ids,
        detection_source=detection_source,
        detection_confidence=detection_confidence,
        detection_classification=detection_classification,
        detection_from=detection_from,
        detection_to=detection_to,
        detection_interval=detection_interval,
        detection_count=detection_count,
    )

    return detections_associated_files


@router.get(
    "/node_definitions",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"detail": ""},
        status.HTTP_400_BAD_REQUEST: {"detail": ""},
    },
)
async def get_node_definitions() -> list[NodeDefinitionResponse]:
    """
    Node type and subtypes for all nodes.
    """
    if router.db_interface is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database Service Unavailable or not started.",
        )

    return router.db_interface.get_node_definitions()
