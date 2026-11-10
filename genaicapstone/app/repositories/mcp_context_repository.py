from db import get_connection


def resolve_mcp_context(conversation_id):
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                CONVERT(VARCHAR(36), s.session_id) AS session_id,
                c.customer_id,
                c.customer_code
            FROM dbo.conversation_sessions AS s
            INNER JOIN dbo.customers AS c
                ON c.customer_id = s.customer_id
            INNER JOIN dbo.app_users AS u
                ON u.customer_id = c.customer_id
            WHERE JSON_VALUE(
                s.context_json,
                '$.foundry_conversation_id'
            ) = ?
              AND s.status = 'ACTIVE'
              AND s.expires_at_utc > SYSUTCDATETIME()
              AND c.is_active = 1
              AND u.is_active = 1;
            """,
            (conversation_id,),
        )

        rows = cursor.fetchmany(2)

        if len(rows) != 1:
            raise ValueError(
                "No unique active customer session is available "
                "for this conversation."
            )

        row = rows[0]

        result = {
            "session_id": row[0],
            "customer_id": row[1],
            "customer_code": row[2],
        }

        connection.commit()
        return result

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()