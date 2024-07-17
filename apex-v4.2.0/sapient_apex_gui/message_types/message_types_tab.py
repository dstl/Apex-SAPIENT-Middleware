#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Tab showing types of message received on a connection."""
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from sapient_apex_gui.core.database_thread import (
    DatabaseExecuteRequest,
    DatabaseResponse,
    DatabaseThread,
)
from sapient_apex_gui.message_types.message_type_to_tree_row import (
    message_type_column_names,
    response_to_tree_rows,
)
from sapient_apex_gui.message_types.message_types_query import sql_get_message_types
from sapient_apex_qt_helpers.model_merger import ModelMerger
from sapient_apex_qt_helpers.view_builder import build_view


class MessageTypesTab(QWidget):
    def __init__(self, db_thread: DatabaseThread):
        super().__init__()
        self.db_thread = db_thread
        self.model_merger = ModelMerger(message_type_column_names)
        self.connection_id = 1

        self.tree_view = QTreeView()
        self.connection_id_edit = QLineEdit()
        view = {
            QVBoxLayout(): {
                QHBoxLayout(): {
                    QLabel("&Connection ID"): {
                        "buddy": self.connection_id_edit,
                    },
                    self.connection_id_edit: {
                        "text": str(self.connection_id),
                        "editingFinished": self.on_editing_finished,
                    },
                },
                self.tree_view: {
                    "model": self.model_merger.model,
                },
            }
        }
        build_view(self, view)

    def on_editing_finished(self):
        try:
            self.connection_id = int(self.connection_id_edit.text())
        except ValueError:
            self.connection_id_edit.setText(str(self.connection_id))
            return
        req = DatabaseExecuteRequest(
            name="get message types",
            query=sql_get_message_types,
            params={"connection_id": self.connection_id},
            callback=self.on_fetched,
            should_fetch_results=True,
        )
        self.db_thread.put(req)

    def on_fetched(self, response: DatabaseResponse):
        if response.params["connection_id"] != self.connection_id:
            return
        tree_rows = response_to_tree_rows([r._asdict() for r in response.results])
        self.model_merger.merge(tree_rows)
