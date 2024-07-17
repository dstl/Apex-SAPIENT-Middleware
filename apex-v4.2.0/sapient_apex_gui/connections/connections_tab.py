#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Tab showing connections grouped by Node ID in a QTreeView."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QTreeView

from sapient_apex_gui.connections.connections_query import (
    ConnectionInfo,
    sql_get_connections,
)
from sapient_apex_gui.connections.tree_builder import column_names, connections_to_tree
from sapient_apex_gui.core.database_thread import (
    DatabaseExecuteRequest,
    DatabaseResponse,
    DatabaseThread,
)
from sapient_apex_qt_helpers.model_merger import ModelMerger


class ConnectionsTab(QTreeView):
    def __init__(self, db_thread: DatabaseThread):
        super().__init__()
        self.db_thread = db_thread
        self.model_merger = ModelMerger(column_names)
        self.setModel(self.model_merger.model)
        self.setColumnWidth(0, 200)  # Leave plenty of space for Node type
        self.setColumnWidth(2, 150)  # A bit of extra space needed for disconnection
        self.setExpandsOnDoubleClick(False)  # Double click switches to messages tab instead
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.on_timer)
        self.timer.start()

    def on_timer(self):
        req = DatabaseExecuteRequest(
            name="get connections",
            query=sql_get_connections,
            params=(),
            callback=self.on_fetched,
            should_fetch_results=True,
        )
        self.db_thread.put(req)

    def on_fetched(self, response: DatabaseResponse):
        tree_rows = connections_to_tree(
            [ConnectionInfo.from_row(r._asdict()) for r in response.results]
        )
        self.model_merger.merge(tree_rows)
        self.timer.start()
