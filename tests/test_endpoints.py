#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from sapient_apex_api.interface.elastic_interface import ElasticInterface
from sapient_apex_api.response_models import (
    NodeDefinitionResponse,
    NodeFieldOfViewResponse,
)
from sapient_apex_api.response_protos import (
    LocationOrRangeBearing,
    NodeDefinition,
    RangeBearingCone,
)
from sapient_apex_server.apex import app

client = TestClient(app)


def test_get_root():
    response = client.get("/")
    assert response.status_code == 200
    reponse_data = response.json()
    assert "info" in reponse_data
    assert "version" in reponse_data


def test_get_registered_node_ids():
    # Test failure with no database interface
    response = client.get("/registered")
    assert response.status_code == 503

    # Test failure with no results
    with mock.patch(
        "sapient_apex_api.controller.router.db_interface", mock.MagicMock()
    ) as mock_db_interface:
        response = client.get("/registered")
        mock_db_interface.get_registered_node_ids.assert_called_once()
        assert response.status_code == 400


def test_get_locations():
    # Test failure with no database interface
    response = client.get("/locations")
    assert response.status_code == 503

    # Test success with "all" node_ids
    with mock.patch(
        "sapient_apex_api.controller.router.db_interface", mock.MagicMock()
    ) as mock_db_interface:
        response = client.get("/locations")
        mock_db_interface.get_locations.assert_called_once_with(node_ids=["all"])
        assert response.status_code == 200

    # Test failure with no results, when specific node_id has been specified.
    with mock.patch(
        "sapient_apex_api.controller.router.db_interface", mock.MagicMock()
    ) as mock_db_interface:
        response = client.get("/locations", params={"node_ids": ["1234"]})
        mock_db_interface.get_locations.assert_called_once_with(node_ids=["1234"])
        assert response.status_code == 400


def test_get_field_of_views():
    # Test failure with no database interface
    response = client.get("/field_of_views")
    assert response.status_code == 503
    # Test success with "all" node_ids
    with mock.patch(
        "sapient_apex_api.controller.router.db_interface", mock.MagicMock()
    ) as mock_db_interface:
        response = client.get("/field_of_views")
        mock_db_interface.get_field_of_views.assert_called_once_with(node_ids=["all"])
        assert response.status_code == 200

    # Test failure with no results, when specific node_id has been specified.
    with mock.patch(
        "sapient_apex_api.controller.router.db_interface", mock.MagicMock()
    ) as mock_db_interface:
        response = client.get("/field_of_views", params={"node_ids": ["1234"]})
        mock_db_interface.get_field_of_views.assert_called_once_with(node_ids=["1234"])
        assert response.status_code == 400

    # Test responses are parsed as expected
    fovs = [
        NodeFieldOfViewResponse(
            node_id="a",
            timestamp="time",
            field_of_view=LocationOrRangeBearing(range_bearing=RangeBearingCone()),
        )
    ]
    with (
        mock.patch.object(ElasticInterface, "get_field_of_views", return_value=fovs),
        mock.patch(
            "sapient_apex_api.controller.router.db_interface",
            ElasticInterface({}, _start_op_thread=False),
        ),
    ):
        response = client.get("/field_of_views")
    assert response.status_code == 200
    assert [NodeFieldOfViewResponse(**item) for item in response.json()] == fovs


def test_get_detections():
    # Test failure with no database interface
    response = client.get("/detections")
    assert response.status_code == 503

    # Test success with "all" node_ids
    with mock.patch(
        "sapient_apex_api.controller.router.db_interface", mock.MagicMock()
    ) as mock_db_interface:
        response = client.get("/detections")
        mock_db_interface.get_detections.assert_called_once()
        assert response.status_code == 200


def test_get_detections_locations():
    # Test failure with no database interface
    response = client.get("/detections/locations")
    assert response.status_code == 503

    # Test that db interface is exercised
    with mock.patch(
        "sapient_apex_api.controller.router.db_interface", mock.MagicMock()
    ) as mock_db_interface:
        response = client.get("/detections/locations")
        mock_db_interface.get_detections_locations.assert_called_once()
        assert response.status_code == 200


def test_get_detections_associated_files():
    # Test failure with no database interface
    response = client.get("/detections/associated_files")
    assert response.status_code == 503

    # Test that db interface is exercised
    with mock.patch(
        "sapient_apex_api.controller.router.db_interface", mock.MagicMock()
    ) as mock_db_interface:
        response = client.get("/detections/associated_files")
        mock_db_interface.get_detections_associated_files.assert_called_once()
        assert response.status_code == 200


def test_get_node_definitions():
    expected = [
        NodeDefinitionResponse(
            node_id="a",
            timestamp="time",
            node_definition=[
                NodeDefinition(
                    node_type=NodeDefinition.NodeType.NODE_TYPE_LIDAR, node_sub_type=["a"]
                ),
                NodeDefinition(node_type="NODE_TYPE_JAMMER", node_sub_type=["a"]),
            ],
        ),
        NodeDefinitionResponse(
            node_id="b",
            timestamp="time",
            node_definition=[NodeDefinition(node_type=5)],
        ),
    ]
    with (
        mock.patch.object(ElasticInterface, "get_node_definitions", return_value=expected),
        mock.patch(
            "sapient_apex_api.controller.router.db_interface",
            ElasticInterface({}, _start_op_thread=False),
        ),
    ):
        response = client.get("/node_definitions")
    assert response.status_code == 200
    assert [NodeDefinitionResponse(**data) for data in response.json()] == expected
    assert (
        response.json()[0]["node_definition"][0]["node_type"]
        == expected[0].node_definition[0].node_type.name
    )


if __name__ == "__main__":
    pytest.main()
