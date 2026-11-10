import json
import logging
from contextlib import contextmanager

from db import get_connection


logger = logging.getLogger(__name__)


class ChatSessionConflict(ValueError):
    pass


@contextmanager
def open_chat_session(session_id, customer_id):
    connection = get_connection()
    cursor = None
    lock_acquired = False
    lock_name = f"telehealth-chat:{session_id}"

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SET NOCOUNT ON;

            DECLARE @Result INT;

            EXEC @Result = sys.sp_getapplock
                @Resource = ?,
                @LockMode = 'Exclusive',
                @LockOwner = 'Session',
                @LockTimeout = 0;

            SELECT @Result;
            """,
            (lock_name,),
        )

        lock_result = cursor.fetchone()[0]
        connection.commit()

        if lock_result < 0:
            raise ChatSessionConflict(
                "Another chat request is already running "
                "for this session. Wait for it to finish."
            )

        lock_acquired = True

        cursor.execute(
            """
            SELECT context_json
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
            raise ChatSessionConflict(
                "Session is expired, closed, or does not "
                "belong to this customer."
            )

        context = json.loads(row[0])

        if not isinstance(context, dict):
            raise ChatSessionConflict(
                "Session context must be a JSON object."
            )

        cursor.execute(
            """
            UPDATE dbo.conversation_sessions
            SET
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
            (str(session_id), customer_id),
        )

        if cursor.fetchone() is None:
            raise ChatSessionConflict(
                "Session expired before chat started."
            )

        connection.commit()

        yield connection, context

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            if lock_acquired:
                try:
                    connection.rollback()

                    cursor.execute(
                        """
                        SET NOCOUNT ON;

                        EXEC sys.sp_releaseapplock
                            @Resource = ?,
                            @LockOwner = 'Session';
                        """,
                        (lock_name,),
                    )

                    connection.commit()

                except Exception:
                    logger.exception(
                        "Could not explicitly release chat lock."
                    )

            try:
                cursor.close()
            finally:
                connection.close()
        else:
            connection.close()


def save_conversation_reference(
    connection,
    session_id,
    customer_id,
    conversation_id,
):
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE dbo.conversation_sessions
            SET context_json = JSON_MODIFY(
                context_json,
                '$.foundry_conversation_id',
                ?
            )
            OUTPUT INSERTED.session_id
            WHERE session_id = ?
              AND customer_id = ?
              AND status = 'ACTIVE'
              AND expires_at_utc > SYSUTCDATETIME();
            """,
            (
                conversation_id,
                str(session_id),
                customer_id,
            ),
        )

        if cursor.fetchone() is None:
            raise ChatSessionConflict(
                "Session became unavailable before "
                "its conversation could be saved."
            )

        connection.commit()

    finally:
        cursor.close()


def verify_session_still_active(
    connection,
    session_id,
    customer_id,
):
    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            SELECT session_id
            FROM dbo.conversation_sessions
            WHERE session_id = ?
              AND customer_id = ?
              AND status = 'ACTIVE'
              AND expires_at_utc > SYSUTCDATETIME();
            """,
            (str(session_id), customer_id),
        )

        row = cursor.fetchone()
        connection.commit()

        if row is None:
            raise ChatSessionConflict(
                "Session closed or expired while processing chat."
            )

    finally:
        cursor.close()
