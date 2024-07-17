#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""Converts a list of connections to a tree of rows to show in the GUI.

This is the core functionality of the connections tab. It converts the raw database rows into
user-visible text and associated styles. The output is a list of TreeRow objects, with nested
TreeRow objects in their children, ready to be converted to a QT model by the ModelMerger class.
"""

from collections import defaultdict, namedtuple
from datetime import datetime, timedelta
import math
from typing import List, Tuple, Optional
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor


from sapient_apex_server.time_util import (
    datetime_to_display_str,
    datetime_to_str,
    timedelta_to_display_str,
    datetime_to_int,
)
from sapient_apex_gui.connections.connections_query import ConnectionInfo, MsgTimes
from sapient_apex_qt_helpers.model_merger import TreeRow

#
# Colour styles
#

# Putting the styles here helps separate them a bit from the rest of the display logic, and also
# ensures we do not construct lots of QBrush objects that are all the same.
_style_warning_severe = {
    Qt.ForegroundRole: QBrush(QColor(128, 0, 0)),
    Qt.BackgroundRole: QBrush(QColor(255, 224, 224)),
}
_style_warning_mild = {
    Qt.ForegroundRole: QBrush(QColor(104, 88, 0)),
    Qt.BackgroundRole: QBrush(QColor(255, 248, 190)),
}
_style_okay = {
    Qt.ForegroundRole: QBrush(QColor(0, 92, 0)),
    Qt.BackgroundRole: QBrush(QColor(232, 255, 232)),
}
_style_disconnected_text = {
    Qt.ForegroundRole: QBrush(QColor(160, 160, 160)),
}
_style_disconnected = {
    Qt.BackgroundRole: QBrush(QColor(244, 244, 244)),
}
_style_neutral = {  # No conclusion can be drawn from message time
    Qt.ForegroundRole: QBrush(QColor(80, 80, 80)),
    Qt.BackgroundRole: QBrush(QColor(244, 244, 244)),
}


#
# STEP 1: ConnectionInfo object to ResultRow for individual connection
#

ResultRow = namedtuple(
    "ResultRow",
    [
        "node",
        "peer",  # Socket's Peer Address
        "connection",
        "status",
        "status_time",
        "apex_time",
        "det_time",
        "message_count",
    ],
)


column_names = (
    "Node",
    "Socket",  # # Socket's Peer Address
    "Connection",
    "Status",
    "Status time",
    "Apex parse / DB",
    "Detection time",
    "Message count",
)
assert len(column_names) == len(ResultRow._fields)


def msg_times_to_cell(
    info: ConnectionInfo,
    max_time: datetime,
    msg_times: Optional[MsgTimes],
    is_connected: bool,
    is_status: bool,
):
    """Converts MsgTimes about a recent status report or detection into coloured cell contents."""
    result = {}
    if msg_times is None:
        result[Qt.DisplayRole] = "-"
        if not is_connected:
            result.update(_style_disconnected)
        elif is_status:
            result.update(_style_warning_severe)
        else:
            result.update(_style_neutral)
    else:
        status_delay = msg_times.rcv_time - msg_times.msg_time
        result[Qt.DisplayRole] = (
            datetime_to_display_str(msg_times.msg_time, max_time)
            + f" ({timedelta_to_display_str(status_delay)})"
        )
        is_dmm = info.client_type == "Peer"
        is_asm = info.client_type == "Child"
        if not is_connected:
            result.update(_style_disconnected)
        elif not (is_asm or is_dmm):
            result.update(_style_neutral)
        elif status_delay < timedelta(milliseconds=-400):
            # The delay is negative (i.e. we were given a time in the future) by a large amount
            result.update(_style_warning_severe)
        elif status_delay < timedelta():
            # Any other negative delay
            result.update(_style_warning_mild)
        elif status_delay > timedelta(seconds=is_dmm, milliseconds=800):
            result.update(_style_warning_severe)
        elif status_delay > timedelta(seconds=is_dmm, milliseconds=200):
            result.update(_style_warning_mild)
        else:
            result.update(_style_okay)
    return result


def msg_times_to_tooltip_str(desc: str, msg_times: Optional[MsgTimes]):
    result = f"Most recent {desc} report:\n"
    if msg_times is None:
        result += "    Timestamp: -\n    Received: -\n    Parsed: -\n    Stored: -"
    else:
        result += (
            f"    Timestamp: {datetime_to_str(msg_times.msg_time)}\n"
            + f"    Received: {datetime_to_str(msg_times.rcv_time)}\n"
            + f"    Parsed: {datetime_to_str(msg_times.decode_time)}\n"
            + f"    Stored: {datetime_to_str(msg_times.save_time)}"
        )
    return result


def connection_info_to_result_row(info: ConnectionInfo, max_time: datetime):
    # "Node" column
    node = {}
    node_id = str(info.node_id) if info.node_id is not None else "-"
    node_type = str(info.node_type) if info.node_type is not None else "(no reg)"
    if info.client_type == "Child":
        node[Qt.DisplayRole] = f"{node_id[:6]}: {node_type}"
    else:
        node[Qt.DisplayRole] = f"({info.client_type})"
    node[Qt.ToolTipRole] = (
        f"Type: {info.client_type}\n"
        + f"Registration time: {datetime_to_str(info.reg_msg_received_timestamp, quiet=True)}\n"
        + f"Node ID: {node_id}\n"
        + f"Node Type: {node_type}"
    )
    # Connection ID is stored in first column, used for double click handler
    node[Qt.UserRole] = info.id

    # "Connection" column
    connection = {}
    connection[
        Qt.DisplayRole
    ] = f"{info.id}: {datetime_to_display_str(info.connected_time, max_time)}"
    is_connected = info.disconnected_time is None
    if not is_connected:
        connection[Qt.DisplayRole] += " -> " + datetime_to_display_str(
            info.disconnected_time, max_time
        )
    connection[Qt.ToolTipRole] = (
        f"Connection ID: {info.id}\n"
        + f"Connected time: {datetime_to_str(info.connected_time, quiet=True)}\n"
        + f"Disconnected time: {datetime_to_str(info.disconnected_time, quiet=True)}\n"
        + f"Disconnected reason: {info.disconnected_reason or '-'}"
    )
    # The connection text display style is applied at the end of the function.

    # "Peer" column
    peer = {Qt.DisplayRole: info.peer}

    # Used in several columns - what is the most recent status report (new or unchanged)?
    unch_is_more_recent = (
        info.status_new_times is not None
        and info.status_unch_times is not None
        and info.status_unch_times.rcv_time > info.status_new_times.rcv_time
    )
    status_recent = info.status_unch_times if unch_is_more_recent else info.status_new_times

    # "Status" column
    status = {}
    if status_recent is None:
        status[Qt.DisplayRole] = "(none)"
    elif info.status_new_times is None:
        status[Qt.DisplayRole] = "(only unchanged)"
    else:
        status[Qt.DisplayRole] = info.status_new_system
    # Display warning colour if status is not "OK".
    if not is_connected:
        status.update(_style_disconnected)
    elif info.client_type not in ("Peer", "Child"):
        status.update(_style_neutral)
    elif status[Qt.DisplayRole].lower().strip() == "ok":
        status.update(_style_okay)
    else:
        status.update(_style_warning_severe)

    # "Status time" column
    status_time = msg_times_to_cell(info, max_time, status_recent, is_connected, True)
    status_time[Qt.ToolTipRole] = (
        msg_times_to_tooltip_str("'New'", info.status_new_times)
        + "\n"
        + msg_times_to_tooltip_str("'Unchanged'", info.status_unch_times)
    )

    # "Apex time" column
    apex_time = {}
    if status_recent is None:
        apex_time[Qt.DisplayRole] = "-"
    else:
        parse_delay = status_recent.decode_time - status_recent.rcv_time
        db_delay = status_recent.save_time - status_recent.decode_time
        total_delay = parse_delay + db_delay
        apex_time[
            Qt.DisplayRole
        ] = f"{timedelta_to_display_str(parse_delay)} / {timedelta_to_display_str(db_delay)}"
        if is_connected:
            if parse_delay > timedelta(milliseconds=10) or total_delay > timedelta(
                milliseconds=100
            ):
                apex_time.update(_style_warning_mild)
            elif parse_delay > timedelta(milliseconds=30) or total_delay > timedelta(
                milliseconds=1000
            ):
                apex_time.update(_style_warning_severe)

    # "Detection time" column
    detection_time = msg_times_to_cell(info, max_time, info.detection_times, is_connected, False)
    detection_time[Qt.ToolTipRole] = msg_times_to_tooltip_str("detection", info.detection_times)

    # "Message count" column
    message_count = {Qt.DisplayRole: str(info.message_count)}

    result = ResultRow(
        node=node,
        peer=peer,
        connection=connection,
        status=status,
        status_time=status_time,
        apex_time=apex_time,
        det_time=detection_time,
        message_count=message_count,
    )

    # Apply disconnected style if appropriate
    if not is_connected:
        for val in result:
            val.update(_style_disconnected_text)

    return result


#
# STEP 2: Create key for a group of connections
#


def _connection_group_key(info: ConnectionInfo):
    """Key used to group together similar connections.

    We first want to group on client type, but want to sort reverse order (DMM, GUI, ASM) so use
    -ord(first_letter) if not empty. Then for ASMs only we want to group by node_id if not empty.
    """
    client_type_reversed_first_letter = -ord(info.client_type[0]) if info.client_type[0] else 0
    node_id = -math.inf
    if info.client_type == "Child" and info.node_id is not None:
        node_id = info.node_id
    return client_type_reversed_first_letter, info.client_type, str(node_id)


#
# STEP 3: Create key for connection (within its node ID group)
#


def get_connection_key(info: ConnectionInfo):
    # First reverse sort by disconnection time, with still-connected at the start
    return (
        datetime_to_int(info.disconnected_time or datetime.max, reverse=True),
        datetime_to_int(info.connected_time, reverse=True),
    )


#
# STEP 4: ResultRow for a node ID (a group of connections)
#


def node_info_to_result_row(info_and_result_list: List[Tuple[ConnectionInfo, ResultRow]]):
    conn_infos, conn_rows = zip(*info_and_result_list)
    connected = [
        (info, result) for info, result in info_and_result_list if info.disconnected_time is None
    ]

    # The relevant connection is the most recent one, or the one still connected. If there are
    # multiple open connections then they are all relevant.
    relevant = connected
    if len(relevant) == 0:
        relevant = info_and_result_list[-1:]

    # "Node" column
    if len(relevant) == 1:
        node = relevant[0][1].node
    else:
        # Multiple open connections.
        all_type_same = all(
            c[1].node[Qt.DisplayRole] == relevant[0][1].node[Qt.DisplayRole] for c in relevant[1:]
        )
        if all_type_same:
            node = {Qt.DisplayRole: relevant[0][1].node[Qt.DisplayRole]}
        else:
            node = {Qt.DisplayRole: f"{relevant[0][0].node_id}: (multiple)"}
        node[Qt.UserRole] = None  # No obvious main connection ID

    # "Peer" column
    first_peer = relevant[0][0].peer.rsplit(":", maxsplit=1)[0]
    if all(c[0].peer.rsplit(":", maxsplit=1)[0] == first_peer for c in relevant[1:]):
        peer = {Qt.DisplayRole: first_peer}
    else:
        peer = {Qt.DisplayRole: "(multiple)"}

    # "Connection" column
    connection = {Qt.DisplayRole: f"{len(connected)} open"}
    disconnected_count = len(conn_rows) - len(connected)
    if disconnected_count != 0:
        connection[Qt.DisplayRole] += f" ({disconnected_count} closed)"
    if len(connected) > 1:
        connection.update(_style_warning_severe)
    # if len(connected) == 0: update with _style_disconnected - this is done at end for all cells.

    # "Status", "Status time", "Detection", "Apex time" columns
    if len(connected) > 1:
        status = {Qt.DisplayRole: "(multiple!)", **_style_warning_severe}
        status_time = {Qt.DisplayRole: "", **_style_warning_severe}
        detection_time = {Qt.DisplayRole: ""}
        apex_time = {Qt.DisplayRole: ""}
    else:
        status = relevant[0][1].status
        status_time = relevant[0][1].status_time
        detection_time = relevant[0][1].det_time
        apex_time = relevant[0][1].apex_time

    # "Message count" column
    message_count = {Qt.DisplayRole: str(sum(info.message_count for info in conn_infos))}

    result = ResultRow(
        node=node,
        peer=peer,
        connection=connection,
        status=status,
        status_time=status_time,
        det_time=detection_time,
        apex_time=apex_time,
        message_count=message_count,
    )

    # Apply disconnected style if appropriate
    if len(connected) == 0:
        for val in result:
            val.update(_style_disconnected_text)

    return result


#
# TOP-LEVEL: Tie together the steps above
#


def connections_to_tree(db_results):
    if not db_results:
        return []

    # STEP 1: ConnectionInfo object to ResultRow for individual connection
    max_time = max(conn_info.max_time() for conn_info in db_results)
    result_row_list = [connection_info_to_result_row(info, max_time) for info in db_results]

    # STEP 2: Group results together
    result_row_grouped = defaultdict(list)
    for info, result in zip(db_results, result_row_list):
        result_row_grouped[_connection_group_key(info)].append((info, result))

    # STEP 3, 4: ResultRow for groups, and add key for individual connections
    result_tree = []
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
    for group_key, info_and_result_list in result_row_grouped.items():
        result_tree.append(
            TreeRow(
                key=group_key,
                columns=list(node_info_to_result_row(info_and_result_list)),
                flags=flags,
                children=[
                    TreeRow(
                        key=get_connection_key(i),
                        columns=row,
                        flags=flags,
                        children=[],
                    )
                    for i, row in info_and_result_list
                ],
            )
        )
    return result_tree
