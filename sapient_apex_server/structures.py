#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Types used through the Apex middleware.

The ConnectionRecord and DisconnectRecord types are small self-contained structures used when a
connection is opened or closed. The MessageRecord type at the bottom is used whenever a message is
received (or sent - almost all messages from Apex are just received messages that are forwarded on).
All remaining types in this file are component parts of the MessageRecord.
"""

import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, IntEnum, auto
from typing import Optional

from google.protobuf.json_format import MessageToJson
from google.protobuf.message import Message

from sapient_apex_server.time_util import datetime_to_str


class MessageFormat(Enum):
    XML = 1
    JSON = 2
    GEO_JSON = 3
    PROTO = 4
    DEFAULT = PROTO


class SapientVersion(IntEnum):
    VERSION6 = auto()
    BSI_FLEX_335_V1_0 = auto()
    BSI_FLEX_335_V2_0 = auto()

    LATEST = BSI_FLEX_335_V2_0
    OLDEST = VERSION6
    LOWEST_PROTO = BSI_FLEX_335_V1_0

    @property
    def protocol_name(self) -> str:
        if self == SapientVersion.VERSION6:
            return "Version6"
        if self == SapientVersion.BSI_FLEX_335_V1_0:
            return "BSI Flex 335 v1.0"
        if self == SapientVersion.BSI_FLEX_335_V2_0:
            return "BSI Flex 335 v2.0"
        raise NotImplementedError()


class DatabaseOperation(Enum):
    CREATE = 0
    READ = 1
    UPDATE = 2
    DELETE = 3
    SHUTDOWN = 4


@dataclass
class ConnectionRecord:
    id: int
    type: str
    format: str
    peer: str  # Socket's Peer Address
    time: datetime


@dataclass
class DisconnectionRecord:
    connection_id: int
    time: datetime
    reason: str


@dataclass
class ReceivedDataRecord:
    connection_id: int
    message_id: int
    timestamp: datetime
    data_bytes: bytes


@dataclass
class ParsedRecord:
    message_type: Optional[str]
    node_id: Optional[str]
    internal_sensor_id: Optional[int]
    destination_node_id: Optional[str]
    message_timestamp: datetime
    detection_confidence: Optional[float]
    parsed_proto: Optional[Message]
    parsed_xml: Optional[ET.Element]

    def get_message_json(self) -> dict:
        if self.parsed_proto:
            assert self.message_type is not None
            assert self.message_type.lower().strip() == self.message_type
            assert self.node_id
            return {
                "node_id": self.node_id,
                "destination_id": (self.destination_node_id or "").strip(),
                "timestamp": datetime_to_str(self.message_timestamp),
                "message_type": self.message_type,
                "message": json.loads(
                    MessageToJson(
                        getattr(self.parsed_proto, self.message_type),
                        preserving_proto_field_name=True,
                    )
                ),
            }
        return {}


@dataclass
class RegistrationRecord:
    node_name: str


@dataclass
class StatusReportRecord:
    system: str  # OK, Error, Tamper, GoodBye (... or maybe others?)
    is_unchanged: bool


class ErrorSeverity(Enum):
    UNSTORED = 0  # Quieter than SILENT! Do not even store in database
    SILENT = 1  # Do not report back to ASM
    NOISY = 2  # Send error message back to ASM
    FATAL = 3  # Close the connection immediately


@dataclass
class ErrorRecord:
    severity: ErrorSeverity
    description: str


def UnstoredError(desc):
    return ErrorRecord(ErrorSeverity.UNSTORED, str(desc))


def SilentError(desc):
    return ErrorRecord(ErrorSeverity.SILENT, str(desc))


def NoisyError(desc):
    return ErrorRecord(ErrorSeverity.NOISY, str(desc))


def FatalError(desc):
    return ErrorRecord(ErrorSeverity.FATAL, str(desc))


@dataclass
class MessageRecord:
    received: ReceivedDataRecord
    # Raw data versions for XML, proto bytes, and JSON representation stored in MessageRecord
    # so that they are still stored in the DB if there is any time of error during parsing
    data_decoded_xml: str
    data_binary_proto: Optional[bytes]
    decoded_timestamp: datetime  # Time decoded (potentially some time after received)
    forwarded_count: int = 0  # How many other connections the was message forwarded to
    data_json: Optional[str] = None
    parsed: Optional[ParsedRecord] = None
    registration: Optional[RegistrationRecord] = None
    status_report: Optional[StatusReportRecord] = None
    error: Optional[ErrorRecord] = None
    saved_timestamp: Optional[datetime] = None
    updated_data_bytes: Optional[bytes] = None  # After time offset adjustment
    sapient_version: SapientVersion = SapientVersion.LATEST

    def type_str(self):
        if self.parsed is None:
            return "--"
        else:
            return self.parsed.message_type
