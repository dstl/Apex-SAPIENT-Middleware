#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from typing import Optional

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from sapient_apex_server.structures import SapientVersion


class SQLBase(DeclarativeBase):
    pass


class Version(SQLBase):
    __tablename__ = "Version"
    id: Mapped[int] = mapped_column(primary_key=True)
    variant: Mapped[str]
    version: Mapped[int]
    conversion_enabled: Mapped[bool]


class RolloverFilename(SQLBase):
    __tablename__ = "RolloverFilename"
    id: Mapped[int] = mapped_column(primary_key=True)
    relative_filepath: Mapped[str]
    absolute_filepath: Mapped[str]


class Message(SQLBase):
    __tablename__ = "Message"
    id: Mapped[int] = mapped_column(primary_key=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("Connection.id"))
    timestamp_received: Mapped[int]
    timestamp_decoded: Mapped[int]
    timestamp_saved: Mapped[int]
    sapient_version: Mapped[SapientVersion]
    xml: Mapped[str]
    proto: Mapped[Optional[bytes]]  # Will not be present for V6 Nodes
    json: Mapped[Optional[str]]
    forwarded_count: Mapped[int]
    parsed_type: Mapped[Optional[str]]
    parsed_node_id: Mapped[Optional[int]]
    parsed_timestamp: Mapped[Optional[int]]
    registration_node_type: Mapped[Optional[str]]
    status_report_system: Mapped[Optional[str]]
    status_report_is_unchanged: Mapped[Optional[bool]]
    error_severity: Mapped[Optional[str]]
    error_description: Mapped[Optional[str]]


class Connection(SQLBase):
    __tablename__ = "Connection"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_type: Mapped[str]
    peer: Mapped[str]  # Socket Address
    connect_time: Mapped[int]
    disconnect_time: Mapped[Optional[int]]
    disconnect_reason: Mapped[Optional[str]]
    recent_msg_id_registration: Mapped[Optional[int]] = mapped_column(ForeignKey(Message.id))
    recent_msg_id_status_new: Mapped[Optional[int]] = mapped_column(ForeignKey(Message.id))
    recent_msg_id_status_unchanged: Mapped[Optional[int]] = mapped_column(ForeignKey(Message.id))
    recent_msg_id_detection: Mapped[Optional[int]] = mapped_column(ForeignKey(Message.id))
