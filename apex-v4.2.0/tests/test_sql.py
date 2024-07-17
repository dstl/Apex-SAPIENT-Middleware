#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from datetime import datetime, timedelta
from pathlib import Path

from pytest import fixture
from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session

from sapient_apex_server.sqlite_saver import SqliteSaver, rollover
from sapient_apex_server.sqlite_schema import Connection, Message
from sapient_apex_server.structures import SapientVersion


@fixture
def database(tmp_path: Path):
    db_saver = SqliteSaver(str(tmp_path / "current.sql"), True)
    initial_time = datetime.utcnow() - timedelta(seconds=100)

    with db_saver.connection.begin():
        db_saver.connection.execute(
            insert(Connection).values(
                [
                    {"client_type": "ASM", "peer": "redteam.com", "connect_time": initial_time},
                    {
                        "client_type": "Fusion",
                        "peer": "redteam.com",
                        "connect_time": initial_time + timedelta(seconds=1),
                    },
                ]
            )
        )
        # Windows SQLite has issues with RETURNING statement, it seems, so doing it the hard way.
        (asm_id,) = db_saver.connection.execute(
            select(Connection.id).where(Connection.client_type == "ASM")
        ).first() or (None,)
        (fusion_id,) = db_saver.connection.execute(
            select(Connection.id).where(Connection.client_type == "Fusion")
        ).first() or (None,)
        assert asm_id is not None
        assert fusion_id is not None
        db_saver.connection.execute(
            insert(Message).values(
                [
                    {
                        "connection_id": asm_id,
                        "timestamp_received": initial_time + timedelta(seconds=20),
                        "timestamp_decoded": initial_time + timedelta(seconds=20),
                        "timestamp_saved": initial_time + timedelta(seconds=20),
                        "sapient_version": SapientVersion.LATEST,
                        "xml": "rollover this one",
                        "proto": b"Some bytes",
                        "parsed_node_id": "this-is-an-asm",
                        "parsed_type": "registration",
                        "forwarded_count": 1,
                    },
                    {
                        "connection_id": fusion_id,
                        "timestamp_received": initial_time + timedelta(seconds=20),
                        "timestamp_decoded": initial_time + timedelta(seconds=20),
                        "timestamp_saved": initial_time + timedelta(seconds=20),
                        "sapient_version": SapientVersion.LATEST,
                        "xml": "rollover this one",
                        "proto": b"Some bytes",
                        "parsed_node_id": "this-is-a-fusion-node",
                        "parsed_type": "registration",
                        "forwarded_count": 0,
                    },
                    {
                        "connection_id": asm_id,
                        "timestamp_received": initial_time + timedelta(seconds=22),
                        "timestamp_decoded": initial_time + timedelta(seconds=22),
                        "timestamp_saved": initial_time + timedelta(seconds=22),
                        "sapient_version": SapientVersion.LATEST,
                        "xml": "not this one",
                        "proto": b"Some bytes",
                        "parsed_node_id": "this-is-an-asm",
                        "parsed_type": "detection_report",
                        "forwarded_count": 1,
                    },
                    {
                        "connection_id": asm_id,
                        "timestamp_received": initial_time + timedelta(seconds=25),
                        "timestamp_decoded": initial_time + timedelta(seconds=25),
                        "timestamp_saved": initial_time + timedelta(seconds=25),
                        "sapient_version": SapientVersion.LATEST,
                        "xml": "rollover this one",
                        "proto": b"Some bytes",
                        "parsed_node_id": "this-is-an-asm",
                        "parsed_type": "detection_report",
                        "forwarded_count": 1,
                    },
                ]
            )
        )
        (reg_asm,) = db_saver.connection.execute(
            select(Message.id)
            .where(Message.connection_id == asm_id)
            .where(Message.parsed_type == "registration")
        ).first() or (None,)
        (reg_fus,) = db_saver.connection.execute(
            select(Message.id)
            .where(Message.connection_id == fusion_id)
            .where(Message.parsed_type == "registration")
        ).first() or (None,)
        (detect_asm,) = db_saver.connection.execute(
            select(Message.id)
            .where(Message.connection_id == asm_id)
            .where(Message.parsed_type == "detection_report")
            .order_by(Message.timestamp_received.desc())
        ).first() or (None,)
        assert reg_asm is not None
        assert reg_fus is not None
        assert detect_asm is not None
        db_saver.connection.execute(
            update(Connection)
            .where(Connection.id == fusion_id)
            .values({"recent_msg_id_registration": reg_fus})
        )
        db_saver.connection.execute(
            update(Connection)
            .where(Connection.id == asm_id)
            .values({"recent_msg_id_registration": reg_asm, "recent_msg_id_detection": detect_asm})
        )

    return db_saver


def test_rollover(database: SqliteSaver, tmp_path: Path):
    newdb = rollover(database, tmp_path / "next.sql", conversion_enabled=True)
    assert (tmp_path / "next.sql").exists()

    with Session(bind=newdb.connection) as session:
        connections = session.scalars(select(Connection)).all()
        messages = session.scalars(select(Message)).all()
        assert len(connections) == 2
        assert len(messages) == 3
        assert all(message.xml == "rollover this one" for message in messages)
