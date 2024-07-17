#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

from threading import Thread
from fastapi import FastAPI
import uvicorn
import contextlib
import time


class Server(uvicorn.Server):
    def install_signal_handlers(self) -> None:
        pass

    @contextlib.contextmanager
    def run_in_thread(self):
        thread = Thread(target=self.run)
        thread.start()
        try:
            while not self.started:
                time.sleep(1e-3)
            yield

        finally:
            self.should_exit = True
            thread.join()


def create_server(app: FastAPI, config: dict) -> Server:
    server_config = uvicorn.Config(
        app=app,
        host=config.get("apiConfig", {}).get("host", "127.0.0.1"),
        port=config.get("apiConfig", {}).get("port", 8080),
    )
    return Server(config=server_config)
