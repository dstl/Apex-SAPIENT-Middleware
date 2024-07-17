#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import json
import logging
import os
import struct
import sys
from pathlib import Path

import trio
from google.protobuf.json_format import MessageToJson
from sqlalchemy import create_engine, text

from sapient_apex_server.message_io import to_version
from sapient_apex_server.structures import SapientVersion, MessageFormat
from sapient_apex_server.time_util import datetime_int_to_str, datetime_str_to_int
from sapient_apex_server.translator.proto_to_proto_translator import (
    empty_sapient_message,
)
from sapient_apex_server.trio_util import (
    connect_tcp_repeatedly,
    receive_size_prefixed,
    receive_until,
)
from sapient_msg.latest.sapient_message_pb2 import SapientMessage

logger = logging.getLogger("apex_replay")


class Database:
    """Handles opening a connection to the database and reading messages from it."""

    def __init__(self, config):
        self.config_url = config["filename"]
        self.config_start_time_str = config["start_time"]
        self.config_start_time = datetime_str_to_int(self.config_start_time_str)
        self.config_end_time = datetime_str_to_int(config["end_time"])
        self.connection = None
        self.has_got_initial_messages = False
        self.cursor = None
        self.most_recent_row = None
        self.sapient_version = SapientVersion[
            config.get("icd_version", SapientVersion.LATEST.name)
            .replace(" ", "_")
            .replace(".", "_")
            .replace("-", "_")
            .upper()
        ]

    @staticmethod
    def _connection_info_to_str(connection_info):
        """Creates a display string from a row result of the query in connect()."""
        (
            connection_id,
            client_type,
            peer,
            connect_time,
            disconnect_time,
            msg_count,
            node_id,
            node_type,
        ) = connection_info
        result = f"{connection_id} ({peer}) {client_type}"
        if node_id is not None:
            result += f" {node_id:.6} ({node_type})"
        width = 60
        result = (result[: width - 3] + "...") if len(result) > width else result.ljust(width)
        result += ": " + datetime_int_to_str(connect_time)
        result += " -> " + datetime_int_to_str(disconnect_time)
        result += " - msg count: " + str(msg_count)
        return result

    def connect(self):
        """Connects to the database."""

        # Create the connection
        url = self.config_url
        if not url:
            logger.info("No filename specified - using latest file in data directory")
            files = sorted(Path("data").glob("*.sqlite"))
            if not files:
                logger.critical("No files found in data directory")
            url = str(files[-1])
        logger.info(f"Connecting to database: {url}")

        if ":///" not in url:
            url = f"sqlite:///{url}"

        self.engine = create_engine(url)
        self.connection = self.engine.connect()

        # Log some information about connections in the database
        connection_info_sql = """
        SELECT
            Connection.id,
            Connection.client_type,
            Connection.peer,
            Connection.connect_time,
            Connection.disconnect_time,
            (
                SELECT COUNT(*)
                FROM Message AS MsgCounted
                WHERE MsgCounted.connection_id = Connection.id
            ) AS msg_count,
            RegMsg.parsed_node_id AS reg_msg_node_id,
            RegMsg.registration_node_type AS reg_msg_node_type
        FROM
            Connection
        LEFT OUTER JOIN
            Message RegMsg ON Connection.recent_msg_id_registration = RegMsg.id
        """
        connection_strs = [
            Database._connection_info_to_str(info)
            for info in self.connection.execute(text(connection_info_sql))
        ]
        logger.info(f"{len(connection_strs)} connections:\n" + "\n".join(connection_strs))

        # Start the main query that iterates over messages
        messages_sql = """
        SELECT
            timestamp_received,
            xml,
            proto,
            parsed_type,
            parsed_node_id,
            status_report_is_unchanged,
            sapient_version
        FROM
            Message
        WHERE
            error_severity IS NULL
        ORDER BY
            id
        """
        self.cursor = self.connection.execute(text(messages_sql))
        self.most_recent_row = self.cursor.fetchone()

    def get_initial_messages(self, message_format: MessageFormat):
        """Gets the most recent registration etc from before start time.
        messages up to, but not including, the start time.
        """
        messages = {}
        while True:
            if self.most_recent_row is None:
                raise ValueError("No messages after start time " + self.config_start_time_str)
            (
                timestamp,
                xml,
                proto,
                msg_type,
                node_id,
                is_unchanged,
                sapient_version,
            ) = self.most_recent_row
            if timestamp >= self.config_start_time:
                break  # Reached first message in requested time window

            if msg_type in ("registration", "status_report"):
                if msg_type == "status_report":
                    if is_unchanged:
                        msg_type = "status_report_unch"
                    elif (node_id, "status_report_unch") in messages:
                        # "New" status reports replace earlier "Unchanged" reports
                        del messages[node_id, "status_report_unch"]

                if message_format == MessageFormat.PROTO:
                    messages[node_id, msg_type] = to_version_as_bytes(
                        proto,
                        SapientVersion[sapient_version],
                        self.sapient_version,
                    )
                elif message_format == MessageFormat.XML:
                    # Directly take the xml column, as its already
                    # been downgraded via parse_proto message conversion
                    messages[node_id, msg_type] = xml

            assert self.cursor is not None
            self.most_recent_row = self.cursor.fetchone()

        return [msg_data for _, msg_data in sorted(messages.items())]

    def get_messages(self, message_format: MessageFormat):
        """Gets all messages within the specified time range."""
        while self.most_recent_row is not None:
            timestamp, xml, proto, *_ = self.most_recent_row
            if self.config_end_time is not None and timestamp >= self.config_end_time:
                break

            msg_data = proto
            if message_format == MessageFormat.PROTO:
                sapient_version = SapientVersion[self.most_recent_row[-1]]
                proto = to_version_as_bytes(proto, sapient_version, self.sapient_version)
            elif message_format == MessageFormat.XML:
                msg_data = xml

            yield timestamp, msg_data
            assert self.cursor is not None
            self.most_recent_row = self.cursor.fetchone()

    def close(self):
        if self.cursor is not None:
            self.cursor.close()
        if self.connection is not None:
            self.connection.close()


async def read_proto_message(receive_stream: trio.abc.ReceiveStream, read_buffer: bytearray):
    """Reads a message and returns it in proto byte format."""
    max_size = 128 * 1024 * 1024
    msg_bytes = await receive_size_prefixed(receive_stream, read_buffer, max_size=max_size)
    return bytes(msg_bytes)


async def read_xml_message(receive_stream: trio.abc.ReceiveStream, read_buffer: bytearray):
    """Reads a message and returns it in xml byte format."""
    max_size = 128 * 1024 * 1024
    msg_bytes = await receive_until(receive_stream, read_buffer, b"\0", max_size=max_size)
    return bytes(msg_bytes)


class NetworkConnection:
    """Opens the network connection and handles sending and receiving messages."""

    def __init__(self, config):
        self.config = config
        self.streams = []
        self.connection_establish_signal = trio.lowlevel.ParkingLot()
        self.message_format = MessageFormat[self.config.get("format", "PROTO")]

    async def connect(self, nursery: trio.Nursery, task_status=trio.TASK_STATUS_IGNORED):
        """Open the network connection.

        The task_status parameter is used to notify the caller that the port is open and ready to
        receive connections. It is only meaningful if is_outbound is False, i.e., we are listening
        rather than connecting outbound. This argument is used in the replay script test.
        """
        if self.config["is_outbound"]:
            nursery.start_soon(
                connect_tcp_repeatedly,
                self.handle_connection,
                self.config["host"],
                self.config["port"],
            )
            logger.info(f"Waiting for connection to {self.config['host']}:{self.config['port']}")
        else:
            # Open the socket for listening
            await nursery.start(trio.serve_tcp, self.handle_connection, self.config["port"])
            logger.info(f"Waiting for connection on port {self.config['port']}")
        task_status.started()
        await self.connection_establish_signal.park()  # Wait until connection established

    async def handle_connection(self, stream: trio.SocketStream):
        """Callback that is called when a connection is established."""
        logger.info("Connection established")
        self.streams.append(stream)
        self.connection_establish_signal.unpark()

        read_buffer = bytearray()
        while True:
            if self.message_format == MessageFormat.PROTO:
                message_bytes = await read_proto_message(stream, read_buffer)
                message_proto = SapientMessage()
                message_proto.ParseFromString(message_bytes)
                message_json = MessageToJson(message_proto, preserving_proto_field_name=True)
                logger.debug("Received proto message from connection:\n" + message_json)
            elif self.message_format == MessageFormat.XML:
                message_bytes = await read_xml_message(stream, read_buffer)
                message_xml = message_bytes.decode("utf8")
                logger.debug("Received xml message from connection:\n" + message_xml)

    async def send(self, msg_data):
        """Sends the given data to the connection."""
        logger.debug(f"Sending {self.message_format} message:\n{msg_data}")
        for stream in self.streams:
            if self.message_format == MessageFormat.PROTO:
                packed_len = struct.pack("<I", len(msg_data))
                msg_bytes = packed_len + msg_data
            elif self.message_format == MessageFormat.XML:
                msg_bytes = msg_data + b"\0"
            await stream.send_all(msg_bytes)

    async def close(self):
        for stream in self.streams:
            await stream.aclose()


class Sleeper:
    """Sleeps a suitable amount of time until messages are ready to send.

    This class takes care of the logic of sleeping. For example, consider if the config asks for
    messages from 08:00:00 onwards, and this class is constructed at 10:00:00 onwards; then if a
    message is read from the database with a timestamp of 08:00:10 then this class will wait until
    10:00:10. That assumes a speed multiplier of 1; if another speed multiplier is chosen then the
    wait time will be adjusted e.g. for a multiplier of 2 then this will wait until 10:00:05.

    To fit with Trio's convention for storing times, this uses floating point seconds, rather than
    Apex's usual convention of integer microseconds.
    """

    def __init__(self, config):
        self.db_start_time = datetime_str_to_int(config["start_time"]) / 1_000_000
        self.real_start_time = trio.current_time()
        self.speed_multiplier = config["speed_multiplier"]
        self.last_lag_warn_time = self.real_start_time - 10  # Note last log time so not too chatty
        self.last_info_time = self.real_start_time - 10  # Separate counter for info level
        self.message_count = 0

    async def sleep_until_message_time(self, db_current_time_ms: int):
        # Compute deadline
        db_current_time = db_current_time_ms / 1_000_000
        db_time_difference = db_current_time - self.db_start_time
        real_time_difference = db_time_difference / self.speed_multiplier
        deadline = self.real_start_time + real_time_difference

        # Warn if high lag or about to wait a long time (due to big gap between messages)
        current_time = trio.current_time()
        wait_time = deadline - current_time
        if wait_time < -1 and (current_time - self.last_lag_warn_time) >= 1:
            logger.warning(f"Lag of {-wait_time:0.1f}s")
            self.last_lag_warn_time = current_time
        elif wait_time > 5:
            logger.warning(f"Waiting for extended time: {wait_time:0.1f}s")

        # Actually perform the sleep
        await trio.sleep_until(deadline)

        # Log time and number of messages sometimes
        if current_time - self.last_info_time > 2:
            logger.info(
                f"Current database time: {datetime_int_to_str(db_current_time_ms)}; "
                + f"messages sent: {self.message_count}"
            )
            self.last_info_time = current_time
        self.message_count += 1


async def start_replayer(config, task_status=trio.TASK_STATUS_IGNORED):
    database = None
    network_connection = None
    try:
        logging.basicConfig(
            level=config["log_level"], format="%(asctime)s %(levelname)s: %(message)s"
        )
        database = Database(config)
        database.connect()
        network_connection = NetworkConnection(config)
        message_format = MessageFormat[config.get("format", "PROTO")]
        async with trio.open_nursery() as nursery:
            await network_connection.connect(nursery, task_status)
            msg_count = 0
            for msg_count, msg_data in enumerate(
                database.get_initial_messages(message_format), start=1
            ):
                await network_connection.send(msg_data)
            logger.info(f"Sent {msg_count} initial messages")
            sleeper = Sleeper(config)  # Must be constructed after above potentially slow calls
            msg_count = 0
            for msg_count, (msg_time, msg_data) in enumerate(
                database.get_messages(message_format), start=1
            ):
                await sleeper.sleep_until_message_time(msg_time)
                await network_connection.send(msg_data)
            logger.info(f"Sent all {msg_count} non-initial messages")
            await network_connection.close()
            network_connection = None
    except trio.ClosedResourceError:
        # When we close the connection after writing, we get this error from reading
        pass
    except Exception as e:
        logger.critical(f"Caught exception {type(e).__name__}: {e}")
    except KeyboardInterrupt:
        logger.critical("Keyboard interrupt detected")
    finally:
        if database is not None:
            database.close()
        if network_connection is not None:
            await network_connection.close()


def get_config():
    if len(sys.argv) > 1:
        config_filename = sys.argv[1]
    else:
        config_filename = "replay_config.json"
        if not Path(config_filename).exists() and Path("..", config_filename).exists():
            # User has started script in a nested directory e.g. by just double clicking replay.exe
            os.chdir("..")
    logger.info("Current working directory: " + str(Path().resolve()))
    logger.info("Using config file: " + config_filename)
    config_path = Path(config_filename)
    if not config_path.exists():
        logger.critical(f"Error: Could not find config file: {config_path.resolve()}")
        sys.exit(1)
    with config_path.open("rb") as f:
        result = json.load(f)
    logger.info("Using config:\n" + json.dumps(result, indent=2))
    return result


def to_version_as_bytes(
    proto: bytes, initial_version: SapientVersion, final_version: SapientVersion
) -> bytes:
    if initial_version == final_version:
        return proto
    msg_initial = empty_sapient_message(initial_version)
    msg_initial.ParseFromString(bytes(proto))
    msg_final = to_version(msg_initial, initial_version, final_version)
    return msg_final.SerializeToString()


def main():
    config = get_config()
    trio.run(start_replayer, config)


if __name__ == "__main__":
    """This utility script is used for replaying messages from an SQL Database
    containing SAPIENT messages. It starts by opening a TCP port and waiting
    for a connection. Once a client is connected it will send all messages
    from the database.
    """
    main()
