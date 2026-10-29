from db import get_connection


class SessionUnavailable(ValueError):
    pass


SESSION_OUTPUT = """
    CONVERT(VARCHAR(36), INSERTED.session_id) AS session_id,
    INSERTED.status,
    INSERTED.context_json,
    INSERTED.created_at_utc,
    INSERTED.last_activity_at_utc,
    INSERTED.expires_at_utc,
    INSERTED.closed_at_utc,
    CONVERT(VARCHAR(16), INSERTED.row_version, 2) AS row_version
"""


def _execute_session_query(query, parameters, missing_error):
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()
        cursor.execute(query, parameters)

        row = cursor.fetchone()

        if row is None:
            raise missing_error

        columns = [column[0] for column in cursor.description]
        result = dict(zip(columns, row))

        connection.commit()
        return result

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()


def insert_session(customer_code):
    query = f"""
        INSERT INTO dbo.conversation_sessions (
            customer_id,
            created_at_utc,
            last_activity_at_utc,
            expires_at_utc
        )
        OUTPUT {SESSION_OUTPUT}
        SELECT
            customer_id,
            SYSUTCDATETIME(),
            SYSUTCDATETIME(),
            DATEADD(MINUTE, 30, SYSUTCDATETIME())
        FROM dbo.customers
        WHERE customer_code = ?
          AND is_active = 1;
    """

    return _execute_session_query(
        query,
        (customer_code,),
        ValueError("Active customer not found."),
    )


def refresh_session(session_id, customer_code):
    query = f"""
        UPDATE s
        SET
            last_activity_at_utc = SYSUTCDATETIME(),
            expires_at_utc = DATEADD(
                MINUTE, 30, SYSUTCDATETIME()
            )
        OUTPUT {SESSION_OUTPUT}
        FROM dbo.conversation_sessions AS s
        INNER JOIN dbo.customers AS c
            ON c.customer_id = s.customer_id
        WHERE s.session_id = ?
          AND c.customer_code = ?
          AND c.is_active = 1
          AND s.status = 'ACTIVE'
          AND s.expires_at_utc > SYSUTCDATETIME();
    """

    return _execute_session_query(
        query,
        (str(session_id), customer_code),
        SessionUnavailable(
            "Session is unavailable, expired, closed, "
            "or does not belong to this customer."
        ),
    )


def close_session_record(session_id, customer_code):
    query = f"""
        UPDATE s
        SET
            status = 'CLOSED',
            closed_at_utc = SYSUTCDATETIME()
        OUTPUT {SESSION_OUTPUT}
        FROM dbo.conversation_sessions AS s
        INNER JOIN dbo.customers AS c
            ON c.customer_id = s.customer_id
        WHERE s.session_id = ?
          AND c.customer_code = ?
          AND c.is_active = 1
          AND s.status = 'ACTIVE'
          AND s.expires_at_utc > SYSUTCDATETIME();
    """

    return _execute_session_query(
        query,
        (str(session_id), customer_code),
        SessionUnavailable(
            "Session is unavailable, expired, closed, "
            "or does not belong to this customer."
        ),
    )