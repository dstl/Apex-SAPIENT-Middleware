#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#
from contextlib import asynccontextmanager
import os
from datetime import datetime
from importlib.metadata import metadata
import json
import logging
from pathlib import Path
from queue import Queue
from signal import signal, SIGINT
import sys
from threading import Thread, Event
import time
from fastapi import FastAPI
from sapient_apex_api.server import create_server
from sapient_apex_api.controller import router
from sapient_apex_api.interface.elastic_interface import ElasticInterface
from sapient_apex_api.manager import Manager

from sapient_apex_server.apex_server import Callbacks, ApexServer
from sapient_apex_server.sqlite_thread import SqliteThread
from sapient_apex_server.structures import MessageRecord
from sapient_apex_server.time_util import datetime_to_str

logger = logging.getLogger("apex")


# This is a workaround for a Nuitka issue where sometimes one ctrl+C results in two exceptions
# https://github.com/Nuitka/Nuitka/issues/1477
keyboard_interrupt_count = 0


def keyboard_interrupt_handler(signum, frame):
    global keyboard_interrupt_count
    keyboard_interrupt_count += 1
    if keyboard_interrupt_count == 1:
        raise KeyboardInterrupt()


signal(SIGINT, keyboard_interrupt_handler)


def get_config():
    if len(sys.argv) > 1:
        config_filename = sys.argv[1]
    else:
        config_filename = "apex_config.json"
        if not Path(config_filename).exists() and Path("..", config_filename).exists():
            # User has started Apex in a nested directory e.g. by just double clicking apex.exe
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


class ApexMain:
    def __init__(self, config):
        self.startup_complete = Event()
        self.database = None

        # Connect to Elasticsearch
        self.database_queue = Queue()
        if config.get("elasticConfig", {}).get("enabled", False):
            self.database = ElasticInterface(config.get("elasticConfig", {}))
        if self.database:
            router.set_db_interface(self.database)
            self.manager = Manager(self.database)

        # Create the database (by running the database thread)
        Path("data").mkdir(exist_ok=True)
        date_str = datetime_to_str(datetime.utcnow()).replace(":", "-")
        sqlite_filename = f"data/data-{date_str}.sqlite"
        self.sqlite_thread = SqliteThread(
            filename=sqlite_filename,
            rollover_config=config.get("rollover"),
            conversion_enabled=config.get("enableMessageConversion", True),
        )

        def write_message_to_db(msg: MessageRecord):
            self.sqlite_thread.add(msg)
            if self.database:
                self.manager.add_sapient_message(msg)

        # Run the server
        callbacks = Callbacks(
            self.sqlite_thread.add,
            write_message_to_db,
            self.sqlite_thread.add,
            self.startup_complete,
        )
        self.server = ApexServer(callbacks, config)
        self.server_thread = Thread(target=self.server.run)
        self.server_thread.start()

    def shutdown(self):
        self.server.stop()
        self.server_thread.join()
        self.sqlite_thread.stop()
        self.sqlite_thread.join()
        if self.database:
            self.database.stop()
            self.database.join()
        self.startup_complete.clear()


def start_apex_main() -> ApexMain:
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logger.info("Starting ...")
    logger.info(f"Running on Python {sys.version}")

    config = get_config()

    root_logger = logging.getLogger()
    root_logger.setLevel(config.get("logLevel", "INFO"))

    return ApexMain(config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    apex = start_apex_main()

    yield

    apex.shutdown()
    logger.info("* * * * Shutdown complete * * * *")
    time.sleep(1)  # So above message can be seen


app = FastAPI(
    title="Apex REST API",
    description=f"""REST API to the {metadata("apex")["summary"]}""",
    version=metadata("apex")["version"],
    lifespan=lifespan,
)
app.include_router(router)


def serve_apex():
    server = create_server(app, get_config())
    with server.run_in_thread():
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.critical("Exiting...")


if __name__ == "__main__":
    serve_apex()
