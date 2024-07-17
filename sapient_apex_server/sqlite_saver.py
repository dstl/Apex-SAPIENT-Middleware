#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Sequence

from sqlalchemy import create_engine, insert, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from sapient_apex_server.sqlite_schema import (
    Connection,
    Message,
    RolloverFilename,
    SQLBase,
    Version,
)
from sapient_apex_server.structures import (
    ConnectionRecord,
    DisconnectionRecord,
    MessageRecord,
)
from sapient_apex_server.time_util import datetime_to_int, datetime_to_str

logger = logging.getLogger("apex")


class SqliteSaver:
    def __init__(self, url: str, conversion_enabled: bool, echo: bool = False):
        if ":///" not in url:
            url = f"sqlite:///{url}"

        logger.info(f"Opening SQLite database with url: {url}")
        self.engine = create_engine(url, echo=echo)
        SQLBase.metadata.create_all(self.engine)

        self.connection = self.engine.connect()

        if "sqlite" in url:
            sqlite_setup(self.connection)
        with self.connection.begin():
            self.connection.execute(
                insert(Version).values(
                    variant="Apex", version=1, conversion_enabled=conversion_enabled
                )
            )
        logger.info("Database opened and tables created")

    def insert_connection(self, conn: ConnectionRecord):
        """Inserts a row in Connection table when a new connection is established."""
        with Session(self.connection) as session, session.begin():
            session.add(
                Connection(
                    id=conn.id,
                    client_type=conn.type,
                    peer=conn.peer,
                    connect_time=datetime_to_int(conn.time),
                )
            )
        logger.info(f"Connection inserted (id: {conn.id}, socket: {conn.peer})")

    @staticmethod
    def _record_to_message(msg: MessageRecord) -> Message:
        """This is the tuple of fields needed for the INSERT message SQL."""
        return Message(
            id=msg.received.message_id,
            connection_id=msg.received.connection_id,
            timestamp_received=datetime_to_int(msg.received.timestamp),
            timestamp_decoded=datetime_to_int(msg.decoded_timestamp),
            timestamp_saved=datetime_to_int(msg.saved_timestamp),
            xml=msg.data_decoded_xml,
            proto=msg.data_binary_proto,
            json=msg.data_json if msg.parsed else None,
            forwarded_count=msg.forwarded_count,
            parsed_type=msg.parsed.message_type if msg.parsed else None,
            parsed_node_id=msg.parsed.node_id if msg.parsed else None,
            parsed_timestamp=(
                datetime_to_int(msg.parsed.message_timestamp) if msg.parsed else None
            ),
            registration_node_type=(msg.registration.node_name if msg.registration else None),
            status_report_system=(msg.status_report.system if msg.status_report else None),
            status_report_is_unchanged=(
                msg.status_report.is_unchanged if msg.status_report else None
            ),
            error_severity=msg.error.severity.name if msg.error else None,
            error_description=msg.error.description if msg.error else None,
            sapient_version=msg.sapient_version,
        )

    def _update_connection_multi(self, msgs: List[MessageRecord]):
        """Updates Connection table with last message IDs when those are received."""
        with self.connection.begin():
            for msg in msgs:
                if msg.error is not None:
                    continue
                args: Optional[dict] = None
                if msg.registration is not None:
                    args = {
                        "recent_msg_id_registration": msg.received.message_id,
                        "recent_msg_id_status_new": None,
                        "recent_msg_id_status_unchanged": None,
                        "recent_msg_id_detection": None,
                    }
                elif msg.status_report is not None and not msg.status_report.is_unchanged:
                    args = {
                        "recent_msg_id_status_new": msg.received.message_id,
                        "recent_msg_id_status_unchanged": None,
                    }
                elif msg.status_report is not None and msg.status_report.is_unchanged:
                    args = {"recent_msg_id_status_unchanged": msg.received.message_id}
                elif msg.parsed is not None and msg.parsed.message_type == "detection_report":
                    args = {"recent_msg_id_detection": msg.received.message_id}
                if args:
                    self.connection.execute(
                        update(Connection)
                        .where(Connection.id == msg.received.connection_id)
                        .values(**args)
                    )

    def insert_message_multi(self, msg_list: List[MessageRecord]):
        """Inserts messages into the Message table and updates relevant Connection columns."""
        # If just an iterator then upgrade to a list, as we need to iterate it more than once.
        if not isinstance(msg_list, list):
            msg_list = list(msg_list)

        # Record insertion time: should be done automatically by slqalchemy or the database,
        # but that would require refactoring the tables themselves
        timenow = datetime.utcnow()
        # Insert the message records and update connection records if necessary
        with Session(self.connection) as session, session.begin():
            for msg in msg_list:
                msg.saved_timestamp = timenow
            # Insert the actual Message rows
            session.add_all(self._record_to_message(msg) for msg in msg_list)
        # Update the rows in the Connection table to reflect those messages
        self._update_connection_multi(msg_list)

        logger.debug(f"Inserted {len(msg_list)} messages")

    def update_disconnection(self, disconn: DisconnectionRecord):
        """Update Connection table to note that it is now disconnected."""
        with self.connection.begin():
            self.connection.execute(
                update(Connection)
                .where(Connection.id == disconn.connection_id)
                .values(
                    disconnect_reason=disconn.reason, disconnect_time=datetime_to_int(disconn.time)
                )
            )
        logger.info(f"Connection disconnection update (id: {disconn.connection_id})")

    def rollover_import(
        self,
        msg_list: Sequence[Message],
        conn_list: Sequence[Connection],
    ):
        """Imports raw Connections and Messages into database"""
        try:
            with Session(self.connection) as session, session.begin():
                # Passing ORM object from one session to another is slightly surprising.
                # It requires merge rather than add!
                for message in msg_list:
                    session.merge(message)
                for connection in conn_list:
                    session.merge(connection)
        except SQLAlchemyError as e:
            logger.critical(f"Database rollover import failed: {e}")
        else:
            logger.debug(f"Rollover imported {len(msg_list)} messages")
            logger.debug(f"Rollover imported {len(conn_list)} connections")

    def rollover_export(
        self, new_db_rel_filename, new_db_abs_filename
    ) -> tuple[Sequence[Connection], Sequence[Message]]:
        """Exports all active Connections and recent Messages from Database"""
        active_connections = []
        recent_messages = []
        try:
            with Session(self.connection) as session, session.begin():
                active_connections = session.scalars(
                    select(Connection).where(Connection.disconnect_time.is_(None))
                ).all()
                all_ids = {
                    id
                    for connection in active_connections
                    for id in (
                        connection.recent_msg_id_registration,
                        connection.recent_msg_id_status_new,
                        connection.recent_msg_id_status_unchanged,
                        connection.recent_msg_id_detection,
                    )
                    if id is not None
                }
                recent_messages = session.scalars(
                    select(Message).where(Message.id.in_(all_ids))
                ).all()

                # Insert new DB filename for GUI rollover
                session.add(
                    RolloverFilename(
                        relative_filepath=new_db_rel_filename, absolute_filepath=new_db_abs_filename
                    )
                )
                session.expunge_all()

        except SQLAlchemyError as e:
            logger.critical(f"Database rollover export failed: {e}")
        else:
            logger.info(f"Rollover information inserted (rollover_filename: {new_db_rel_filename})")
            logger.debug(f"Retrieved {len(active_connections)} active connections")
            logger.debug(f"Retrieved {len(recent_messages)} recent messages")
        return active_connections, recent_messages

    def close(self):
        """Close the database, in particular so WAL and SHM files are cleaned up."""
        self.connection.close()


def rollover(
    old_saver: SqliteSaver, path: Optional[Path] = None, conversion_enabled: bool = True
) -> SqliteSaver:
    # Create new saver instance
    date_str = datetime_to_str(datetime.utcnow()).replace(":", "-")
    sqlite_rel_filename = str(path or Path(f"data/data-{date_str}.sqlite"))
    new_saver = SqliteSaver(sqlite_rel_filename, conversion_enabled)
    sqlite_abs_filename = os.path.abspath(str(sqlite_rel_filename))
    # Export active connections and recent messages from current database
    connections, messages = old_saver.rollover_export(
        new_db_rel_filename=sqlite_rel_filename,
        new_db_abs_filename=sqlite_abs_filename,
    )
    # Import active connections and recent messages into new database
    new_saver.rollover_import(msg_list=messages, conn_list=connections)
    return new_saver


def sqlite_setup(connection):
    with connection.begin():
        script = """\
                        --- Enable WAL mode, which is faster than the default rollback journal
                        PRAGMA journal_mode = WAL;
                        --- Change synchronous mode from FULL to OFF. Safe from corruption
                        --- even if the program crashes, so long as the operating system does
                        --- not crash.
                        PRAGMA synchronous = OFF;
                        --- Use up 1GB virtual memory for memory mapping the database file
                        PRAGMA mmap_size = 1000000000;
                        --- create indices
                        CREATE UNIQUE INDEX IF NOT EXISTS index_message_connection_id
                            ON Message(connection_id, id);
                        CREATE INDEX IF NOT EXISTS index_message_connection_type
                            ON Message(connection_id, parsed_type, id);
                        CREATE INDEX IF NOT EXISTS index_message_noerror_connection_type
                            ON Message(connection_id, parsed_type, id)
                            WHERE error_severity IS NOT NULL;
                        """
        for statement in script.split(";"):
            if statement.strip():
                connection.execute(text(statement.strip()))
