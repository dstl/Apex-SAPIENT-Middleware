#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import math
from collections.abc import Callable
from typing import Optional, Union
from unittest.mock import MagicMock

import trio
from pytest import fixture
from typing_extensions import Self

from sapient_apex_server.apex_server import ApexServer, Callbacks
from sapient_apex_server.connection import MessageFormat


class MockStream(trio.abc.Stream):
    def __init__(self, sending, receiving):
        super().__init__()
        self.sending = sending
        self.receiving = receiving

    def __aenter__(self) -> Self:
        return self

    async def aclose(self) -> None:
        return

    async def receive_some(self, max_bytes: Optional[int] = None) -> Union[bytes, bytearray]:
        return await self.receiving.receive()

    async def send_all(self, data: Union[bytes, bytearray, memoryview]) -> None:
        await self.sending.send(data)

    async def wait_send_all_might_not_block(self) -> None:
        pass


@fixture
def callbacks() -> Callbacks:
    return Callbacks(MagicMock(), MagicMock(), MagicMock(), MagicMock())


@fixture
async def server(callbacks):
    with trio.fail_after(30):
        config = {
            "messageMaxSizeKb": 1_000,
            "enableTimeSyncAdjustment": False,
            "enableMessageConversion": True,
            "connections": [],
        }
        server = ApexServer(callbacks, config)
        await server._do_run()
        yield server
        server.stop()


@fixture
def add_dummy_node(server: ApexServer, nursery) -> Callable:
    def add_stream(type: str, format: str = "XML", **kwargs) -> trio.abc.Stream:
        from_node = trio.open_memory_channel(max_buffer_size=math.inf)
        to_node = trio.open_memory_channel(max_buffer_size=math.inf)
        server_side = MockStream(from_node[0], to_node[1])
        asm_side = MockStream(to_node[0], from_node[1])
        nursery.start_soon(server.serve, server_side, {**kwargs, "type": type, "format": format})
        if type.strip().lower() == "dmm":
            server.connection_creator.shared_data.dmm_msg_format = MessageFormat[format]
        return asm_side

    return add_stream
