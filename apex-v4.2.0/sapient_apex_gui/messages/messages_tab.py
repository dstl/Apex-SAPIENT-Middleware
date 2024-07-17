#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

import logging
import math
import xml.etree.ElementTree as ET

from PySide6.QtCore import QMargins, QModelIndex, Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from sapient_apex_gui.core.database_thread import (
    DatabaseExecuteRequest,
    DatabaseResponse,
    DatabaseThread,
)
from sapient_apex_gui.messages.message_to_tree_row import (
    db_row_to_tree_row,
    message_column_names,
)
from sapient_apex_gui.messages.messages_query import (
    sql_count_messages,
    sql_count_messages_for_connection,
    sql_count_messages_for_connection_and_type,
    sql_count_messages_for_connection_and_type_null,
    sql_get_messages,
    sql_get_messages_for_connection,
    sql_get_messages_for_connection_and_type,
    sql_get_messages_for_connection_and_type_null,
)
from sapient_apex_qt_helpers.model_merger import ModelMerger
from sapient_apex_qt_helpers.syntax_highligher_json import SyntaxHighlighterJson
from sapient_apex_qt_helpers.syntax_highlighter_xml import SyntaxHighlighterXml
from sapient_apex_qt_helpers.view_builder import build_view

logger = logging.getLogger("apex_gui")


_COUNT_PER_PAGE = 20


def _bytes_as_hex(x: bytes) -> str:
    """Formats bytes as a side-by-side display of hex and raw characters"""
    result_lines = []
    if x:
        for i in range(0, len(x), 16):
            x_line = x[i : i + 16]
            result_lines.append(
                x_line.hex(sep=" ")
                + "   " * (16 - len(x_line))
                + "   "
                + "".join((chr(b) if 32 <= b < 127 else ".") for b in x_line)
            )
    return "\n".join(result_lines)


class MessagesTab(QWidget):
    def __init__(self, db_thread: DatabaseThread):
        super().__init__()
        # << First	< Prev	Page: 7	Of: 12	Next >	Last >>
        self.db_thread = db_thread
        self.current_page = 1
        self.last_page_pending = False
        self.current_connection_id = None
        self.current_message_type = None  # If not None, filter by this string
        self.current_message_type_is_null = False  # If True, filter by IS NULL
        self.conversion_enabled = False

        # Controls on top line
        self.current_page_edit = QLineEdit()
        self.total_pages_edit = QLineEdit()
        self.current_connection_id_edit = QLineEdit()
        self.current_message_type_edit = QLineEdit()

        # Main tree view showing list of messages
        self.messages_results_treeview = QTreeView()
        self.messages_results_model_merger = ModelMerger(message_column_names)

        # Editor showing message
        font = QFont("Consolas")
        font.setStyleHint(QFont.TypeWriter)
        font.setPointSize(10)
        self.message_xml_editor = QTextEdit()
        self.syntax_highlighter_xml = SyntaxHighlighterXml(self.message_xml_editor, font)
        self.message_json_editor = QTextEdit()
        self.syntax_highlighter_json = SyntaxHighlighterJson(self.message_json_editor, font)
        self.message_proto_editor = QTextEdit()
        self.message_proto_editor.setFont(font)
        self.message_errors = QTextEdit()

        view = {
            QVBoxLayout(): {
                # Top toolbar for setting connection ID
                QHBoxLayout(): {
                    QLabel("&Connection ID:"): {
                        "buddy": self.current_connection_id_edit,
                    },
                    self.current_connection_id_edit: {
                        "returnPressed": self.get_results,
                    },
                    QLabel("(Leave blank to search over all connections)"): {},
                },
                # Second toolbar for setting message type
                QHBoxLayout(): {
                    QLabel("&Message Type:"): {
                        "buddy": self.current_message_type_edit,
                    },
                    self.current_message_type_edit: {
                        "returnPressed": self.get_results,
                    },
                    QLabel(
                        "(Only valid if connection ID set; blank for all, 'null' for unparsed)"
                    ): {},
                },
                # Third toolbar for navigating pages
                QHBoxLayout(): {
                    QPushButton("<< First"): {"clicked": self.page_first},
                    QPushButton("< Prev"): {"clicked": self.page_previous},
                    QLabel("&Page:"): {
                        "buddy": self.current_page_edit,
                    },
                    self.current_page_edit: {
                        "returnPressed": self.get_results,
                        "text": "1",
                    },
                    QLabel("Of:"): {},
                    self.total_pages_edit: {
                        "readOnly": True,
                        "text": "0",
                    },
                    QPushButton("Next >"): {
                        "clicked": self.page_next,
                    },
                    QPushButton("Last >>"): {
                        "clicked": self.page_last,
                    },
                },
                QSplitter(): {
                    "orientation": Qt.Vertical,
                    # List of messages
                    self.messages_results_treeview: {
                        "model": self.messages_results_model_merger.model,
                    },
                    # Individual message content, along with side buttons
                    QTabWidget(): {
                        # XML message tab
                        (QHBoxLayout(), "XML"): {
                            "contentsMargins": QMargins(0, 0, 0, 0),
                            self.message_xml_editor: {},
                            QVBoxLayout(): {
                                "contentsMargins": QMargins(0, 0, 0, 0),
                                QPushButton("Copy"): {"clicked": self.copy_xml_message},
                                QPushButton("Indent"): {"clicked": self.indent_xml_message},
                                QCheckBox("Highlight"): {
                                    "checked": True,
                                    "clicked": self.syntax_xml_check_changed,
                                },
                            },
                        },
                        # JSON message tab
                        (QHBoxLayout(), "JSON"): {
                            "contentsMargins": QMargins(0, 0, 0, 0),
                            self.message_json_editor: {},
                            QVBoxLayout(): {
                                "contentsMargins": QMargins(0, 0, 0, 0),
                                QPushButton("Copy"): {"clicked": self.copy_json_message},
                                QCheckBox("Highlight"): {
                                    "checked": True,
                                    "clicked": self.syntax_json_check_changed,
                                },
                            },
                        },
                        # proto message tab
                        (QHBoxLayout(), "Proto"): {
                            "contentsMargins": QMargins(0, 0, 0, 0),
                            self.message_proto_editor: {},
                            QVBoxLayout(): {
                                "contentsMargins": QMargins(0, 0, 0, 0),
                                QPushButton("Copy All"): {"clicked": self.copy_proto_message_all},
                                QPushButton("Copy Hex"): {"clicked": self.copy_proto_message_hex},
                            },
                        },
                        # Errors tab
                        (QHBoxLayout(), "Errors"): {
                            "contentsMargins": QMargins(0, 0, 0, 0),
                            self.message_errors: {},
                            QVBoxLayout(): {
                                "contentsMargins": QMargins(0, 0, 0, 0),
                                QPushButton("Copy"): {"clicked": self.copy_error_message},
                            },
                        },
                    },
                },
            }
        }
        build_view(self, view)

        # Connect a signal in the QTreeView's selection model, must happen after build_view.
        self.messages_results_treeview.selectionModel().currentChanged.connect(
            self.on_selection_changed
        )

    def set_conversion_flag(self, flag: bool):
        self.conversion_enabled = flag

    def db_fetch_messages(self):
        request = DatabaseExecuteRequest(
            name="get messages",
            query=sql_get_messages,
            params={
                "count_per_page": _COUNT_PER_PAGE,
                "current_page": self.current_page,
            },
            callback=self.on_messages_fetched,
            should_fetch_results=True,
        )
        if self.current_connection_id is not None:
            request.params["connection_id"] = self.current_connection_id
        if self.current_message_type_is_null:
            request.name = "get msgs conn null type"
            request.query = sql_get_messages_for_connection_and_type_null
        elif self.current_message_type is not None:
            request.name = "get msgs conn type"
            request.query = sql_get_messages_for_connection_and_type
            request.params["parsed_type"] = self.current_message_type
        else:
            request.name = "get msgs for conn"
            request.query = sql_get_messages_for_connection

        self.db_thread.put(request)

    def db_count_messages(self):
        request = DatabaseExecuteRequest(
            name="count messages",
            query=sql_count_messages,
            params=(),
            callback=self.on_count_fetched,
            should_fetch_results=True,
        )
        if self.current_connection_id is not None:
            if self.current_message_type_is_null:
                request.name = "count msgs conn null type"
                request.query = sql_count_messages_for_connection_and_type_null
                request.params = {"connection_id": self.current_connection_id}
            elif self.current_message_type is not None:
                request.name = "count msgs conn type"
                request.query = sql_count_messages_for_connection_and_type
                request.params = {
                    "connection_id": self.current_connection_id,
                    "parsed_type": self.current_message_type,
                }
            else:
                request.name = "count msgs for conn"
                request.query = sql_count_messages_for_connection
                request.params = {"connection_id": self.current_connection_id}

        self.db_thread.put(request)

    def get_results(self, should_get_last_page=False):
        """Parses connection ID and page number text boxes and calls above database routines"""
        try:
            if self.current_connection_id_edit.text().strip() == "":
                new_connection_id = None
            else:
                new_connection_id = int(self.current_connection_id_edit.text())
                if new_connection_id <= 0:
                    raise ValueError
        except ValueError:
            self.current_connection_id_edit.setText(
                "" if self.current_connection_id is None else str(self.current_connection_id)
            )
            return
        self.current_connection_id = new_connection_id
        if self.current_connection_id is None:
            self.current_message_type_edit.setText("")
            self.current_message_type = None
            self.current_message_type_is_null = False
        else:
            message_type_text = self.current_message_type_edit.text().strip()
            if message_type_text.lower() == "null":
                self.current_message_type_is_null = True
                self.current_message_type = None
                self.current_message_type_edit.setText("null")
            elif message_type_text == "":
                self.current_message_type_is_null = False
                self.current_message_type = None
                self.current_message_type_edit.setText("")
            else:
                self.current_message_type_is_null = False
                self.current_message_type = message_type_text
                self.current_message_type_edit.setText(message_type_text)
        if should_get_last_page:
            self.last_page_pending = True
            self.db_count_messages()
            # on_count_fetched will check the last_page_pending flag and then call db_fetch_messages
            # with page number set to page count, so nothing else to do now
            return
        try:
            new_page = int(self.current_page_edit.text())
            if new_page <= 0:
                raise ValueError
        except ValueError:
            self.current_page_edit.setText(str(self.current_page))
            return
        self.current_page = new_page
        self.last_page_pending = False  # On the off chance that count for last page is in flight
        self.db_count_messages()
        self.db_fetch_messages()

    def on_messages_fetched(self, response: DatabaseResponse):
        params = {"count_per_page": _COUNT_PER_PAGE, "current_page": self.current_page}
        if self.current_connection_id is not None:
            params["connection_id"] = self.current_connection_id
        if self.current_message_type is not None:
            params["parsed_type"] = self.current_message_type
        if params != response.params:
            # Query response from previous inputs
            return
        self.messages_results_model_merger.merge(
            [db_row_to_tree_row(msg._asdict()) for msg in response.results]
        )

    def on_count_fetched(self, response: DatabaseResponse):
        connection_id = response.params["connection_id"]
        if connection_id != self.current_connection_id:
            return
        parsed_type = response.params.get("parsed_type", None)
        if self.current_message_type != parsed_type:
            return
        count = response.results[0][0]
        page_count = math.ceil(count / _COUNT_PER_PAGE)
        self.total_pages_edit.setText(str(page_count))
        if self.last_page_pending:
            # If this query was triggered by clicking last page button, need to get actual messages
            self.last_page_pending = False
            if page_count == 0:
                page_count = 1
            self.current_page = page_count
            self.current_page_edit.setText(str(self.current_page))
            self.db_fetch_messages()

    def page_first(self):
        self.current_page_edit.setText("1")
        self.get_results()

    def page_previous(self):
        self.current_page_edit.setText(str(self.current_page - 1))
        self.get_results()

    def page_next(self):
        self.current_page_edit.setText(str(self.current_page + 1))
        self.get_results()

    def page_last(self):
        self.get_results(should_get_last_page=True)

    def on_selection_changed(self, index: QModelIndex, old_index: QModelIndex):
        if not index.isValid():
            self.message_json_editor.setText("")
            self.message_proto_editor.setText("")
            self.message_errors.setText("")
            return
        # The data is stored in the user data of the first column.
        first_column = index.siblingAtColumn(0)
        xml, json, proto_bytes, error_desc = first_column.data(Qt.UserRole)
        if self.conversion_enabled:
            if isinstance(xml, bytes):
                self.message_xml_editor.setText(xml.decode("utf8"))
            else:
                self.message_xml_editor.setText(xml)
        else:
            self.message_xml_editor.setText("Conversion is disabled")
        self.message_json_editor.setText(json)
        self.message_proto_editor.setText(_bytes_as_hex(proto_bytes))
        self.message_errors.setText(error_desc or "None")

    def set_connection_id(self, connection_id: int):
        # Used in MainWindow when connection row is double clicked
        self.current_connection_id_edit.setText(str(connection_id))
        self.get_results(should_get_last_page=True)

    def copy_xml_message(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.message_xml_editor.toPlainText())

    def copy_json_message(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.message_json_editor.toPlainText())

    def copy_proto_message_hex(self):
        clipboard = QGuiApplication.clipboard()
        full_text = self.message_proto_editor.toPlainText()
        # Each line starts with 16 hex bytes, each has 2 characters + 1 space separator
        hex_text = "\n".join(line[: 3 * 16 - 1] for line in full_text.split("\n"))
        clipboard.setText(hex_text)

    def copy_proto_message_all(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.message_proto_editor.toPlainText())

    def copy_error_message(self):
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.message_errors.toPlainText())

    def indent_xml_message(self):
        try:
            root = ET.fromstring(self.message_xml_editor.toPlainText())
            ET.indent(root)
            result_bytes = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
            self.message_xml_editor.setText(result_bytes.decode("utf8"))
        except Exception:
            pass

    def syntax_xml_check_changed(self, is_checked):
        if is_checked:
            self.syntax_highlighter_xml.setDocument(self.message_xml_editor.document())
        else:
            self.syntax_highlighter_xml.setDocument(None)

    def syntax_json_check_changed(self, is_checked):
        if is_checked:
            self.syntax_highlighter_json.setDocument(self.message_json_editor.document())
        else:
            self.syntax_highlighter_json.setDocument(None)
