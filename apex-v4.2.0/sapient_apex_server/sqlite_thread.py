#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import itertools
import logging
import sys
from datetime import datetime, timedelta
from threading import Condition, Semaphore, Thread
from typing import Optional

from sapient_apex_server.sqlite_saver import SqliteSaver
from sapient_apex_server.sqlite_saver import rollover as rollover_impl
from sapient_apex_server.structures import (
    ConnectionRecord,
    DisconnectionRecord,
    MessageRecord,
)

logger = logging.getLogger("apex")


class SqliteThread:
    def __init__(self, filename, rollover_config, conversion_enabled):
        self.pending = []
        # Semaphore for waiting for thread to start and db to initialise
        self.start_semaphore = Semaphore(value=0)
        # Condition variable for passing insert requests to the thread
        self.condition = Condition()
        self.filename = filename
        self.rollover_config = rollover_config
        self.conversion_enabled = conversion_enabled

        if self.rollover_config.get("enable"):
            unit = self.rollover_config.get("unit")
            value = self.rollover_config.get("value")
            # Validate rollover value
            if not isinstance(value, int):
                logger.critical("Error: rollover_value must be an integer")
                sys.exit(1)
            if value < 1:
                logger.critical("Error: rollover_value value must be greater than 1")
                sys.exit(1)

            # Validate rollover unit
            if not isinstance(unit, str):
                logger.critical("Error: rollover_unit must be a string")
                sys.exit(1)
            if unit not in ["days", "seconds", "minutes", "hours", "weeks"]:
                logger.critical(
                    "Error: rollover_unit only supports: weeks, days, hours, minutes, or seconds."
                )
                sys.exit(1)
            self.rollover_interval = timedelta(**{unit: value})
        else:
            self.rollover_interval = timedelta(weeks=52)

        self.thread = Thread(target=self.run)
        self.thread.start()
        # Wait for database to be created (if not already finished)
        self.start_semaphore.acquire()

    def add(self, item: Optional[MessageRecord]):
        with self.condition:
            self.pending.append(item)
            self.condition.notify()

    def rollover(self, old_saver: SqliteSaver) -> SqliteSaver:
        return rollover_impl(old_saver, conversion_enabled=self.conversion_enabled)

    def stop(self):
        self.add(None)

    def run(self):
        saver = SqliteSaver(self.filename, self.conversion_enabled)
        self.start_semaphore.release()
        next_rollover = datetime.now() + self.rollover_interval
        while True:
            with self.condition:
                self.condition.wait(timeout=1)

            # Check if database needs to rollover before writting
            if self.rollover_config.get("enable") is True and datetime.now() >= next_rollover:
                logger.info("Database rollover starting...")
                new_saver = self.rollover(saver)
                if new_saver is not None:
                    saver.close()
                    saver = new_saver
                    logger.info("Database rollover complete.")
                next_rollover = datetime.now() + self.rollover_interval

            if len(self.pending) > 0:
                last_pending = self.pending
                self.pending = []  # Allow more items to be added to list while processing these
                # Deliberately do not sort before groupby so that order is preserved.
                # e.g. if queue is (Msg, Msg, Conn, Msg, Msg, Msg), we end up with groups:
                # [(Msg, Msg), (Conn,), (Msg, Msg, Msg)]
                # last_pending = sorted(last_pending, key=lambda x: str(type(x)))
                # Needed for groupby()
                for this_type, items in itertools.groupby(last_pending, key=type):
                    if issubclass(this_type, ConnectionRecord):
                        for next_msg in items:
                            saver.insert_connection(next_msg)
                    elif issubclass(this_type, DisconnectionRecord):
                        for next_msg in items:
                            saver.update_disconnection(next_msg)
                    elif issubclass(this_type, MessageRecord):
                        items = list(items)  # Convert from an iterator into a proper list
                        chunk_size = 50  # Prevent too many messages from being written at once.
                        for items_start in range(0, len(items), chunk_size):
                            saver.insert_message_multi(
                                items[items_start : items_start + chunk_size]
                            )
                    elif issubclass(this_type, type(None)):
                        logger.info("SqliteThread exiting")
                        saver.close()
                        return
                    else:
                        logger.error(f"SqliteThread got unknown type {this_type}")

    def join(self):
        self.thread.join()
