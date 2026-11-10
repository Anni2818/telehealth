import json

from db import get_connection


class WorkflowConflict(ValueError):
    pass


def set_session_workflow(
    session_id,
    customer_id,
    workflow,
):
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT context_json
            FROM dbo.conversation_sessions WITH (UPDLOCK, HOLDLOCK)
            WHERE session_id = ?
              AND customer_id = ?
              AND status = 'ACTIVE'
              AND expires_at_utc > SYSUTCDATETIME();
            """,
            (str(session_id), customer_id),
        )

        row = cursor.fetchone()

        if row is None:
            raise WorkflowConflict(
                "Session is unavailable or expired."
            )

        cursor.execute(
            """
            SELECT action_id
            FROM dbo.pending_actions WITH (UPDLOCK, HOLDLOCK)
            WHERE session_id = ?
              AND status = 'PENDING'
              AND expires_at_utc > SYSUTCDATETIME();
            """,
            (str(session_id),),
        )

        if cursor.fetchone() is not None:
            raise WorkflowConflict(
                "Resolve the current pending action "
                "before switching workflows."
            )

        context = json.loads(row[0])

        if not isinstance(context, dict):
            raise WorkflowConflict(
                "Invalid session context."
            )

        context["current_workflow"] = workflow

        cursor.execute(
            """
            UPDATE dbo.conversation_sessions
            SET
                context_json = ?,
                last_activity_at_utc = SYSUTCDATETIME(),
                expires_at_utc = DATEADD(
                    MINUTE, 30, SYSUTCDATETIME()
                )
            OUTPUT INSERTED.session_id
            WHERE session_id = ?
              AND customer_id = ?
              AND status = 'ACTIVE'
              AND expires_at_utc > SYSUTCDATETIME();
            """,
            (
                json.dumps(context),
                str(session_id),
                customer_id,
            ),
        )

        if cursor.fetchone() is None:
            raise WorkflowConflict(
                "Session expired while changing workflow."
            )

        connection.commit()

        return {
            "session_id": str(session_id),
            "current_workflow": workflow,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()


def get_session_workflow(session_id, customer_id):
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT JSON_VALUE(
                context_json,
                '$.current_workflow'
            )
            FROM dbo.conversation_sessions
            WHERE session_id = ?
              AND customer_id = ?
              AND status = 'ACTIVE'
              AND expires_at_utc > SYSUTCDATETIME();
            """,
            (str(session_id), customer_id),
        )

        row = cursor.fetchone()

        if row is None:
            raise WorkflowConflict(
                "Session is unavailable or expired."
            )

        connection.commit()
        return row[0]

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()