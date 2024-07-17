#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import functools
import logging
import math
from dataclasses import dataclass
from datetime import datetime
from threading import Event
from typing import Callable

import trio

from sapient_apex_server.connection import ConnectionCreator
from sapient_apex_server.message_io import ConnectionWriter
from sapient_apex_server.parse_proto import parse_proto
from sapient_apex_server.parse_xml import parse_xml
from sapient_apex_server.structures import (
    ConnectionRecord,
    DisconnectionRecord,
    ErrorSeverity,
    MessageFormat,
    MessageRecord,
    ReceivedDataRecord,
    SapientVersion,
)
from sapient_apex_server.translator.id_generator import IdGenerator
from sapient_apex_server.trio_util import (
    BufferedWriter,
    ThreadSafeCancelScope,
    connect_tcp_repeatedly,
    receive_size_prefixed,
    receive_until,
)
from sapient_apex_server.validate_proto import ValidationOptions, Validator


@dataclass
class Callbacks:
    """These callbacks are sent by the ApexServer and handled by methods of the SqliteSaver."""

    on_connect: Callable[[ConnectionRecord], None]
    on_message_receive: Callable[[MessageRecord], None]
    on_disconnect: Callable[[DisconnectionRecord], None]
    on_startup_complete: Event


logger = logging.getLogger("apex")

_previous_message_id = 0


class ApexError(RuntimeError):
    """Used to distinguish errors found by Apex (e.g. message parsing errors)."""

    pass


class ApexServer:
    def __init__(self, callbacks: Callbacks, config: dict):
        self.callbacks = callbacks
        self.connection_creator = ConnectionCreator(config)
        self.parser_thread_token = trio.CapacityLimiter(total_tokens=1)
        self.config = config
        self.validation_config = ValidationOptions.from_config_dict(
            config.get("validationOptions", {})
        )
        self.top_level_cancel_scope = ThreadSafeCancelScope()
        self.id_generator = IdGenerator(config)

    async def serve(self, stream: trio.SocketStream, connection_config: dict):
        """The main connection handling function, which shuffles data between other classes."""
        error = None
        read_buffer = bytearray()

        connection_config = normalize_connection_config(
            connection_config, self.config["enableMessageConversion"]
        )

        buffered_writer = BufferedWriter(stream, self.config["messageMaxSizeKb"] * 1024 * 10)
        connection_id, connection = self.connection_creator.create(
            connection_config,
            ConnectionWriter(
                buffered_writer.write_nowait,
                self.id_generator,
                encoding=connection_config["format"],
                version=connection_config["icd_version"],
            ),
        )
        self.callbacks.on_connect(
            ConnectionRecord(
                connection_id,
                connection_config["type"],
                connection_config["format"].name,
                get_peername(stream) or get_peername(connection_config),
                datetime.utcnow(),
            )
        )
        msg_send_channel, msg_recv_channel = trio.open_memory_channel(max_buffer_size=math.inf)

        # One of the tasks for this connection: just reads messages and puts on a memory channel.
        # This is done rather than reading as part of the main loop so that we can accurately record
        # when the message was received, even if the parsing thread has a backlog. It does ruin
        # network backpressure, but that is probably not useful for Sapient middleware anyway.
        async def read_to_channel():
            while True:
                receive_fn = (
                    receive_size_prefixed
                    if connection_config["format"] == MessageFormat.PROTO
                    else receive_until
                )
                message_bytes = await receive_fn(
                    stream,
                    read_buffer,
                    delimiter=b"\0",
                    max_size=self.config["messageMaxSizeKb"] * 1024,
                    return_delimiter=True,
                )
                global _previous_message_id
                _previous_message_id += 1
                raw_message = ReceivedDataRecord(
                    connection_id=connection_id,
                    message_id=_previous_message_id,
                    timestamp=datetime.utcnow(),
                    data_bytes=message_bytes,
                )
                msg_send_channel.send_nowait(raw_message)

        parser = _get_parser(
            connection_config["format"],
            enable_message_conversion=self.config.get("enableMessageConversion", True),
            enable_sensor_id_auto=self.config.get("autoAssignSensorIDInRegistration", {}).get(
                "enable", True
            ),
            sapient_version=connection_config["icd_version"],
        )

        # The main read task for the connection: pulls messages off of the read channel and
        # processes them.
        async def read_from_channel():
            validator = Validator(self.validation_config)
            async for raw_message in msg_recv_channel:
                # Parse the message (if valid); use a worker thread in case it takes a while
                msg = await trio.to_thread.run_sync(
                    parser,
                    raw_message,
                    validator,
                    self.id_generator,
                    limiter=self.parser_thread_token,
                )

                # Actually handle the message; this is done in the connection object.
                # This can set more fields in the message record (error, forwarded_count).
                connection.handle_message(msg, self.id_generator)

                # Callback to main(); this writes the message to SQLite
                if msg.error is None or msg.error.severity != ErrorSeverity.UNSTORED:
                    self.callbacks.on_message_receive(msg)

                # Exit the loop if that was a fatal error. This test is deliberately here,
                # rather than straight after handle_message, so that the message is still
                # written to the database.
                if msg.error is not None and msg.error.severity == ErrorSeverity.FATAL:
                    raise ApexError(msg.error.description)

        error_messages = []

        def exception_handler(e):
            """To cope with members of trio exceptions, we use this with MultiError.catch()."""
            if isinstance(e, trio.Cancelled):
                msg = "Apex shutting down"
                if msg not in error_messages:
                    error_messages.append(msg)
            elif isinstance(e, EOFError):
                error_messages.append("Connection closed")
            elif isinstance(e, ApexError):
                error_messages.append(str(e))
            else:
                error_messages.append(f"{type(e).__name__}: {e}")
            if isinstance(e, Exception):
                return None  # We catch and swallow most exceptions
            else:
                return e  # But not if a BaseException, most likely trio.Cancelled

        try:
            with trio.MultiError.catch(exception_handler):
                async with trio.open_nursery() as nursery:
                    nursery.start_soon(buffered_writer.perform_writes)
                    nursery.start_soon(read_to_channel)
                    nursery.start_soon(read_from_channel)
        finally:
            if read_buffer:
                if len(read_buffer) > 40:
                    buf_str = repr(read_buffer[:40])[1:] + "..."
                else:
                    buf_str = repr(read_buffer[:40])
                error_messages.append(f" ({len(read_buffer)} read bytes outstanding: {buf_str})")
            error = "; ".join(error_messages)
            logger.info(f"Connection {connection_id} fatal error: {error}")
            connection.handle_closed()
            self.callbacks.on_disconnect(
                DisconnectionRecord(connection_id, datetime.utcnow(), error)
            )
            with trio.move_on_after(2):
                await stream.aclose()

    async def _do_run(self):
        with self.top_level_cancel_scope:
            async with trio.open_nursery() as nursery:
                assert isinstance(nursery, trio.Nursery)
                for connection_config in self.config["connections"]:
                    # Start by binding connection config to parameter of self.serve() function
                    handler = functools.partial(self.serve, connection_config=connection_config)
                    if connection_config.get("outbound"):
                        # Open outbound socket connection
                        nursery.start_soon(
                            connect_tcp_repeatedly,
                            handler,
                            connection_config["host"],
                            connection_config["port"],
                        )
                    else:
                        # Open the socket for listening
                        # Use nursery.start rather than nursery.start_soon to make sure the port
                        # is open before on_startup_complete is called
                        await nursery.start(trio.serve_tcp, handler, connection_config["port"])

                # Set startup as complete
                self.callbacks.on_startup_complete.set()

    def run(self):
        trio.run(self._do_run)

    def stop(self):
        self.top_level_cancel_scope.cancel()


@functools.singledispatch
def get_peername(_, /) -> str:
    return "unknown"


@get_peername.register
def get_peername_stream(stream: trio.SocketStream, /) -> str:
    return ":".join(str(x) for x in stream.socket.getpeername())


@get_peername.register
def get_peername_config(config: dict, /) -> str:
    def try_mqtt(_config) -> str:
        if _config.get("peername"):
            return _config["peername"]
        inbound_topic = _config.get("inbound_topic", "").strip()
        outbound_topic = _config.get("inbound_topic", "").strip()
        if not (inbound_topic and outbound_topic):
            return ""
        return f"in:{inbound_topic},out:{outbound_topic}"

    return try_mqtt(config) or get_peername(None)


def _get_parser(
    message_format: MessageFormat = MessageFormat.DEFAULT,
    enable_message_conversion: bool = True,
    enable_sensor_id_auto: bool = True,
    sapient_version: SapientVersion = SapientVersion.LATEST,
):
    if not enable_message_conversion:
        return functools.partial(
            parse_proto,
            enable_message_conversion=False,
            sapient_version=sapient_version,
        )
    if message_format == MessageFormat.PROTO:
        return functools.partial(
            parse_proto,
            enable_message_conversion=True,
            sapient_version=sapient_version,
        )
    if message_format == MessageFormat.XML:
        return functools.partial(parse_xml, enable_sensor_id_auto=enable_sensor_id_auto)
    raise NotImplementedError("unknown parser")


def normalize_connection_config(config: dict, enable_conversion: bool = True) -> dict:
    config = config.copy()
    config["format"] = (
        MessageFormat[config.get("format", "XML")] if enable_conversion else MessageFormat.PROTO
    )
    if "icd_version" not in config:
        config["icd_version"] = (
            SapientVersion.VERSION6
            if config["format"] == MessageFormat.XML
            else SapientVersion.LATEST
        )
    else:
        format = config["icd_version"].upper().replace(" ", "_").replace(".", "_")
        config["icd_version"] = SapientVersion[format]
    return config
