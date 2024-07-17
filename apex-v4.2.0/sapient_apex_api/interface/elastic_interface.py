#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import logging
from datetime import datetime, timedelta
from queue import Queue
from threading import Thread
from typing import Any, Dict, Iterable, List

from elasticsearch import Elasticsearch, helpers
from elasticsearch.exceptions import ConnectionError as ElasticConnectionError

from sapient_apex_api.interface.base_interface import BaseInterface
from sapient_apex_api.response_models import (
    AssociatedFile,
    AssociatedFilesResponse,
    DetectionResponse,
    DetectionSource,
)
from sapient_apex_api.response_models import Location as LocationResponse
from sapient_apex_api.response_models import (
    LocationOrRangeBearing as LocationOrRangeBearingResponse,
)
from sapient_apex_api.response_models import (
    NodeDefinition,
    NodeDefinitionResponse,
    NodeFieldOfViewResponse,
    NodeLocationResponse,
)
from sapient_apex_api.response_protos import setattr_all
from sapient_apex_server.structures import DatabaseOperation

logger = logging.getLogger(__name__)

# Surpress elasticsearch logs:
tracer = logging.getLogger("elasticsearch")
tracer.setLevel(logging.ERROR)
tracer.addHandler(logging.FileHandler("indexer.log"))

logging.getLogger("elastic_transport.transport").setLevel(logging.ERROR)


message_template = {
    "properties": {
        "node_id": {"type": "keyword"},
        "destination_id": {"type": "keyword"},
        "timestamp": {"type": "date"},
        "message_type": {"type": "keyword"},
        "message": {
            "type": "object",
            # Turn off elastic indexing for the contents,
            # because when using Nodes between V6/BSI V1/V2
            # there will be fields which have changed their types
            # and makes elastic throw exceptions.
            # Its also likely that issue will be seen with optional fields
            # which all nodes may not provide.
            # The queries we currently use do not rely on message contents needing to
            # be indexed.
            "enabled": False,
        },
    }
}


class DefaultKeyword:
    """Tag for default keywords.

    Only usefull where `None` is a valid value and the default is a mutable value.
    """

    pass


class ElasticInterface(BaseInterface):
    def __init__(
        self, elastic_config: dict, index: str = "messages", _start_op_thread: bool = True
    ):
        self.message_queue = Queue()
        self.index = index
        hostname = (
            elastic_config.get("host", "localhost") + ":" + str(elastic_config.get("port", 9200))
        )
        if elastic_config.get("useSsl", True):
            self.es = Elasticsearch(
                hosts=["https://" + hostname],
                verify_certs=True,
                basic_auth=(
                    elastic_config.get("user", ""),
                    elastic_config.get("password", ""),
                ),
                ca_certs=elastic_config.get("certLocation", "./http_ca.crt"),
            )
        else:
            self.es = Elasticsearch(hosts=["http://" + hostname])
        self.thread = Thread(target=self.run)
        if _start_op_thread:
            self.thread.start()

    def insert_into(self, index: str, data: dict):
        queue_message = {
            "operation": DatabaseOperation.CREATE,
            "index": index,
            "data": data,
        }
        self.message_queue.put_nowait(queue_message)

    def scan(self, index: str, query: dict) -> Iterable[dict[str, Any]]:
        """Executes a scan query on the elastic database.
        Returns any found results as a generator object.

        Args:
            index (str): The index.
            query (dict): The query itself, in this case in the Elastic DSL format.

        Returns:
            Iterable[dict[str, Any]]: A generator object with the found results.
        """

        return helpers.scan(self.es, query=query)

    def search(
        self,
        index: str,
        query: dict,
        sort: Any = None,
        size: int = None,
    ) -> Any:
        """Executes a search query on the elastic database.
        Returned results, defaults to 10 elements and
        will needed to be scrolled if many elements are present or prefer using scan.

        Args:
            index (str): The index.
            query (dict): The query itself, in this case in the Elastic DSL format.
            sort (Any): The sort parameters, for elastic, this is a list of ':' separated
            pairs, defining the field_name:sort_order

        Returns:
            Any: The found results
        """

        return self.es.search(
            index=index,
            query=query,
            sort=sort,
            size=size,
            source=True,
        )

    def run(self):
        try:
            if not self.es.indices.exists(index=self.index):
                self.es.indices.create(index=self.index, mappings=message_template)
        except ElasticConnectionError:
            raise RuntimeError("Could not connect to Elasticsearch DB")

        while True:
            # wait and read a message from the queue
            message = self.message_queue.get()
            # process message
            if message["operation"] is DatabaseOperation.CREATE:
                logger.debug(
                    f"Inserting message [{message['data']}] into index [{message['index']}]"
                )
                self.es.index(index=message["index"], document=message["data"])
            elif message["operation"] is DatabaseOperation.SHUTDOWN:
                logger.info("Database thread shutting down...")
                return

    def stop(self):
        self.message_queue.put_nowait({"operation": DatabaseOperation.SHUTDOWN})

    def join(self):
        self.thread.join()

    def get_number_of_nodes(self, **kwargs) -> int:
        query = kwargs.pop("query", {"bool": {"must": {"term": {"message_type": "registration"}}}})
        result = self.es.search(
            index=self.index,
            aggs={"node_ids": {"cardinality": {"field": "node_id", "precision_threshold": 5000}}},
            query=query,
            **kwargs,
        )
        return int(result["aggregations"]["node_ids"]["value"])

    def get_node_definitions(self, **kwargs) -> list[NodeDefinitionResponse]:
        return [
            NodeDefinitionResponse(
                node_id=r["node_id"],
                timestamp=r["timestamp"],
                node_definition=[
                    NodeDefinition(**definition) for definition in r["message"]["node_definition"]
                ],
            )
            for r in self.get_latest_registration_messages(**kwargs)
        ]

    def get_latest_registration_messages(self, **kwargs) -> list:
        nbdocs = self.get_number_of_nodes()
        if nbdocs >= 5000:
            raise NotImplementedError("Too many documents to collapse")

        query = kwargs.pop("query", {"bool": {"must": {"term": {"message_type": "registration"}}}})
        result = self.es.search(
            index=self.index,
            query=query,
            collapse={"field": "node_id"},
            sort=["timestamp:desc"],
            size=nbdocs,
            **kwargs,
        )
        return [r["_source"] for r in result["hits"]["hits"]]

    def get_latest_status_report_message(self, node_id: str) -> tuple[str, str, dict[str, Any]]:
        full_node_id = ""
        timestamp: str = ""
        status_report_message = {}

        # We want to search for the latest status_report for this node_id, so setup the search
        # such that the result is ordered by timestamp, we take the first one.
        query = {
            "bool": {
                "must": [
                    {"match_phrase": {"message_type": "status_report"}},
                    {"match_phrase": {"node_id": node_id}},
                ]
            }
        }

        # Note: This is a normal elastic search, as the (scan)search appears to not support
        # sorting or limiting. As we expect only one message, scrolling/paging is not required.
        # Also note the sort parameter is a list of ':' separated pairs and not a dict,
        # which appears to be python specific elastic library implementation & not well
        # documented.
        sort = ["timestamp:desc"]

        status_report_results = self.search(
            index=self.index,
            query=query,
            sort=sort,
            size=1,
        )

        for status_report_result in status_report_results["hits"]["hits"]:
            full_node_id = status_report_result["_source"]["node_id"]
            timestamp = status_report_result["_source"]["timestamp"]
            status_report_message = status_report_result["_source"]["message"]

        return full_node_id, timestamp, status_report_message

    def get_detection_reports(
        self,
        node_id: str,
        detection_source: DetectionSource,
        detection_confidence: float,
        detection_classification: str,
        detection_from: datetime,
        detection_to: datetime,
        detection_interval: timedelta,
        detection_count: int,
    ) -> (str, str, List[Dict[str, Any]]):
        full_node_id = ""
        timestamp: str = ""
        detection_report_messages = []

        query = {
            "bool": {
                "must": [
                    {"match_phrase": {"message_type": "detection_report"}},
                    {"match_phrase": {"node_id": node_id}},
                    # Setting queries on non-elastic fields does not work
                    # These are handled manually after the query
                    # {
                    #     "range": {
                    #         "detection_report.detection_confidence": {
                    #             "gte": detection_confidence,
                    #             "lte": 1.0,
                    #         }
                    #     }
                    # },
                ]
            }
        }

        # Time filters
        if detection_interval != timedelta(0):
            current_time = datetime.now()
            previous_time = current_time - detection_interval
            query["bool"]["must"].append(
                {
                    "range": {
                        "timestamp": {
                            "gte": previous_time,
                            "lte": current_time,
                        }
                    }
                }
            )
        elif detection_from != datetime.min and detection_to != datetime.min:
            query["bool"]["must"].append(
                {
                    "range": {
                        "timestamp": {
                            "gte": detection_from,
                            "lte": detection_to,
                        }
                    }
                }
            )

        # Note: This is a normal elastic search, as the (scan)search appears to not support
        # sorting or limiting. As we expect only one message, scrolling/paging is not required.
        # Also note the sort parameter is a list of ':' separated pairs and not a dict,
        # which appears to be python specific elastic library implementation & not well
        # documented.
        sort = ["timestamp:desc"]

        detection_report_results = self.search(
            index="messages",
            query=query,
            sort=sort,
            size=detection_count,
        )

        for detection_report_result in detection_report_results["hits"]["hits"]:
            full_node_id = detection_report_result["_source"]["node_id"]
            timestamp = detection_report_result["_source"]["timestamp"]

            detection_report_message = detection_report_result["_source"]["message"]
            append_message = (
                float(detection_report_message.get("detection_confidence", -1))
                > detection_confidence
            )
            append_message &= (not detection_classification) or any(
                detection_classification in classification.get("type", [])
                for classification in detection_report_message.get("classification", {})
            )

            # If used by a fusion node, the “associated_detection” field shall represent a
            # list of individual sensor edge node detections that were used to
            # generate a fused detection.
            # So we will use this to determine if a particular detection report is
            # from a edge or fusion node.

            associated_detection = detection_report_message.get("associated_detection", [])
            if detection_source == DetectionSource.fused and not associated_detection:
                append_message = False  # Looking for fused, but this is a sensor detection
            elif detection_source == DetectionSource.edge and associated_detection:
                append_message = False  # Looking for edge, but found a fused detection

            if append_message:
                detection_report_messages.append(detection_report_message)

        return full_node_id, timestamp, detection_report_messages

    def get_registered_node_ids(self) -> list[str]:
        return [r["node_id"] for r in self.get_latest_registration_messages()]

    def get_locations(self, node_ids: list[str]) -> list[NodeLocationResponse]:
        """Get the (list of) NodeLocationResponse

        Args:
            node_ids (list[str]): The node_ids, defaults to empty list/all nodes.

        Returns:
            list[NodeLocationResponse]: NodeLocationResponse
        """

        # Run two types of searches on the database
        # 1. Search all registration messages to get the node_ids & store unique values.
        # 2. Use these node_ids to search for the latest status_report for each.
        # and populate the NodeLocationResponse list

        registered_node_ids = (
            self.get_registered_node_ids() if node_ids and "all" in node_ids else node_ids
        )

        node_locations: list[NodeLocationResponse] = []
        for node_id in registered_node_ids:
            full_node_id, timestamp, status_report_message = self.get_latest_status_report_message(
                node_id=node_id
            )

            if "node_location" in status_report_message:
                node_location = LocationResponse()
                setattr_all(node_location, status_report_message["node_location"])

                node_locations.append(
                    NodeLocationResponse(
                        node_id=full_node_id,
                        timestamp=timestamp,
                        node_location=node_location,
                    ),
                )

        return node_locations

    def get_field_of_views(self, node_ids: list[str]) -> list[NodeFieldOfViewResponse]:
        """Get the (list of) NodeFieldOfViewResponse

        Args:
            node_ids (list[str]): The node_ids, defaults to empty list/all nodes.

        Returns:
            list[NodeFieldOfViewResponse]: NodeFieldOfViewResponse
        """

        # Run two types of searches on the database
        # 1. Search all registration messages to get the node_ids & store unique values.
        # 2. Use these node_ids to search for the latest status_report for each.
        # and populate the NodeLocationResponse list

        registered_node_ids = (
            self.get_registered_node_ids() if node_ids and "all" in node_ids else node_ids
        )
        node_field_of_views: list[NodeFieldOfViewResponse] = []
        for node_id in registered_node_ids:
            full_node_id, timestamp, status_report_message = self.get_latest_status_report_message(
                node_id=node_id,
            )

            if "field_of_view" in status_report_message:
                node_field_of_view = LocationOrRangeBearingResponse()
                setattr_all(node_field_of_view, status_report_message["field_of_view"])

                node_field_of_views.append(
                    NodeFieldOfViewResponse(
                        node_id=full_node_id,
                        timestamp=timestamp,
                        field_of_view=node_field_of_view,
                    ),
                )

        return node_field_of_views

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
        """Gets (a list of) detections.

        Args:
            node_ids (list[str]): The node_ids, defaults to empty list/all nodes.
            detection_source (DetectionSource): Source of detection.
            detection_confidence (float): confidence value to filter on (above)
            detection_classification (str): classification
            detection_from (datetime): from timestamp
            detection_to (datetime): to timestamp
            detection_interval (timedelta): delta time from current
            detection_count (int): number of messages to retrieve per node_id

        Returns:
            list[DetectionResponse]: DetectionResponse
        """

        registered_node_ids = (
            self.get_registered_node_ids() if node_ids and "all" in node_ids else node_ids
        )

        detection_reponses: list[DetectionResponse] = []
        for node_id in registered_node_ids:
            full_node_id, timestamp, detection_report_messages = self.get_detection_reports(
                node_id=node_id,
                detection_source=detection_source,
                detection_confidence=detection_confidence,
                detection_classification=detection_classification,
                detection_from=detection_from,
                detection_to=detection_to,
                detection_interval=detection_interval,
                detection_count=detection_count,
            )

            for detection_report_message in detection_report_messages:
                detection_reponses.append(
                    DetectionResponse(
                        node_id=full_node_id,
                        timestamp=timestamp,
                        detection_report=detection_report_message,
                    ),
                )

        return detection_reponses

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
        """Gets (a list of) locations for detections.

        Args:
            node_ids (list[str]): The node_ids, defaults to empty list/all nodes.
            detection_source (DetectionSource): Source of detection.
            detection_confidence (float): confidence value to filter on (above)
            detection_classification (str): classification
            detection_from (datetime): from timestamp
            detection_to (datetime): to timestamp
            detection_interval (timedelta): delta time from current
            detection_count (int): number of messages to retrieve per node_id

        Returns:
            list[NodeLocationResponse]: NodeLocationResponse
        """
        registered_node_ids = (
            self.get_registered_node_ids() if node_ids and "all" in node_ids else node_ids
        )

        detection_locations: list[NodeLocationResponse] = []
        for node_id in registered_node_ids:
            full_node_id, timestamp, detection_report_messages = self.get_detection_reports(
                node_id=node_id,
                detection_source=detection_source,
                detection_confidence=detection_confidence,
                detection_classification=detection_classification,
                detection_from=detection_from,
                detection_to=detection_to,
                detection_interval=detection_interval,
                detection_count=detection_count,
            )

            for detection_report_message in detection_report_messages:
                if "location" in detection_report_message:
                    detection_location = LocationResponse()
                    setattr_all(detection_location, detection_report_message["location"])

                    detection_locations.append(
                        NodeLocationResponse(
                            node_id=full_node_id,
                            timestamp=timestamp,
                            node_location=detection_location,
                        ),
                    )

        return detection_locations

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
        """Gets (a list of) associated files for detections.

        Args:
            node_ids (list[str]): The node_ids, defaults to empty list/all nodes.
            detection_source (DetectionSource): Source of detection.
            detection_confidence (float): confidence value to filter on (above)
            detection_classification (str): classification
            detection_from (datetime): from timestamp
            detection_to (datetime): to timestamp
            detection_interval (timedelta): delta time from current
            detection_count (int): number of messages to retrieve per node_id

        Returns:
            list[AssociatedFilesResponse]: AssociatedFilesResponse
        """
        registered_node_ids = (
            self.get_registered_node_ids() if node_ids and "all" in node_ids else node_ids
        )

        detection_associated_files_response: list[AssociatedFilesResponse] = []
        for node_id in registered_node_ids:
            full_node_id, timestamp, detection_report_messages = self.get_detection_reports(
                node_id=node_id,
                detection_source=detection_source,
                detection_confidence=detection_confidence,
                detection_classification=detection_classification,
                detection_from=detection_from,
                detection_to=detection_to,
                detection_interval=detection_interval,
                detection_count=detection_count,
            )

            for detection_report_message in detection_report_messages:
                if "associated_file" in detection_report_message:
                    detection_associated_files: [AssociatedFile] = []
                    for the_associated_file in detection_report_message["associated_file"]:
                        detection_associated_file = AssociatedFile()
                        setattr_all(
                            detection_associated_file,
                            the_associated_file,
                        )

                        detection_associated_files.append(detection_associated_file)

                    detection_associated_files_response.append(
                        AssociatedFilesResponse(
                            node_id=full_node_id,
                            timestamp=timestamp,
                            associated_files=detection_associated_files,
                        ),
                    )

        return detection_associated_files_response
