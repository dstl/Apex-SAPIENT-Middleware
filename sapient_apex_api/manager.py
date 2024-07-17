#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""This file contains all operations that Apex will need to perform that interact
with a database.

To abstract away specific database implementations, the interface package contains
the base CRUD operations for each database, which allows Apex to easily change
the database implementation by just swiching which interface this manager uses."""

import logging

from sapient_apex_api.interface.base_interface import BaseInterface
from sapient_apex_server.structures import MessageRecord

logger = logging.getLogger(__name__)


class Manager:
    index: str = "messages"

    def __init__(self, interface: BaseInterface):
        self.interface = interface

    def add_sapient_message(self, msg: MessageRecord):
        if msg.parsed is None:
            # Seems to be the case for ApexRecorder messages and will throw exceptions
            # Also we dont want duplicated messages in the (elastic) database.
            return

        logger.debug(
            f"inserting SAPIENT message with node id [{msg.parsed.node_id}] and timestamp"
            f" [{msg.parsed.message_timestamp}] into {self.index} index"
        )
        message = msg.parsed.get_message_json()
        if message:
            self.interface.insert_into(self.index, message)
            logger.debug(
                f"Successfully inserted SAPIENT message with node id [{msg.parsed.node_id}] and"
                f" timestamp [{msg.parsed.message_timestamp}] into {self.index} index"
            )
        else:
            logger.error(
                f"Could not insert message with id [{msg.parsed.node_id}] and timestamp"
                f" [{msg.parsed.message_timestamp}]"
            )
