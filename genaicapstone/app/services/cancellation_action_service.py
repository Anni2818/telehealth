from datetime import datetime, timezone

from db import get_connection
from app.repositories.booking_repository import WRITE_SETTINGS
from app.repositories.cancellation_action_repository import (
    execute_cancellation_in_transaction,
    lock_customer_session,
    prepare_cancellation_in_transaction,
)


def _run_cancellation_operation(
    customer_code,
    session_id,
    operation,
    operation_id,
):
    customer_code = customer_code.strip()

    if not customer_code:
        raise ValueError("Customer code is required.")

    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()
        cursor.execute(WRITE_SETTINGS)

        customer_id = lock_customer_session(
            cursor,
            customer_code,
            session_id,
        )

        result = operation(
            cursor,
            customer_id,
            session_id,
            operation_id,
        )

        cursor.execute(
            """
            DECLARE @Now DATETIME2(3) = SYSUTCDATETIME();

            UPDATE dbo.conversation_sessions
            SET
                last_activity_at_utc = @Now,
                expires_at_utc = DATEADD(MINUTE, 30, @Now)
            WHERE session_id = ?
              AND status = 'ACTIVE'
              AND expires_at_utc > @Now;

            SELECT @@ROWCOUNT;
            """,
            (str(session_id),),
        )

        if cursor.fetchone()[0] != 1:
            raise ValueError(
                "Session expired during the operation. "
                "Changes were not committed."
            )

        for key, value in result.items():
            if isinstance(value, datetime):
                result[key] = value.replace(
                    tzinfo=timezone.utc
                ).isoformat()

        connection.commit()
        return result

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()


def prepare_cancellation(
    customer_code,
    session_id,
    appointment_id,
):
    return _run_cancellation_operation(
        customer_code,
        session_id,
        prepare_cancellation_in_transaction,
        appointment_id,
    )


def execute_cancellation_action(
    customer_code,
    session_id,
    action_id,
    confirmed,
):
    if confirmed is not True:
        raise ValueError(
            "Explicit confirmation is required before cancellation."
        )

    return _run_cancellation_operation(
        customer_code,
        session_id,
        execute_cancellation_in_transaction,
        action_id,
    )