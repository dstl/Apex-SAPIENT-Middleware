#
# Copyright (c) 2019-2024 Roke Manor Research Ltd
#


sql_get_message_types = """
SELECT *
FROM (
    -- Last message and count of messages (unconditional)
    SELECT
        parsed_type, all_count, all_last_id,
        parsed_timestamp AS all_last_ts_parsed,
        timestamp_received AS all_last_ts_received
    FROM Message AS LastMsg
    INNER JOIN (
        SELECT COUNT(*) AS all_count, MAX(id) AS all_last_id
        FROM Message
        WHERE connection_id = :connection_id
        GROUP BY parsed_type
    ) AS InnerMsg ON LastMsg.id = InnerMsg.all_last_id
) AS AllMsg
LEFT OUTER JOIN (  -- equivalent to FULL OUTER JOIN in this context
    -- Last message with error and count of messages with error
    SELECT
        parsed_type AS err_parsed_type, err_count, err_last_id,
        parsed_timestamp AS err_last_ts_parsed,
        timestamp_received AS err_last_ts_received,
        error_severity AS err_last_severity,
        error_description AS err_last_description
    FROM Message AS LastMsg
    INNER JOIN (
        SELECT COUNT(*) AS err_count, MAX(id) AS err_last_id
        FROM Message
        WHERE connection_id = :connection_id AND error_severity IS NOT NULL
        GROUP BY parsed_type
    ) AS InnerMsg ON LastMsg.id = InnerMsg.err_last_id
) AS ErrMsg
ON parsed_type = err_parsed_type;
"""
