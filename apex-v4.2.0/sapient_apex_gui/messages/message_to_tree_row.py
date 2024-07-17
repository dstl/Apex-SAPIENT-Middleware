#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Converts a message record into a TreeRow used by the QTreeView ModelMerger."""

from PySide6.QtCore import Qt

from sapient_apex_qt_helpers.model_merger import TreeRow
from sapient_apex_server.time_util import datetime_int_to_str

message_column_names = [
    "ID",
    "Connection",
    "Node ID",
    "Type",
    "Forwarded",
    "Timestamp",
    "Received",
    "Saved",
    "Error Severity",
    "Error Message",
    "Status System",
    "Is Unchanged",
    "Node Type",
]


def db_row_to_tree_row(row: dict) -> TreeRow:
    columns = [
        row["id"],
        row["connection_id"],
        row["parsed_node_id"] or "-",
        row["parsed_type"] or "-",
        row["forwarded_count"],
        datetime_int_to_str(row["parsed_timestamp"], quiet=True),
        datetime_int_to_str(row["timestamp_received"], quiet=True),
        datetime_int_to_str(row["timestamp_saved"], quiet=True),
        row["error_severity"] or "-",
        (row["error_description"] or "-").split("\n", maxsplit=1)[0],
        row["status_report_system"] or "-",
        (
            bool(row["status_report_is_unchanged"])
            if row["status_report_is_unchanged"] is not None
            else "-"
        ),
        row["registration_node_type"] or "-",
    ]
    result = TreeRow(
        key=row["id"],
        columns=[{Qt.DisplayRole: x} for x in columns],
        flags=Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        children=[],
    )
    # Include JSON, Proto, and Errors in user data of first column
    result.columns[0][Qt.UserRole] = (
        row["xml"],
        row["json"],
        row["proto"],
        row["error_description"],
    )
    return result
