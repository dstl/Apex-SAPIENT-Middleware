#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sapient_apex_server.time_util import int_to_datetime


@dataclass
class MsgTimes:
    msg_time: datetime
    rcv_time: datetime
    decode_time: datetime
    save_time: datetime

    @staticmethod
    def from_row(row: dict, prefix: str):
        msg_time = row[prefix + "parsed_timestamp"]
        if msg_time is None:
            return None
        else:
            return MsgTimes(
                msg_time=int_to_datetime(msg_time),
                rcv_time=int_to_datetime(row[prefix + "timestamp_received"]),
                decode_time=int_to_datetime(row[prefix + "timestamp_decoded"]),
                save_time=int_to_datetime(row[prefix + "timestamp_saved"]),
            )


sql_get_connections = """
SELECT
    Connection.id,
    Connection.client_type,
    Connection.peer,
    Connection.connect_time,
    Connection.disconnect_time,
    Connection.disconnect_reason,
    (
        SELECT COUNT(*)
        FROM Message AS MsgCounted
        WHERE MsgCounted.connection_id = Connection.id
    ) AS msg_count,
    RegMsg.parsed_node_id AS reg_msg_node_id,
    RegMsg.registration_node_type AS reg_msg_node_type,
    RegMsg.timestamp_received AS reg_msg_timestamp_received,
    StatusMsgNew.status_report_system AS status_new_msg_system,
    StatusMsgNew.parsed_timestamp AS status_new_msg_parsed_timestamp,
    StatusMsgNew.timestamp_received AS status_new_msg_timestamp_received,
    StatusMsgNew.timestamp_decoded AS status_new_msg_timestamp_decoded,
    StatusMsgNew.timestamp_saved AS status_new_msg_timestamp_saved,
    StatusMsgUnchanged.status_report_system AS status_unch_msg_system,
    StatusMsgUnchanged.parsed_timestamp AS status_unch_msg_parsed_timestamp,
    StatusMsgUnchanged.timestamp_received AS status_unch_msg_timestamp_received,
    StatusMsgUnchanged.timestamp_decoded AS status_unch_msg_timestamp_decoded,
    StatusMsgUnchanged.timestamp_saved AS status_unch_msg_timestamp_saved,
    DetectionMsg.parsed_timestamp AS detection_msg_parsed_timestamp,
    DetectionMsg.timestamp_received AS detection_msg_timestamp_received,
    DetectionMsg.timestamp_decoded AS detection_msg_timestamp_decoded,
    DetectionMsg.timestamp_saved AS detection_msg_timestamp_saved
FROM
    Connection
LEFT OUTER JOIN
    Message RegMsg ON Connection.recent_msg_id_registration = RegMsg.id
LEFT OUTER JOIN
    Message StatusMsgNew ON Connection.recent_msg_id_status_new = StatusMsgNew.id
LEFT OUTER JOIN
    Message StatusMsgUnchanged ON Connection.recent_msg_id_status_unchanged = StatusMsgUnchanged.id
LEFT OUTER JOIN
    Message DetectionMsg ON Connection.recent_msg_id_detection = DetectionMsg.id;
"""


@dataclass
class ConnectionInfo:
    # "Node" column
    id: int
    node_id: Optional[int]
    client_type: str  # ASM or DMM
    node_type: str  # e.g. "AptCore Radar ASM" or "(DMM)" or "(multiple)"

    # "Socket" column
    peer: str  # e.g. "127.0.0.1:23747"

    # "Connection" column
    connected_time: datetime
    disconnected_time: Optional[datetime]
    disconnected_reason: Optional[str]

    # "Status" and "status time" columns
    reg_msg_received_timestamp: Optional[datetime]
    status_new_system: Optional[str]
    status_new_times: Optional[MsgTimes]
    status_unch_times: Optional[MsgTimes]
    detection_times: Optional[MsgTimes]

    # "Message count" column
    message_count: int

    def max_time(self):
        result = self.connected_time
        if self.disconnected_time is not None and self.disconnected_time > result:
            result = self.disconnected_time
        if self.reg_msg_received_timestamp is not None and self.reg_msg_received_timestamp > result:
            result = self.reg_msg_received_timestamp
        if self.status_new_times and self.status_new_times.rcv_time > result:
            result = self.status_new_times.rcv_time
        if self.status_unch_times and self.status_unch_times.rcv_time > result:
            result = self.status_unch_times.rcv_time
        if self.detection_times and self.detection_times.rcv_time > result:
            result = self.detection_times.rcv_time
        return result

    @staticmethod
    def from_row(row: dict):
        return ConnectionInfo(
            id=row["id"],
            node_id=row["reg_msg_node_id"],
            client_type=row["client_type"],
            node_type=row["reg_msg_node_type"],
            peer=row["peer"],
            connected_time=int_to_datetime(row["connect_time"]),
            disconnected_time=int_to_datetime(row["disconnect_time"]),
            disconnected_reason=row["disconnect_reason"],
            reg_msg_received_timestamp=int_to_datetime(row["reg_msg_timestamp_received"]),
            status_new_system=row["status_new_msg_system"],
            status_new_times=MsgTimes.from_row(row, "status_new_msg_"),
            status_unch_times=MsgTimes.from_row(row, "status_unch_msg_"),
            detection_times=MsgTimes.from_row(row, "detection_msg_"),
            message_count=row["msg_count"],
        )
