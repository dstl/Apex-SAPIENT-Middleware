#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Thread to execute database queries so that the GUI thread is not held up.

This class starts a thread and allows database queries to be run on it. Callers are responsible for
supplying the SQL and parameters, and these requests are passed to the database thread using a
standard Python queue.Queue. Responses are passed back to the main thread using a private signal and
slot that are connected to each other, which then calls the callback supplied in the request.

The request also includes a function that is called for each row of the query and the result is
added to the list ultimately passed to the callback. This allows the row data to be turned into some
more useful structure. If this function is not passed then no attempt is made to look at the result
of the query, which is useful for write-only queries like inserts and index creation.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Callable, Optional, Sequence, Union

from PySide6 import QtCore
from sqlalchemy import Row, create_engine, select, text
from sqlalchemy.exc import SQLAlchemyError

from sapient_apex_server.sqlite_schema import RolloverFilename, Version

logger = logging.getLogger("apex_gui")

# Apex GUI supported variant and version
_SUPPORTED_DB_VARIANT = "Apex"
_SUPPORTED_DB_VERSION = 1


@dataclass
class DatabaseResponse:
    """Response to a database query"""

    # Parameters that were supplied in the request
    params: Union[tuple, dict]
    # Result rows
    results: Sequence[Row]
    # Time in milliseconds that query took to execute
    time_taken: int
    # Time at which the query was run (specifically, when it finished)
    time_finished: datetime


@dataclass
class DatabaseExecuteRequest:
    """Contains a database query to be passed from GUI thread to database thread"""

    # Just for debugging purposes, name of query
    name: str
    # SQL of query to execute
    query: str
    # Parameters to the query
    params: dict = field(default=dict)
    # Callback that will be supplied with result of query, if not None
    callback: Optional[Callable[[DatabaseResponse], None]] = None
    # Whether to fetch results (False is useful for write queries like creating indices)
    should_fetch_results: bool = False


@dataclass
class OpenDatabaseResponse:
    """Response to a database open request"""

    # Database that was opened (or attempted)
    filename: str
    # Error string, if any error occurred
    error_str: Optional[str]
    # Flag if db is live or old
    is_live: bool
    # Flag if message conversion was enabled when db was created
    conversion_enabled: bool


@dataclass
class OpenDatabaseRequest:
    """Request to open a different database, used on startup and when open button is clicked"""

    # What file to open
    filename: str
    # Callback to main thread to return status
    callback: Callable[[OpenDatabaseResponse], None]


class DatabaseThread(QtCore.QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._supported_db_variant = _SUPPORTED_DB_VARIANT
        self._supported_db_version = _SUPPORTED_DB_VERSION
        self._queue = Queue()
        self._response_signal.connect(self._handle_response)
        self._connection = None
        self._thread = Thread(target=self._run, name="db")
        self._thread.start()

    def put(self, request: DatabaseExecuteRequest):
        self._queue.put(request)

    def open(self, filename: str, callback: Callable[[OpenDatabaseResponse], None]):
        self._queue.put(OpenDatabaseRequest(filename, callback))

    def stop(self):
        self._queue.put(None)
        self._thread.join()

    # Internal signal to move call back to main thread.
    _response_signal = QtCore.Signal(object, object)

    def _handle_response(self, callback: Callable[[object], None], results):
        callback(results)

    def _run(self):
        while True:
            req = self._queue.get()
            if req is None:
                logger.debug("Database thread exiting")
                return
            elif isinstance(req, OpenDatabaseRequest):
                self._handle_open_request(req)
            elif isinstance(req, DatabaseExecuteRequest):
                self._handle_execute_request(req)
            else:
                logger.error(f"Invalid database request: {req}")

    def _db_version_supported(self, db_version_rows):
        version = None
        error_str = None
        conversion_enabled = True
        for _, db_variant, db_version, conversion_enabled_flag in db_version_rows:
            conversion_enabled = bool(conversion_enabled_flag)
            if db_variant == self._supported_db_variant:
                version = db_version
        if version is None:
            error_str = (
                f"Could not find supported database version variant: {self._supported_db_variant}"
            )
            logger.error(error_str)
        elif version != self._supported_db_version:
            error_str = (
                f"Unsupported database version: {version},                  Supported version:"
                f" {self._supported_db_version}"
            )
            logger.error(error_str)
        if error_str:
            logger.error("Database version validation failed, GUI may not operate as expected")
        return error_str, conversion_enabled

    def _handle_open_request(self, req: OpenDatabaseRequest):
        logger.info(f"Opening SQLite database with filename: {req.filename}")
        error_str = None
        rollover_result = None
        conversion_enabled = True
        if not Path(req.filename).exists():
            error_str = "Could not find file"
            self._connection = None
        else:
            try:
                if ":///" not in req.filename:
                    req.filename = f"sqlite:///{req.filename}"
                self._engine = create_engine(req.filename)
                self._connection = self._engine.connect()
                with self._connection.begin():
                    # SQLite only checks the connection when a query is run
                    # Also need to check if db is live or old
                    rollover_result = self._connection.execute(select(RolloverFilename)).fetchall()
                    db_version_rows = self._connection.execute(select(Version)).fetchall()
                error_str, conversion_enabled = self._db_version_supported(db_version_rows)
            except SQLAlchemyError as e:
                error_str = f"{type(e).__name__}: {e}"
                logger.error(f"While opening {req.filename} caught {error_str}")
                self._connection = None
        is_live = rollover_result is not None and len(rollover_result) == 0
        response = OpenDatabaseResponse(req.filename, error_str, is_live, conversion_enabled)
        self._response_signal.emit(req.callback, response)

    def _handle_execute_request(self, req: DatabaseExecuteRequest):
        start_time = time.perf_counter()
        results = []
        if self._connection is not None:
            try:
                with self._connection.begin():
                    cursor = self._connection.execute(text(req.query), req.params)
                    if req.should_fetch_results is not None:
                        results = cursor.fetchall()
            except SQLAlchemyError as e:
                logger.error(f"For query {req.name} got error: {e}")
        time_taken = int((time.perf_counter() - start_time) * 1000)
        logger.debug(
            f"For query '{req.name}' (params {req.params}) got {len(results)} rows"
            f" in {time_taken}ms"
        )
        if req.callback is not None:
            response = DatabaseResponse(req.params, results, time_taken, datetime.utcnow())
            self._response_signal.emit(req.callback, response)
