#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Main window of Apex GUI.

The window is responsible for starting the database thread and telling it what file to open, and
controls the bar across the top with the database file name and error status. Aside from that, it
delegates to the other widgets by creating them and putting them in a QTabWidget.
"""

from pathlib import Path
import sys
import os


from PySide6.QtCore import QSize, QMargins, QModelIndex, Qt, QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QFileDialog,
)

from sapient_apex_qt_helpers.view_builder import build_view

from sapient_apex_gui.core.database_thread import (
    DatabaseThread,
    OpenDatabaseResponse,
    DatabaseExecuteRequest,
    DatabaseResponse,
)
from sapient_apex_gui.connections.connections_tab import ConnectionsTab
from sapient_apex_gui.message_types.message_types_tab import MessageTypesTab
from sapient_apex_gui.messages.messages_tab import MessagesTab


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_thread = DatabaseThread()
        self.filename_label = QLabel()
        self.tab_widget = QTabWidget()
        self.messages_tab = MessagesTab(self.db_thread)
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_rollover_timer)

        view = {
            "size": QSize(1000, 300),
            "windowTitle": "Apex GUI",
            QVBoxLayout(): {
                "contentsMargins": QMargins(0, 0, 0, 0),
                "spacing": 0,
                QHBoxLayout(): {
                    "contentsMargins": QMargins(5, 1, 5, 1),
                    self.filename_label: {
                        "text": "(Loading ...)",
                    },
                    QPushButton("Open ..."): {
                        "maximumWidth": 100,
                        "clicked": self.on_open_button_clicked,
                    },
                },
                self.tab_widget: {
                    (ConnectionsTab(self.db_thread), "Connections"): {
                        "doubleClicked": self.on_connection_double_clicked
                    },
                    (MessageTypesTab(self.db_thread), "Message Types"): {},
                    (self.messages_tab, "Messages"): {},
                },
            },
        }
        build_view(self, view)

        self.startup_open_database()
        self.timer.start(1000)

    def on_rollover_timer(self):
        req = DatabaseExecuteRequest(
            name="get information",
            query="SELECT relative_filepath, absolute_filepath FROM RolloverFilename;",
            params=(),
            callback=self.on_rollover_fetched,
            should_fetch_results=True,
        )
        self.db_thread.put(req)

    def on_rollover_fetched(self, response: DatabaseResponse):
        if len(response.results) > 0:
            relative_path = response.results[0]["relative_filepath"]
            absolute_path = response.results[0]["absolute_filepath"]
            if os.path.isfile(relative_path):
                self.db_thread.open(str(relative_path), self.on_open_database_response)
            elif os.path.isfile(absolute_path):
                self.db_thread.open(str(absolute_path), self.on_open_database_response)
        self.timer.start()

    def closeEvent(self, event):
        self.db_thread.stop()

    def startup_open_database(self):
        if len(sys.argv) > 1:
            self.db_thread.open(sys.argv[1], self.on_open_database_response)
            return

        db_paths = sorted(Path("data").glob("*.sqlite"))
        if not db_paths:
            self.filename_label.setText("(No database found and no path passed on command line)")
            return

        self.db_thread.open(str(db_paths[-1]), self.on_open_database_response)

    def on_open_button_clicked(self):
        path = Path().resolve()
        data_path = path.joinpath("data")
        if data_path.exists():
            path = data_path
        result = QFileDialog.getOpenFileName(
            self, "Open Database", str(path), "SQLite databases (*.sqlite)"
        )
        if isinstance(result, tuple):
            # Seems to be returning (filename, filter) tuple, but all docs say just the filename is
            # returned - bug in one version of Qt?
            result = result[0]
            assert isinstance(result, str)
        if not result:
            # Empty string means user clicked cancel
            return

        self.filename_label.setText("Opening ...")
        self.db_thread.open(result, self.on_open_database_response)

    def on_open_database_response(self, response: OpenDatabaseResponse):
        if response.error_str:
            label_text = f"({response.error_str}) {response.filename}"
        else:
            label_text = response.filename
            if response.is_live:
                self.timer.start()
            else:
                self.timer.stop()
        self.messages_tab.set_conversion_flag(response.conversion_enabled)
        self.filename_label.setText(label_text)

    def on_connection_double_clicked(self, index: QModelIndex):
        first_column = index.siblingAtColumn(0)  # Connection ID is stored in first column
        connection_id = first_column.model().itemFromIndex(first_column).data(Qt.UserRole)
        if connection_id is None:
            # This is a summary row with multiple active connections
            return
        self.messages_tab.set_connection_id(connection_id)
        self.tab_widget.setCurrentWidget(self.messages_tab)
