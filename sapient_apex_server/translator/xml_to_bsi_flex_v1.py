#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import copy
import itertools
import logging
import uuid
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple

import ulid
from google.protobuf.descriptor import Descriptor
from google.protobuf.json_format import MessageToJson
from google.protobuf.message import Message

from sapient_apex_server.translator.id_generator import IdGenerator, SensorIdMapping
from sapient_apex_server.xml_conversion.from_xml import Converter
from sapient_apex_server.xml_conversion.naming import get_enum_value_xml_name
from sapient_msg.bsi_flex_335_v1_0.registration_pb2 import Registration
from sapient_msg.bsi_flex_335_v1_0.sapient_message_pb2 import SapientMessage

logger = logging.getLogger(__name__)


class ToProtoTranslator:
    def __init__(self):
        self.converter = Converter(SapientMessage, False)

    def _populate_region(
        self, xml_message: ET.Element, xml_region_name: str, proto_region_name: str
    ):
        """
        Move locationList/rangeBearingCone into a new element nested inside of the
        xml_region_name element.

        Example
        -------
        Old Region:
            <region>
              <locationList>
                ...
              </locationList>
            </region>

        New Region:
            <region>
              <regionArea>
                <locationList>
                  ...
                </locationList>
              </regionArea>
            </region>
        """
        # Wrap region location/range bearing in a region tag
        for xml_region in xml_message.findall(xml_region_name):
            region_elem = ET.SubElement(xml_region, proto_region_name)
            if (loc_list := xml_region.find("locationList")) is not None:
                region_elem.append(loc_list)
                xml_region.remove(loc_list)
            else:
                rb_cone = xml_region.find("rangeBearingCone")
                region_elem.append(rb_cone)
                xml_region.remove(rb_cone)

    def _get_message_ulid(
        self, xml_message: ET.Element, id_generator: IdGenerator
    ) -> (str, List[str]):
        """Get the corresponding UUID to the integer ID from the XML message.

        This will only create an new ID/UUID pair if the message type is a registration message. If
        there isn't already an ID/UUID pair and the message type isn't a registration, then an error
        will be returned.
        """
        # First, obtain the integer ID from either the sourceID or sensorID element
        if (source_id_elem := xml_message.find("sourceID")) is not None:
            message_id = int(source_id_elem.text)
            xml_message.remove(source_id_elem)
        else:
            sensor_id_elem = xml_message.find("sensorID")
            message_id = int(sensor_id_elem.text)
            xml_message.remove(sensor_id_elem)
        # Next, get the corresponding UUID for that integer ID
        # (create one if the message is a registration)
        if message_id in map(
            lambda x: x.xml_id if hasattr(x, "xml_id") else x,
            id_generator.node_id_map.values(),
        ):
            node_id = id_generator.get_ulid_from_id(id_generator.node_id_map, message_id)
        elif xml_message.tag == "SensorRegistration":
            node_id = str(uuid.uuid4())
            id_generator.node_id_map[node_id] = SensorIdMapping(message_id)
        else:
            return "", [f"Sensor with ID [{message_id}] has no corresponding ULID."]
        return node_id, []

    def _get_enum_names(self, message_desc: Descriptor) -> Dict[str, List[str]]:
        """Get the enum names for the specified enum.

        Returns a map where the key is the v7 name of the enum field and the value is a list
        of the string representation of each of the enum values in that enum.
        """
        enum_map = {}
        for field in message_desc.fields:
            if field.enum_type is not None:
                enum_names = []
                for enum_value_desc in field.enum_type.values:
                    enum_names.append(get_enum_value_xml_name(enum_value_desc))
                enum_map[field.camelcase_name] = enum_names
        return enum_map

    def _add_location_type_field(
        self, location_type: ET.Element, location_type_enum_names: dict, field_name: str
    ):
        """Convert locationType fields into their v7 equivalant.

        v6 locationType had the units and datum fields as a generic string, whereas v7 has
        them each as a oneof that differs depending on whether the locationType is location
        or rangeBearing. This function determines whether the enum should be location or
        rangeBearing by looking at the specific enum values and seeing whether the XML
        version matches the location or rangeBearing version.

        Example
        -------
        Old message:
        <locationType units="UTM" datum="WGS84 Geoid" />

        New message:
        <locationType locationUnits="UTM" locationDatum="WGS84 Geoid" />
        """
        elem_name = None
        for translated_field_name, enum_names in location_type_enum_names.items():
            if location_type.attrib[field_name] in enum_names:
                elem_name = translated_field_name
        if elem_name is not None:
            location_type.attrib[elem_name] = location_type.attrib[field_name]
            location_type.attrib.pop(field_name)

    def _fix_completion_time(
        self,
        command_elem: ET.Element,
        attrib_name: str,
        completion_time_attrib_name: str,
        completion_time_elem: Optional[ET.Element],
    ) -> ET.Element:
        """Nest the completion time's units and value fields inside of a completionTime
        element to match the v7 message.

        Example
        -------
        Old message:
        <command completionTimeUnits="Seconds" completionTime="10" />

        New message:
        <command>
          <completionTime units="Seconds" value="10" />
        </command>
        """
        if attrib_name in command_elem.attrib:
            if completion_time_elem is None:
                completion_time_elem = ET.SubElement(command_elem, "completionTime")
            completion_time_elem.attrib[completion_time_attrib_name] = command_elem.attrib[
                attrib_name
            ]
            command_elem.attrib.pop(attrib_name)

        return completion_time_elem

    def _populate_registration_fields(self, xml_message: ET.Element):
        """Perform necessary changes to make an XML registration look like the Protobuf format.

        See individual functions to learn what changes are made.
        """
        # Move nodeType fields to be nested within a nodeDefinition tag
        if len((node_types := xml_message.findall("nodeType"))) > 0:
            node_def_elem = ET.SubElement(xml_message, "nodeDefinition")
            for node_type in node_types:
                node_def_elem.append(node_type)
                xml_message.remove(node_type)

        # Change units and datum attributes in all locationType fields to be
        # subelements of locationType
        location_type_enum_names = self._get_enum_names(Registration.LocationType.DESCRIPTOR)
        for location_type in xml_message.iter("locationType"):
            # v6 only had WGS84 (no Ellipsoid or Geoid). Always assume Ellipsoid
            location_type.attrib["datum"] = "WGS84 Ellipsoid"
            self._add_location_type_field(location_type, location_type_enum_names, "units")
            self._add_location_type_field(location_type, location_type_enum_names, "datum")

            # Also remove the text from the element
            location_type.text = None

        # Move units attribute in <confidence units="" /> to an attribute for
        # classDefinition/subClassDefinition (parent of confidence element)
        for class_def in itertools.chain(
            xml_message.iter("classDefinition"),
            xml_message.iter("subClassDefinition"),
            xml_message.iter("behaviourDefinition"),
        ):
            if (confidence := class_def.find("confidence")) is not None:
                class_def.attrib["units"] = confidence.attrib["units"]
                class_def.remove(confidence)

        command_type_enum_names = [
            u.title() for u in self._get_enum_names(Registration.Command.DESCRIPTOR)["type"]
        ]
        for command in xml_message.iter("command"):
            # change <command completionTime="" completionTimeUnits="" /> to be
            # <command><completionTime units="" value="" /></command>
            completion_time_elem = self._fix_completion_time(
                command, "completionTime", "value", None
            )
            self._fix_completion_time(command, "completionTimeUnits", "units", completion_time_elem)
            if command.attrib["name"].title() in command_type_enum_names:
                command.attrib["type"] = command.attrib["name"].title()
            else:
                command.attrib["type"] = "Request"

        # remove performanceValue elements from inside of classPerformance element
        for class_performance in xml_message.iter("classPerformance"):
            class_performance.attrib["value"] = class_performance.attrib["unitValue"]
            del class_performance.attrib["unitValue"]
            for performance_value in class_performance.findall("performanceValue"):
                class_performance.remove(performance_value)

        # Migrate performanceValue into detection_performance and
        # remove performanceValue elements from inside of detectionPerformance element
        for detection_definition in xml_message.iter("detectionDefinition"):
            new_detection_performances = []
            for detection_performance in detection_definition.iter("detectionPerformance"):
                for performance_value in detection_performance.findall("performanceValue"):
                    new_detection_performance = copy.deepcopy(detection_performance)
                    new_detection_performance.attrib["type"] = performance_value.attrib["type"]
                    new_detection_performance.attrib["value"] = performance_value.attrib["value"]
                    new_detection_performances.append(new_detection_performance)

                detection_definition.remove(detection_performance)

            if new_detection_performances:
                for new_element in new_detection_performances:
                    _ = ET.SubElement(
                        detection_definition,
                        "detectionPerformance",
                        new_element.attrib,
                    )

        # Set performanceValue.unit to be the same as performanceValue.type
        for performance_value in xml_message.iter("performanceValue"):
            performance_value.attrib["units"] = performance_value.attrib["type"]

        # v6 defines all attributes of the Capabilities element to start with an upper case letter
        # to support both upper and lower case, convert all Capabilities attributes to lower case
        for capability in xml_message.iter("capabilities"):
            capability.attrib = {key.lower(): value for key, value in capability.attrib.items()}

    def _xml_message_preprocessing(self, xml_message: ET.Element, id_generator: IdGenerator):
        """Get the XML message into a format similar to SapientMessage, so it is easy to parse."""
        xml_msg_copy = copy.deepcopy(
            xml_message
        )  # Create a copy of the xml message so that the original doesn't change
        # Step 1: wrap XML in:
        # <SapientMessage><timestamp>...</timestamp><nodeId>...</nodeId></SapientMessage>
        parent_elem = ET.Element("SapientMessage")
        timestamp_elem = ET.SubElement(parent_elem, "timestamp")
        original_timestamp_elem = xml_msg_copy.find("timestamp")
        timestamp_elem.text = original_timestamp_elem.text
        xml_msg_copy.remove(original_timestamp_elem)

        node_id, errs = self._get_message_ulid(xml_msg_copy, id_generator)
        if len(errs) > 0:
            return xml_msg_copy, errs

        id_elem = ET.SubElement(parent_elem, "nodeId")
        id_elem.text = node_id

        parent_elem.append(xml_msg_copy)
        # Step 2: perform message specific preprocessing
        if xml_msg_copy.tag == "SensorRegistration":
            self._populate_registration_fields(xml_msg_copy)
            # Add icd version
            if xml_msg_copy.find("icdVersion") is None:
                icd_version_elem = ET.SubElement(xml_msg_copy, "icdVersion")
                icd_version_elem.text = "BSI Flex 335 v1.0"
            # Add node definition
            if xml_msg_copy.find("nodeDefinition") is None:
                node_def_elem = ET.SubElement(xml_msg_copy, "nodeDefinition")
                node_type_elem = ET.SubElement(node_def_elem, "nodeType")
                node_type_elem.text = "Other"
                node_sub_type_elem = ET.SubElement(node_def_elem, "nodeSubType")
                node_sub_type_elem.text = xml_msg_copy.find("sensorType").text

        elif xml_msg_copy.tag == "StatusReport":
            self._populate_region(xml_msg_copy, "statusRegion", "region")
            for status_region in xml_msg_copy.findall("statusRegion"):
                xml_msg_copy.remove(status_region)
        elif xml_msg_copy.tag == "DetectionReport":
            # remove value attribute from subclass
            for classification in xml_msg_copy.findall("class"):
                for sub_class in classification.findall("subClass"):
                    del sub_class.attrib["value"]
        elif xml_msg_copy.tag == "Alert":
            # Assume all alerts being sent are from DMM -> ASM (or DMM -> Apex)
            id_elem.text = id_generator.get_ulid_from_id(id_generator.node_id_map, 0)
            dest_id_elem = ET.SubElement(parent_elem, "destinationId")
            dest_id_elem.text = node_id
            # Remove location and description fields from AssociatedDetection
            for assoc_detection in xml_msg_copy.findall("associatedDetection"):
                assoc_detection.remove(assoc_detection.find("location"))
                assoc_detection.remove(assoc_detection.find("description"))
        elif xml_msg_copy.tag == "SensorTask":
            self._populate_region(xml_msg_copy, "region", "regionArea")
            id_elem.text = id_generator.get_ulid_from_id(id_generator.node_id_map, 0)
            dest_id_elem = ET.SubElement(parent_elem, "destinationId")
            dest_id_elem.text = node_id
            # We want the task ID to be associated with the ASM as well as the DMM, so add
            # the ID to the ASM's task_id_map
            task_ulid = ulid.new().str
            id_generator.insert_new_ulid_id_pair(
                task_ulid,
                int(xml_msg_copy.find("taskID").text),
                id_generator.node_id_map[node_id].task_id_map,
                id_generator.is_node_id_map("task_id"),
            )
            id_generator.insert_new_ulid_id_pair(
                task_ulid,
                int(xml_msg_copy.find("taskID").text),
                id_generator.node_id_map[id_elem.text].task_id_map,
                id_generator.is_node_id_map("task_id"),
            )
            # Make sure that the commandParameter contains the objectID, if the objectID is
            # specified
            if (command_elem := xml_msg_copy.find("command")) is not None:
                if (object_id_elem := command_elem.find("objectID")) is not None:
                    command_param_elem = ET.SubElement(command_elem, "commandParameter")
                    command_param_elem.text = id_generator.get_ulid_from_id(
                        id_generator.node_id_map, int(object_id_elem.text)
                    )
                    command_elem.remove(object_id_elem)

        # We don't know the coordinate system or datum of any locations that are sent in any XML
        # messages, so set them all to unspecified
        for location in itertools.chain(
            xml_msg_copy.iter("location"),
            xml_msg_copy.iter("rangeBearing"),
            xml_msg_copy.iter("rangeBearingCone"),
        ):
            if location.find("coordinateSystem") is None:
                coordinate_system = ET.SubElement(location, "coordinateSystem")
                coordinate_system.text = "Unspecified"
            if location.find("datum") is None:
                datum = ET.SubElement(location, "datum")
                datum.text = "Unspecified"

        ET.indent(parent_elem)
        return parent_elem, []

    def translate(
        self, xml_message: ET.Element, id_generator: IdGenerator
    ) -> Tuple[Message, List[str]]:
        """
        The public function for this class. Takes an XML message and converts it to a
        Protobuf SapientMessage.
        """
        logger.debug(f"Converting message [{ET.tostring(xml_message)} to protobuf")

        message_updated, errs = self._xml_message_preprocessing(xml_message, id_generator)
        if len(errs) > 0:
            return Message(), errs
        node_id = message_updated.find("nodeId").text

        message_and_errors = self.converter.from_elem(message_updated, id_generator, node_id)
        error_list = message_and_errors[1]
        message = message_and_errors[0]
        logger.debug(
            f"Converted message [{ET.tostring(xml_message)}] to protobuf message"
            f" [{MessageToJson(message)}] with errors [{error_list}]"
        )

        logger.debug(
            f"Finished converting message [{ET.tostring(xml_message)}] to protobuf message"
            f" [{MessageToJson(message)}]"
        )
        return message, error_list
