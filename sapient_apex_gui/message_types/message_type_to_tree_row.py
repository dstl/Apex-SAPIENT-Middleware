#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Converts a message type record into a TreeRow used by the QTreeView ModelMerger."""

from datetime import datetime
from typing import Sequence

from PySide6.QtCore import Qt

from sapient_apex_qt_helpers.model_merger import TreeRow
from sapient_apex_server.time_util import (
    datetime_to_display_str,
    datetime_to_str,
    int_to_datetime,
    timedelta_to_display_str,
)

message_type_column_names = [
    "Type",
    "Count",
    "Last time",
    "Error count",
    "Error last time",
    "Error last description",
]


def _time_to_column(type_name: str, col_type: str, row: dict, max_time: datetime):
    msg_id = row[col_type + "_last_id"]
    if msg_id is None:
        return {Qt.DisplayRole: "-"}
    timestamp = int_to_datetime(row[col_type + "_last_ts_parsed"])
    time_received = int_to_datetime(row[col_type + "_last_ts_received"])

    if timestamp is None:
        time_str = f"[rcv: {datetime_to_display_str(time_received, max_time=max_time)}]"
    else:
        time_str = (
            datetime_to_display_str(timestamp, max_time)
            + f" ({timedelta_to_display_str(time_received - timestamp)})"
        )
    return {
        Qt.DisplayRole: time_str,
        Qt.ToolTipRole: (
            f"Most recent '{type_name}' message:\n"
            + f"    Message ID: {msg_id}\n"
            + f"    Timestamp: {datetime_to_str(timestamp, quiet=True)}\n"
            + f"    Received: {datetime_to_str(time_received, quiet=True)}"
        ),
    }


def message_type_db_row_to_tree_row(row: dict, max_time: datetime) -> TreeRow:
    type_name = row["parsed_type"] or "-"
    last_error_str = str(row["err_last_description"] or "-")
    if row["err_last_severity"]:
        last_error_str = row["err_last_severity"].title() + ": " + last_error_str
    return TreeRow(
        key=type_name,
        columns=[
            {Qt.DisplayRole: type_name},
            {Qt.DisplayRole: str(row["all_count"])},
            _time_to_column(type_name, "all", row, max_time),
            {Qt.DisplayRole: str(row["err_count"] or 0)},
            _time_to_column(type_name, "err", row, max_time),
            {Qt.DisplayRole: last_error_str, Qt.ToolTipRole: last_error_str},
        ],
        flags=Qt.ItemIsEnabled | Qt.ItemIsSelectable,
        children=[],
    )


_time_columns = [
    "all_last_ts_parsed",
    "all_last_ts_received",
    "err_last_ts_parsed",
    "err_last_ts_received",
]


def response_to_tree_rows(db_rows: Sequence[dict]) -> list[TreeRow]:
    if not db_rows:
        return []

    max_time = int_to_datetime(
        max(row[col] for row in db_rows for col in _time_columns if row[col] is not None)
    )

    return [message_type_db_row_to_tree_row(row, max_time) for row in db_rows]
