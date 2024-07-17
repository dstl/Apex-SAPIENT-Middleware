#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import logging
import xml.etree.ElementTree as ET

from google.protobuf.json_format import MessageToJson

from sapient_apex_server.time_util import datetime_to_str
from sapient_apex_server.translator.id_generator import IdGenerator
from sapient_apex_server.xml_conversion.to_xml import WhichFields, message_to_element
from sapient_msg.bsi_flex_335_v1_0.sapient_message_pb2 import SapientMessage

logger = logging.getLogger(__name__)


def translate(proto_message: SapientMessage, id_generator: IdGenerator) -> ET.Element:
    """Converts BSI FLEX 335 V1 Protobuf message to Sapient Version 6 XML message."""
    logger.debug(f"Converting message [{MessageToJson(proto_message)} to XML")

    # Step 1: perform the preprocessing to make the message easier to translate
    _proto_message_preprocessing(proto_message, id_generator)
    logger.debug(
        f"Completed protobuf message preprocessing of message [{MessageToJson(proto_message)}"
    )

    # Step 2: translate the message to XML
    message_type = proto_message.WhichOneof("content")
    message_content = getattr(proto_message, message_type)
    message_xml = message_to_element(
        message_content, proto_message.node_id, WhichFields.OFFICIAL, id_generator
    )
    logger.debug(
        f"Converted message [{MessageToJson(proto_message)}] "
        f"to XML message [{ET.tostring(message_xml)}]"
    )

    # Step 3: perform the postprocessing to get the message into a format that conforms with v6
    _translation_postprocessing(message_xml, proto_message, id_generator)

    logger.debug(
        f"Finished converting message [{MessageToJson(proto_message)}] to XML message "
        f"[{ET.tostring(message_xml)}]"
    )
    return message_xml


def _proto_message_preprocessing(proto_message: SapientMessage, id_generator: IdGenerator):
    """Get the protobuf message into a format that is similar to V6 XML protobuf messages."""

    for node_id in (proto_message.node_id, proto_message.destination_id):
        if node_id not in id_generator.node_id_map:
            id_generator.insert_new_ulid_id_pair(
                node_id,
                id_generator.get_next_id(),
                id_generator.node_id_map,
                True,
            )


def _translation_postprocessing(
    message_xml: ET.Element,
    proto_message: SapientMessage,
    id_generator: IdGenerator,
):
    """It is much easier to make adjustments to the message format when it is in
    XML as the XML messages don't have to conform to a schema. Make the changes necessary
    for the XML messages to be correctly read.
    """
    # Add timestamp to proto message
    timestamp_elem = ET.SubElement(message_xml, "timestamp")
    timestamp_elem.text = datetime_to_str(proto_message.timestamp.ToDatetime())

    # Handle translating node_id / destination_id to sourceID / sensorID
    if message_xml.tag in (
        "Alert",
        "AlertResponse",
        "DetectionReport",
        "StatusReport",
    ):
        # Add node_id to proto message as sourceID
        source_id_elem = ET.SubElement(message_xml, "sourceID")
        source_id_elem.text = str(id_generator.node_id_map[proto_message.node_id].xml_id)
    elif message_xml.tag in (
        "SensorTask",
        "SensorTaskACK",
    ):
        # Add destination_id to proto message as sensorID
        sensor_id_elem = ET.SubElement(message_xml, "sensorID")
        sensor_id_elem.text = str(id_generator.node_id_map[proto_message.destination_id].xml_id)
    else:
        # Add node_id to proto message as sensorID
        sensor_id_elem = ET.SubElement(message_xml, "sensorID")
        sensor_id_elem.text = str(id_generator.node_id_map[proto_message.node_id].xml_id)

    # Indent timestamp and id tags so that they appear on a new line when tostring is called
    ET.indent(message_xml)

    # Move locationList/rangeBearingCone out of regionArea and then remove regionArea
    if message_xml.tag in ["SensorTask"]:
        for region_elem in message_xml.findall("region"):
            region_area_elem = region_elem.find("regionArea")
            if (loc_list := region_area_elem.find("locationList")) is not None:
                region_elem.append(loc_list)
                region_area_elem.remove(loc_list)
            elif (rb_cone := region_area_elem.find("rangeBearingCone")) is not None:
                region_elem.append(rb_cone)
                region_area_elem.remove(rb_cone)
            region_elem.remove(region_area_elem)
    elif message_xml.tag == "DetectionReport":
        # v7 changed the subClass "value" field to a "type" field
        for subclass in message_xml.iter("subClass"):
            subclass.attrib["value"] = subclass.attrib["type"]
    elif message_xml.tag == "SensorRegistration":
        # nodeType isn't nested within a nodeDefinition in v6, move it to the outer registration
        # layer
        for node_def in message_xml.iter("nodeDefinition"):
            if (node_type := node_def.find("nodeType")) is not None:
                node_type_elem = ET.SubElement(message_xml, "nodeType")
                node_type_elem.text = node_type.text
            message_xml.remove(node_def)

        # Update LocationType fields so that the names are correct for v6
        for location_type in message_xml.iter("locationType"):
            if "locationUnits" in location_type.attrib.keys():
                location_type.attrib["units"] = location_type.attrib["locationUnits"]
                # Populate the locationType text to show the correct value
                location_type.text = "UTM" if location_type.attrib["units"] == "UTM" else "GPS"
                location_type.attrib["value"] = location_type.text
            if "locationDatum" in location_type.attrib.keys():
                location_type.attrib["datum"] = location_type.attrib["locationDatum"]
