#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

# Unit tests to verify Apex validator is successfully checking messages
import uuid
from datetime import datetime, timedelta

import pytest
import ulid
from google.protobuf.json_format import ParseDict

from sapient_apex_server.time_util import datetime_to_pb
from sapient_apex_server.validate_proto import (
    ValidationOptions,
    ValidationType,
    Validator,
)
from sapient_msg.latest.alert_ack_pb2 import AlertAck
from sapient_msg.latest.detection_report_pb2 import DetectionReport
from sapient_msg.latest.location_pb2 import Location, LocationList
from sapient_msg.latest.range_bearing_pb2 import LocationOrRangeBearing
from sapient_msg.latest.registration_ack_pb2 import RegistrationAck
from sapient_msg.latest.registration_pb2 import Registration
from sapient_msg.latest.sapient_message_pb2 import SapientMessage
from sapient_msg.latest.status_report_pb2 import StatusReport
from sapient_msg.latest.velocity_pb2 import ENUVelocity
from tests.msg_templates import get_register_template
from tests.testing_proto_pb2 import (
    AlertAckTest,
    RegistrationAckTest,
    SapientMessageTest,
)


@pytest.fixture(scope="session")
def validator_instance() -> Validator:
    options = {
        "validationTypes": [
            "mandatory_fields_present",
            "mandatory_oneof_present",
            "mandatory_repeated_present",
            "no_unknown_fields",
            "no_unknown_enum_values",
            "id_format_valid",
            "message_timestamp_reasonable",
            "detection_timestamp_reasonable",
            "supported_icd_version",
        ],
        "strictIdFormat": True,
        "messageTimestampRange": [-0.9, 0.1],
        "detectionMinimumGap": 0.08,
        "supportedIcdVersions": [
            "BSI Flex 335 v1.0",
            "BSI Flex 335 v2.0",
        ],
    }
    return Validator(ValidationOptions.from_config_dict(options))


def test_successful_validate(validator_instance: Validator):
    msg = ParseDict(get_register_template(node_id=str(uuid.uuid4())), SapientMessage())
    errors = []
    validator_instance.validate_sapient_message(msg, datetime.utcnow(), errors)
    assert len(errors) == 0


def test_mandatory_field(validator_instance: Validator):
    errors = []
    msg = SapientMessage(
        timestamp=datetime_to_pb(datetime.utcnow()),
        node_id=str(uuid.uuid4()),
        destination_id=None,
        alert_ack=AlertAck(
            alert_id=ulid.new().str,
            # alert_status="ALERT_STATUS_ACCEPTED",
            reason="Testing for missing alert_status validation",
        ),
    )
    validator_instance.validate_sapient_message(msg, datetime.utcnow(), errors)
    assert any(error.type == ValidationType.MANDATORY_FIELDS_PRESENT for error in errors)
    assert any("Missing mandatory field: " in error.message for error in errors)


def test_mandatory_repeated_field(validator_instance: Validator):
    errors = []
    msg = SapientMessage(
        timestamp=datetime_to_pb(datetime.utcnow()),
        node_id=str(uuid.uuid4()),
        destination_id=None,
        status_report=StatusReport(
            report_id=ulid.new().str,
            system="SYSTEM_OK",
            info="INFO_NEW",
            field_of_view=LocationOrRangeBearing(
                location_list=LocationList(
                    locations=[
                        # Location(
                        #     x=1,
                        #     y=2,
                        #     coordinate_system="LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                        #     datum="LOCATION_DATUM_WGS84_E"
                        # )
                    ]
                )
            ),
            status=[
                StatusReport().Status(
                    status_level="STATUS_LEVEL_INFORMATION_STATUS",
                    status_type="STATUS_TYPE_WEATHER",
                    status_value="raining",
                )
            ],
        ),
    )
    validator_instance.validate_sapient_message(msg, datetime.utcnow(), errors)
    assert any(error.type == ValidationType.MANDATORY_REPEATED_PRESENT for error in errors)
    assert any("Missing mandatory repeated field: " in error.message for error in errors)


def test_mandatory_oneof_field(validator_instance: Validator):
    errors = []
    msg = SapientMessage(
        timestamp=datetime_to_pb(datetime.utcnow()),
        node_id=str(uuid.uuid4()),
        destination_id=None,
        status_report=StatusReport(
            report_id=ulid.new().str,
            system="SYSTEM_OK",
            info="INFO_NEW",
            field_of_view=LocationOrRangeBearing(
                # location_list=LocationList(
                #     locations=[Location(
                #         x=1,
                #         y=2,
                #         coordinate_system="LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                #         datum="LOCATION_DATUM_WGS84_E"
                #     )]
                # )
            ),
            status=[
                StatusReport().Status(
                    status_level="STATUS_LEVEL_INFORMATION_STATUS",
                    status_type="STATUS_TYPE_WEATHER",
                    status_value="raining",
                )
            ],
        ),
    )
    validator_instance.validate_sapient_message(msg, datetime.utcnow(), errors)
    assert any(error.type == ValidationType.MANDATORY_ONEOF_PRESENT for error in errors)
    assert any("Missing mandatory OneOf field: " in error.message for error in errors)


def test_valid_uuid(validator_instance: Validator):
    errors = []
    msg = SapientMessage(
        timestamp=datetime_to_pb(datetime.utcnow()),
        node_id="6a24a9c1-8214-415a-8927-50099e086AD4",  # Uppercase AD at the end
        destination_id=None,
        registration_ack=RegistrationAck(acceptance=True),
    )
    validator_instance.validate_sapient_message(msg, datetime.utcnow(), errors)
    assert any(error.type == ValidationType.ID_FORMAT_VALID for error in errors)
    assert any("Invalid UUID: " in error.message for error in errors)


def test_valid_ulid(validator_instance: Validator):
    errors = []
    msg = SapientMessage(
        timestamp=datetime_to_pb(datetime.utcnow()),
        node_id=str(uuid.uuid4()),
        destination_id=None,
        alert_ack=AlertAck(
            alert_id="01H7DCESBYA6QTKFMY6FD7WE6TFOOBAR",  # FOOBAR in ULID
            alert_ack_status="ALERT_ACK_STATUS_ACCEPTED",
        ),
    )
    validator_instance.validate_sapient_message(msg, datetime.utcnow(), errors)
    assert any(error.type == ValidationType.ID_FORMAT_VALID for error in errors)
    assert any("Invalid ULID: " in error.message for error in errors)


def test_no_unknown_fields(validator_instance: Validator):
    errors = []
    msg = SapientMessageTest(
        timestamp=datetime_to_pb(datetime.utcnow()),
        node_id=str(uuid.uuid4()),
        destination_id=None,
        registration_ack=RegistrationAckTest(
            acceptance=True, new_field_example="Test unknown field"
        ),
    )
    # Parse SapientMessageTest msg into SapientMessage
    proto_msg = SapientMessage()
    proto_msg.ParseFromString(bytes(msg.SerializeToString()))
    validator_instance.validate_sapient_message(proto_msg, datetime.utcnow(), errors)
    assert any(error.type == ValidationType.NO_UNKNOWN_FIELDS for error in errors)
    assert any("Unknown field number: " in error.message for error in errors)


def test_enums_known(validator_instance: Validator):
    errors = []
    msg = SapientMessageTest(
        timestamp=datetime_to_pb(datetime.utcnow()),
        node_id=str(uuid.uuid4()),
        destination_id=None,
        alert_ack=AlertAckTest(
            alert_id=ulid.new().str,
            alert_ack_status="UNKNOWN_ENUM",
            reason="Testing unknown enum",
        ),
    )
    # Parse SapientMessageTest msg into SapientMessage
    proto_msg = SapientMessage()
    proto_msg.ParseFromString(bytes(msg.SerializeToString()))
    validator_instance.validate_sapient_message(proto_msg, datetime.utcnow(), errors)
    assert any(error.type == ValidationType.NO_UNKNOWN_ENUM_VALUES for error in errors)
    assert any("Unknown enum value: " in error.message for error in errors)


def test_message_timestamp_reasonable(validator_instance: Validator):
    errors = []
    msg = SapientMessage(
        timestamp=datetime_to_pb(datetime.utcnow() - timedelta(hours=1)),
        node_id=str(uuid.uuid4()),
        destination_id=None,
        registration_ack=RegistrationAck(acceptance=True),
    )
    validator_instance.validate_sapient_message(msg, datetime.utcnow(), errors)
    assert any(error.type == ValidationType.MESSAGE_TIMESTAMP_REASONABLE for error in errors)
    assert any("Timestamp delta" in error.message for error in errors)


def test_detection_timestamp_reasonable(validator_instance: Validator):
    errors = []
    timestamp = datetime.utcnow()
    msg = SapientMessage(
        timestamp=datetime_to_pb(timestamp),
        node_id=str(uuid.uuid4()),
        destination_id=None,
        detection_report=DetectionReport(
            report_id=ulid.new().str,
            object_id=ulid.new().str,
            location=Location(
                x=1,
                y=2,
                coordinate_system="LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                datum="LOCATION_DATUM_WGS84_E",
            ),
            enu_velocity=ENUVelocity(east_rate=5.1, north_rate=3.1),
        ),
    )
    validator_instance.validate_sapient_message(msg, datetime.utcnow(), errors)

    # Send next detection only 1 microsecond later
    timestamp = timestamp + timedelta(microseconds=1)
    msg.timestamp.CopyFrom(datetime_to_pb(timestamp))
    validator_instance.validate_sapient_message(msg, datetime.utcnow(), errors)
    assert any(error.type == ValidationType.DETECTION_TIMESTAMP_REASONABLE for error in errors)
    assert any("Detection time delta" in error.message for error in errors)


test_icd_params = [
    # test_icd_version, expected_result
    ("", False),
    ("TEST_ICD_V999", False),
    ("BSIFlex335v1.0", False),
    ("BSI_Flex_335_V1.0", False),
    ("BSI_Flex_335_v1_0", False),
    ("BSI_Flex_335_v1.0", True),
    ("BSI Flex 335 v2.0", True),
    # Valid format, but not supported yet
    ("BSI Flex 335 v5.0", False),
    ("BSI Flex 335 v123.0", False),
]


@pytest.fixture(ids=[param[0] for param in test_icd_params], params=test_icd_params)
def icd_params(request):
    return request.param


def test_supported_icd_version(validator_instance: Validator, icd_params):
    errors = []
    (test_icd_version, expected_result) = icd_params

    msg = SapientMessage(
        timestamp=datetime_to_pb(datetime.utcnow()),
        node_id=str(uuid.uuid4()),
        destination_id=None,
        registration=Registration(
            node_definition=[Registration().NodeDefinition(node_type="NODE_TYPE_OTHER")],
            icd_version=test_icd_version,
            name="Supported ICD Version Test Node",
            short_name="Test Node",
            capabilities=[Registration().Capability(category="", type="")],
            status_definition=Registration().StatusDefinition(
                status_interval=Registration().Duration(units="TIME_UNITS_SECONDS", value=5)
            ),
            mode_definition=[
                Registration().ModeDefinition(
                    mode_name="default",
                    mode_type="MODE_TYPE_PERMANENT",
                    settle_time=Registration().Duration(units="TIME_UNITS_SECONDS", value=1),
                    detection_definition=[
                        Registration().DetectionDefinition(
                            location_type=Registration().LocationType(
                                location_units="LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                                location_datum="LOCATION_DATUM_WGS84_E",
                            )
                        )
                    ],
                    task=Registration().TaskDefinition(
                        region_definition=Registration().RegionDefinition(
                            region_type=["REGION_TYPE_BOUNDARY"],
                            region_area=[
                                Registration().LocationType(
                                    location_units="LOCATION_COORDINATE_SYSTEM_LAT_LNG_DEG_M",
                                    location_datum="LOCATION_DATUM_WGS84_E",
                                )
                            ],
                        )
                    ),
                )
            ],
        ),
    )
    validator_instance.validate_sapient_message(msg, datetime.utcnow(), errors)

    if expected_result:
        assert not any(error.type == ValidationType.SUPPORTED_ICD_VERSION for error in errors)
        assert not any("Unsupported ICD version: " in error.message for error in errors)
    else:
        assert any(error.type == ValidationType.SUPPORTED_ICD_VERSION for error in errors)
        assert any("Unsupported ICD version: " in error.message for error in errors)


def main():
    options = {
        "validationTypes": [
            "mandatory_fields_present",
            "mandatory_oneof_present",
            "mandatory_repeated_present",
            "no_unknown_fields",
            "no_unknown_enum_values",
            "id_format_valid",
            "message_timestamp_reasonable",
            "detection_timestamp_reasonable",
            "supported_icd_version",
        ],
        "strictIdFormat": True,
        "messageTimestampRange": [-0.9, 0.1],
        "detectionMinimumGap": 0.08,
        "supportedIcdVersions": ["ICD7.0", "BSI Flex 335 v1.0"],
    }

    val_instance = Validator(ValidationOptions.from_config_dict(options))
    test_successful_validate(val_instance)
    test_no_unknown_fields(val_instance)
    test_enums_known(val_instance)
    test_valid_ulid(val_instance)
    test_valid_uuid(val_instance)
    test_mandatory_field(val_instance)
    test_mandatory_repeated_field(val_instance)
    test_mandatory_oneof_field(val_instance)
    test_message_timestamp_reasonable(val_instance)
    test_detection_timestamp_reasonable(val_instance)
    test_supported_icd_version(val_instance)


if __name__ == "__main__":
    main()
