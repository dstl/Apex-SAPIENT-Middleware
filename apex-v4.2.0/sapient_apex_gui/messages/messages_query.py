#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#

"""SQL query for fetching data for the messages tab."""

sql_get_messages = """
SELECT
    id, connection_id, forwarded_count,
    timestamp_received, timestamp_decoded, timestamp_saved,
    xml, proto, json,
    parsed_type, parsed_node_id, parsed_timestamp,
    registration_node_type,
    status_report_system, status_report_is_unchanged,
    error_severity, error_description
FROM
    Message
WHERE
    id > (:current_page - 1) * :count_per_page
    AND id <= :current_page * :count_per_page
ORDER BY id
"""

sql_get_messages_for_connection = """
SELECT
    id, connection_id, forwarded_count,
    timestamp_received, timestamp_decoded, timestamp_saved,
    xml, proto, json,
    parsed_type, parsed_node_id, parsed_timestamp,
    registration_node_type,
    status_report_system, status_report_is_unchanged,
    error_severity, error_description
FROM
    Message
WHERE
    connection_id = :connection_id
ORDER BY id
LIMIT :count_per_page OFFSET (:current_page - 1) * :count_per_page
"""

sql_get_messages_for_connection_and_type = """
SELECT
    id, connection_id, forwarded_count,
    timestamp_received, timestamp_decoded, timestamp_saved,
    xml, proto, json,
    parsed_type, parsed_node_id, parsed_timestamp,
    registration_node_type,
    status_report_system, status_report_is_unchanged,
    error_severity, error_description
FROM
    Message
WHERE
    connection_id = :connection_id
    AND parsed_type = :parsed_type
ORDER BY id
LIMIT :count_per_page OFFSET (:current_page - 1) * :count_per_page
"""

sql_get_messages_for_connection_and_type_null = """
SELECT
    id, connection_id, forwarded_count,
    timestamp_received, timestamp_decoded, timestamp_saved,
    xml, proto, json,
    parsed_type, parsed_node_id, parsed_timestamp,
    registration_node_type,
    status_report_system, status_report_is_unchanged,
    error_severity, error_description
FROM
    Message
WHERE
    connection_id = :connection_id
    AND parsed_type IS NULL
ORDER BY id
LIMIT :count_per_page OFFSET (:current_page - 1) * :count_per_page
"""


sql_count_messages = """
SELECT COUNT(*) FROM Message
"""

sql_count_messages_for_connection = """
SELECT COUNT(*) FROM Message WHERE connection_id = :connection_id
"""

sql_count_messages_for_connection_and_type = """
SELECT COUNT(*) FROM Message WHERE connection_id = :connection_id AND parsed_type = :parsed_type
"""

sql_count_messages_for_connection_and_type_null = """
SELECT COUNT(*) FROM Message WHERE connection_id = :connection_id AND parsed_type IS NULL
"""
