from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from time import time_ns
from typing import NoReturn, Optional, Sequence
from uuid import UUID, uuid4

import trio
import ulid
from google.protobuf.json_format import MessageToJson
from google.protobuf.json_format import Parse as MessageFromJson
from plotille import Figure
from sqlalchemy import Engine, insert, select

from sapient_apex_server.message_io import encode_binary
from sapient_apex_server.structures import SapientVersion
from sapient_apex_server.translator.proto_to_proto_translator import (
    empty_sapient_message,
)
from sapient_apex_server.trio_util import receive_size_prefixed
from sapient_msg.latest.sapient_message_pb2 import SapientMessage
from sapient_msg.testing.messages import registration_message, status_message
from tests.loadtesting.basetask import LoadTestBaseTask
from tests.loadtesting.schema import Event, get_engine


@dataclass
class Message:
    id: int
    is_sent: bool
    event_date: datetime
    scenario_id: int
    message: SapientMessage


async def log_messages(
    engine: Engine,
    stream: trio.abc.ReceiveStream,
    version: SapientVersion,
    scenario_id: int,
) -> NoReturn:
    buffer = bytearray()
    while True:
        message_bytes = await receive_size_prefixed(stream, buffer, max_size=4096)
        received = time_ns()
        message = empty_sapient_message(version)
        message.ParseFromString(bytes(message_bytes))
        json = MessageToJson(message)
        with engine.connect() as connection, connection.begin():
            connection.execute(
                insert(Event).values(
                    {
                        "event_date": datetime.fromtimestamp(received * 1e-9),
                        "scenario_id": scenario_id,
                        "json": json,
                        "is_sent": False,
                    }
                )
            )


async def create_node(
    hostname: str, port: int, engine: Engine, scenario_id: int, nursery: trio.Nursery
) -> trio.abc.SendStream:
    stream = await trio.open_tcp_stream(hostname.strip(), port)

    async def log_node_message():
        await log_messages(engine, stream, SapientVersion.LATEST, scenario_id)

    nursery.start_soon(log_node_message)

    return stream


async def register_node(
    hostname: str, port: int, engine: Engine, scenario_id: int, nursery: trio.Nursery, **kwargs
) -> tuple[UUID, trio.abc.SendStream]:
    uuid = kwargs.pop("node_id", str(uuid4()))
    message = registration_message(node_id=uuid, **kwargs)
    json = MessageToJson(message)

    stream = await create_node(hostname, port, engine, scenario_id, nursery)
    binary = encode_binary(message)
    sent = time_ns()
    await stream.send_all(binary)

    with engine.connect() as connection, connection.begin():
        connection.execute(
            insert(Event).values(
                {
                    "event_date": datetime.fromtimestamp(sent * 1e-9),
                    "scenario_id": scenario_id,
                    "json": json,
                    "is_sent": True,
                }
            )
        )

    return uuid, stream


async def registration_scenario(
    hostname: str,
    port: int,
    engine: Engine,
    scenario_id: int,
    nursery: trio.Nursery,
    heartbeat_s: float = 1.0,
    registration_details: Optional[dict] = None,
    status_details: Optional[dict] = None,
) -> NoReturn:
    """Register new node and sends heartbeats for ever."""
    uuid, stream = await register_node(
        hostname, port, engine, scenario_id, nursery, **(registration_details or {})
    )
    status_details = status_details or {}
    status_details["node_id"] = uuid
    message = status_message(**status_details)

    async def send_message(message):
        message.status_report.report_id = ulid.new().str
        message.timestamp.GetCurrentTime()

        binary = encode_binary(message)
        sent = time_ns()
        await stream.send_all(binary)

        with engine.connect() as connection, connection.begin():
            connection.execute(
                insert(Event).values(
                    {
                        "event_date": datetime.fromtimestamp(sent * 1e-9),
                        "scenario_id": scenario_id,
                        "json": MessageToJson(message),
                        "is_sent": True,
                    }
                )
            )

    await send_message(message)
    while True:
        await trio.sleep(heartbeat_s)
        await send_message(message)


class LoadTestTaskRegistration(LoadTestBaseTask):
    def __init__(
        self,
        database: str = ":memory:",
        apex_hostname: str = "127.0.0.1",
        child_port: int = 5020,
        peer_port: int = 5002,
        heartbeat_interval_s: float = 2,
    ) -> None:
        self.apex_hostname = apex_hostname
        self.engine = get_engine(database)
        self.child_port = child_port
        self.peer_port = peer_port
        self.heartbeat_interval = heartbeat_interval_s

    @property
    def parameters(self) -> dict:
        return {
            "apex_hostname": self.apex_hostname,
            "child_port": self.child_port,
            "peer_port": self.peer_port,
            "heartbeat_interval": self.heartbeat_interval,
        }

    async def setup(self, *, nursery: trio.Nursery, scenario_id: int, **_) -> None:
        await register_node(self.apex_hostname, self.peer_port, self.engine, scenario_id, nursery)

    async def __call__(self, *, nursery: trio.Nursery, scenario_id: int, **_) -> None:
        await registration_scenario(
            self.apex_hostname,
            self.child_port,
            self.engine,
            scenario_id,
            nursery,
            heartbeat_s=self.heartbeat_interval,
        )

    def analyze(self, scenario_id: int):
        messages = get_scenario_messages(self.engine, scenario_id)

        def statistics(data: Sequence[float]) -> tuple[float, float]:
            avg = sum(data) / len(data)
            stddev = sqrt(sum((x - avg) * (x - avg) for x in data) / len(data))
            return avg, stddev

        avg, stddev = statistics(ack_return(messages)[1])
        print(
            "Registration acknowledgments latency:\n"
            f"  - average (s): {avg}\n"
            f"  - stdandard deviation (s): {stddev}\n"
        )

        avg, stddev = statistics(registration_passthrough(messages)[1])
        print(
            "Registration message latency from child node to peer node:\n"
            f"  - average (s): {avg}\n"
            f"  - stdandard deviation (s): {stddev}\n"
        )

        avg, stddev = statistics(status_report_passthrough(messages)[1])
        print(
            "Status report latency from child node to peer node:\n"
            f"  - average (s): {avg}\n"
            f"  - stdandard deviation (s): {stddev}\n"
        )

    def plot_cli_figure(self, scenario_id: int):
        messages = get_scenario_messages(self.engine, scenario_id)
        print(plot_figures(messages).show(legend=True))


def plot_figures(messages: Sequence[Message]) -> Figure:
    fig = figure(*ack_return(messages), label="registration", lc=25)
    figure(
        *status_report_passthrough(
            messages,
        ),
        fig=fig,
        label="status report",
        lc=200,
    )
    return figure(*registration_passthrough(messages), fig=fig, label="acknowledgments", lc=100)


def registration_passthrough(messages: Sequence[Message]) -> tuple[list[float], list[float]]:
    messages = [m for m in messages if m.message.WhichOneof("content") == "registration"]

    sent = {m.message.node_id: m.event_date for m in messages if m.is_sent}
    received = {m.message.node_id: m.event_date for m in messages if not m.is_sent}
    keys = [u[0] for u in sorted(sent.items(), key=lambda x: x[1]) if u[0] in received]

    x = [(sent[k] - sent[keys[0]]).total_seconds() for k in keys]
    y = [(received[k] - sent[k]).total_seconds() for k in keys]
    return x, y


def ack_return(messages: Sequence[Message]) -> tuple[list[float], list[float]]:
    sent = {
        m.message.node_id: m.event_date
        for m in messages
        if m.is_sent and m.message.WhichOneof("content") == "registration"
    }
    received = {
        m.message.destination_id: m.event_date
        for m in messages
        if not m.is_sent and m.message.WhichOneof("content") == "registration_ack"
    }
    keys = [u[0] for u in sorted(sent.items(), key=lambda x: x[1]) if u[0] in received]

    x = [(sent[k] - sent[keys[0]]).total_seconds() for k in keys]
    y = [(received[k] - sent[k]).total_seconds() for k in keys]
    return x, y


def status_report_passthrough(messages: Sequence[Message]) -> tuple[list[float], list[float]]:
    messages = [m for m in messages if m.message.WhichOneof("content") == "status_report"]

    sent = {m.message.status_report.report_id: m.event_date for m in messages if m.is_sent}
    received = {m.message.status_report.report_id: m.event_date for m in messages if not m.is_sent}
    keys = [u[0] for u in sorted(sent.items(), key=lambda x: x[1]) if u[0] in received]

    x = [(sent[k] - sent[keys[0]]).total_seconds() for k in keys]
    y = [(received[k] - sent[k]).total_seconds() for k in keys]
    return x, y


def figure(
    x: Sequence[float], y: Sequence[float], fig: Optional[Figure] = None, **kwargs
) -> Figure:
    if fig is None:
        fig = Figure()
        fig.with_colors = True
        fig.x_label = "Load-testing time(s)"
        fig.y_label = "Latency(s)"
        fig.color_mode = "byte"
    fig.scatter(x, y, **kwargs)
    return fig


def get_scenario_messages(engine: Engine, scenario_id: int):
    def read_message(data: str) -> SapientMessage:
        result = SapientMessage()
        MessageFromJson(data, result)
        return result

    with engine.connect() as connection:
        events = connection.execute(
            select(Event).where(Event.scenario_id == scenario_id).order_by(Event.event_date)
        ).fetchall()

        return [
            Message(
                id=u[0],
                is_sent=u[1],
                event_date=u[2],
                scenario_id=u[3],
                message=read_message(u[-1]),
            )
            for u in events
        ]
