#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import time
from datetime import datetime, timedelta
from os import environ
from pathlib import Path
from queue import Queue
from random import choice, choices
from typing import Optional, Sequence, Union
from unittest import mock

import pytest
import ulid
from dotenv import dotenv_values
from elastic_transport import ApiResponseMeta, HeadApiResponse, HttpHeaders, NodeConfig
from elasticsearch.helpers import bulk
from google.protobuf.json_format import MessageToDict

from sapient_apex_api.interface.elastic_interface import (
    ElasticInterface,
    message_template,
)
from sapient_apex_api.response_models import NodeDefinition, NodeDefinitionResponse
from sapient_apex_server.structures import DatabaseOperation
from sapient_apex_server.time_util import datetime_to_pb, datetime_to_str
from sapient_msg.latest.registration_pb2 import Registration
from sapient_msg.latest.sapient_message_pb2 import SapientMessage


@pytest.fixture
def dotenv():
    """Dotenv file read by docker compose."""
    basedir = Path(__file__).parent
    assert (basedir / "docker-compose.yml").exists()
    dotenv = dotenv_values(basedir / ".env")
    directory = Path(dotenv.get("CREDENTIALS_DIR") or "")
    if not directory.is_absolute():
        dotenv["CREDENTIALS_DIR"] = str(
            (basedir / (dotenv["CREDENTIALS_DIR"] or ".env")).absolute()
        )

    return {**dotenv, **environ}


@pytest.fixture
def mock_es_config(dotenv: dict):
    return {
        "host": dotenv.get("ELASTIC_HOSTNAME", "localhost"),
        "port": dotenv["ES_PORT"],
        "useSsl": True,
        "certLocation": "ca.crt",
        "user": "elastic",
        "password": dotenv["ELASTIC_PASSWORD"],
    }


@pytest.fixture
def es_certificate(dotenv):
    for certificate in (
        Path(dotenv["CREDENTIALS_DIR"]) / "es-ca.crt",
        Path(dotenv["CREDENTIALS_DIR"]) / "ca" / "ca.crt",
        Path("C:\\elasticsearch-8.11.1\\config\\certs\\http_ca.crt"),
    ):
        if certificate.exists():
            return certificate

    pytest.skip(reason="Missing certificate for elastic-search")


@pytest.fixture
def es_config(mock_es_config, es_certificate):
    es_config = mock_es_config.copy()
    es_config["certLocation"] = str(es_certificate)
    return es_config


@pytest.fixture
def interface(es_config, index: str):
    interface = ElasticInterface(es_config, index=index, _start_op_thread=False)

    if not interface.es.ping():
        pytest.skip("Elastic search cluster is not running")

    interface.thread.start()

    if not wait_for_index(interface, index):
        raise RuntimeError(f"Could not create index {index}")

    yield interface

    interface.es.indices.delete(index=index)

    interface.stop()
    interface.join()


@pytest.fixture
def index() -> str:
    return "testindex-" + ulid.new().str.lower()


class TestElasticInterface:
    message_queue: Queue
    interface: ElasticInterface

    @pytest.fixture(autouse=True)
    def cleanup_interface(self):
        yield

        if self.interface:
            self.interface.stop()
            self.interface.join()

    def start_elastic(self, index_exists: bool, index: str):
        with (
            mock.patch("elasticsearch.client.IndicesClient.create") as mocked_index_create,
            mock.patch("elasticsearch.client.IndicesClient.exists") as mocked_index_exists,
        ):
            mocked_index_exists.return_value = HeadApiResponse(
                ApiResponseMeta(
                    200 if index_exists else 404, "1", HttpHeaders(), 0.02, NodeConfig("", "", 1000)
                )
            )
            es_config = {
                "host": "localhost",
                "port": 9200,
                "useSsl": True,
                "certLocation": "C:\\elasticsearch-8.11.1\\config\\certs\\http_ca.crt",
                "user": "elastic",
                "password": "password",
            }
            self.interface = ElasticInterface(
                es_config,
                index=index,
            )
            time.sleep(1)  # wait for bit for the ElasticInterface threads to spin up
            mocked_index_exists.assert_called_once_with(index=index)
            if index_exists:
                mocked_index_create.assert_not_called()
            else:
                mocked_index_create.assert_called_once_with(index=index, mappings=message_template)

    def _create_queue_message(self, operation: DatabaseOperation, index: str, message: dict):
        return {"operation": operation, "index": index, "data": message}

    def test_insert_into(self, index: str):
        self.start_elastic(True, index)
        # Stop the thread in the interface so that we can just test the insert function
        self.interface.stop()
        self.interface.join()

        test_dict = {"test": "test"}
        self.interface.insert_into("testIndex", test_dict)
        assert not self.interface.message_queue.empty()
        message = self.interface.message_queue.get_nowait()
        assert message == self._create_queue_message(
            DatabaseOperation.CREATE, "testIndex", test_dict
        )

    def test_startup_index_exists(self, index):
        self.start_elastic(True, index)

    def test_startup_no_index(self, index):
        self.start_elastic(False, index)

    def test_create_message(self, index):
        self.start_elastic(True, index)
        create_message_request = {
            "node_id": "1234",
            "destination_id": "5678",
            "timestamp": datetime_to_str(datetime.utcnow()),
            "message_type": "registration",
            "message": {"test": "test"},
        }
        with mock.patch("elasticsearch.Elasticsearch.index") as mocked_insert:
            self.interface.message_queue.put(
                self._create_queue_message(DatabaseOperation.CREATE, index, create_message_request)
            )
            time.sleep(0.5)
            mocked_insert.assert_called_once_with(index=index, document=create_message_request)

    # Testing/Mocking the Elastic DB messages & searches is a TODO
    # Via ElasticMock (does not support elastic v8 !) or similar


def wait_for_index(interface: ElasticInterface, index: str, /, exists: bool = True) -> bool:
    for _ in range(100):
        if interface.es.indices.exists(index=index) == exists:
            return True
        time.sleep(0.1)
    return False


def wait_for_document_count(interface: ElasticInterface, index: str, /, n: int = -1) -> bool:
    if wait_for_index(interface, index, exists=True):
        for _ in range(100):
            count = interface.es.count(index=index).get("count", None)
            if count is not None and ((n < 0 and count > 0) or count == n):
                return True
            time.sleep(0.1)
    return False


def wait_for_any_document(interface: ElasticInterface, index: str) -> bool:
    return wait_for_document_count(interface, index, n=-1)


def random_delta(days: Union[int, Sequence[int]] = 10):
    if isinstance(days, int):
        days = range(days)
    return timedelta(days=choice(days), hours=choice(range(23)), minutes=choice(range(60)))


def random_ids(n: int):
    int_ids = [str(u) for u in set(choices(range(n * 4), k=n))][: n // 2]
    ulids = [ulid.new().str for _ in range(n - len(int_ids))]
    return int_ids + ulids


def random_message(index: str, node_id: str, now: Optional[datetime] = None, **kwargs) -> dict:
    now = now or datetime.utcnow()
    kwargs["timestamp"] = kwargs.pop("timestamp", now - random_delta())

    result = {
        "_index": index,
        "node_id": node_id,
        "destination_id": choice(range(1, 1000)),
        "message_type": choice(("registration", "status_report", "registration_ack")),
        **kwargs,
    }

    if result["message_type"] == "registration":
        message = random_registration(node_id=node_id, **kwargs)
        jsonlike = MessageToDict(message, preserving_proto_field_name=True)
        result["message"] = jsonlike["registration"]
    return result


def random_registration(**kwargs):
    adjectives = ["allergic", "bright", "blue", "barking"]
    names = ["penguin", "rhino", "florida-man"]
    return SapientMessage(
        registration=Registration(
            name=kwargs.get("name", choice(adjectives) + " " + choice(names)),
            short_name=kwargs.get("short_name", choice(" abcdefjhijklmnop").strip()),
            node_definition=[random_node_definition(**kwargs)],
            icd_version=kwargs.get("icd_version", "TEST_ICD_V999"),
        ),
        node_id=kwargs.get("node_id", ulid.new().str),
        destination_id=kwargs.get("destination_id", ulid.new().str),
        timestamp=datetime_to_pb(kwargs.get("timestamp", datetime.utcnow())),
    )


def random_node_definition(**kwargs):
    return Registration.NodeDefinition(
        node_type=kwargs.get("node_type", choice(Registration.NodeType.values())),
        node_sub_type=choice([[], choices("abcdef", k=2)]),
    )


def test_create_real_message(interface: ElasticInterface, index: str):
    assert interface.es.indices.exists(index=index)
    assert interface.es.count(index=index).get("count", 1) == 0

    create_message_request = {
        "node_id": "1234",
        "destination_id": "5678",
        "timestamp": datetime_to_str(datetime.utcnow()),
        "message_type": "registration",
        "message": {"test": "test"},
    }
    interface.message_queue.put(
        {
            "operation": DatabaseOperation.CREATE,
            "index": index,
            "data": create_message_request,
        }
    )
    assert wait_for_any_document(interface, index)
    assert interface.es.count(index=index).get("count", 0) == 1


def test_get_number_of_nodes(interface: ElasticInterface, index: str, ndocs: int = 500):
    ids = random_ids(ndocs)
    bulk(
        interface.es,
        (random_message(index, node_id, message_type="registration") for node_id in ids),
    )
    bulk(
        interface.es,
        (random_message(index, node_id) for node_id in ids for _ in range(9)),
    )
    assert wait_for_document_count(interface, index, n=10 * len(ids))
    assert interface.get_number_of_nodes() == len(ids)


def test_get_latest_registrations(interface: ElasticInterface, index: str, ndocs: int = 500):
    now = datetime.now()
    registrations = {
        node_id: random_message(
            index,
            node_id,
            timestamp=now - random_delta() - timedelta(days=100),
            message_type="registration",
        )
        for node_id in random_ids(ndocs)
    }

    bulk(interface.es, registrations.values())
    # newer messages -- none of which are registration
    bulk(
        interface.es,
        (
            random_message(
                index,
                node_id,
                timestamp=data["timestamp"] + random_delta(days=99),
                message_type=choice(("status_report", "registration_ack")),
            )
            for node_id, data in registrations.items()
            for _ in range(4)
        ),
    )
    # older messages -- some of which are registration
    bulk(
        interface.es,
        (
            random_message(
                index,
                node_id,
                timestamp=data["timestamp"] - random_delta(days=99),
            )
            for node_id, data in registrations.items()
            for _ in range(5)
        ),
    )
    assert wait_for_document_count(interface, index, n=10 * len(registrations))
    assert interface.get_number_of_nodes() == len(registrations)

    # Get latest registration messages and check against expected results
    results = interface.get_latest_registration_messages()
    results = {
        r["node_id"]: {**r, "_index": index, "timestamp": datetime.fromisoformat(r["timestamp"])}
        for r in results
    }
    assert results == registrations


def test_get_node_definitions(interface: ElasticInterface, index: str, ndocs: int = 50):
    now = datetime.now()
    registrations = [
        random_message(
            index,
            node_id,
            timestamp=now - random_delta() - timedelta(days=100),
            message_type="registration",
        )
        for node_id in random_ids(ndocs)
    ]

    bulk(interface.es, registrations)
    bulk(
        interface.es,
        (
            random_message(
                index,
                node_id=data["node_id"],
                timestamp=data["timestamp"] - random_delta(days=99),
            )
            for data in registrations
            for _ in range(5)
        ),
    )
    assert wait_for_document_count(interface, index, n=6 * len(registrations))
    assert interface.get_number_of_nodes() == len(registrations)

    # Get latest registration messages and check against expected results
    expected = {
        data["node_id"]: NodeDefinitionResponse(
            node_id=data["node_id"],
            timestamp=datetime_to_str(data["timestamp"], quiet=True).replace(" ", "T"),
            node_definition=[
                NodeDefinition(**definition) for definition in data["message"]["node_definition"]
            ],
        )
        for data in registrations
    }
    assert len(expected) == len(registrations)

    definitions = interface.get_node_definitions()
    assert len(definitions) == len(registrations)
    comparison = {data.node_id: data for data in definitions}
    assert comparison == expected


if __name__ == "__main__":
    pytest.main()
