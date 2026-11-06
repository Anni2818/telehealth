from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from db import get_connection
from app.repositories.booking_repository import WRITE_SETTINGS
from app.repositories.cancellation_action_repository import (
    lock_customer_session,
)
from app.repositories.rescheduling_action_repository import (
    ReschedulingActionConflict,
    execute_reschedule_in_transaction,
    prepare_reschedule_in_transaction,
)


def _format_result(result):
    timezone_id = result.get("time_zone_id")

    if timezone_id:
        local_timezone = ZoneInfo(timezone_id)

        for field in (
            "current_starts_at_utc",
            "new_starts_at_utc",
            "new_ends_at_utc",
        ):
            value = result.get(field)

            if isinstance(value, datetime):
                local_field = field.replace("_utc", "_local")

                result[local_field] = value.replace(
                    tzinfo=timezone.utc
                ).astimezone(local_timezone).isoformat()

    for key, value in list(result.items()):
        if isinstance(value, datetime):
            result[key] = value.replace(
                tzinfo=timezone.utc
            ).isoformat()

    return result


def _run_rescheduling_operation(
    customer_code,
    session_id,
    operation,
    **operation_arguments,
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
            cursor=cursor,
            customer_id=customer_id,
            session_id=session_id,
            **operation_arguments,
        )

        cursor.execute(
            """
            DECLARE @Now DATETIME2(3) = SYSUTCDATETIME();

            UPDATE dbo.conversation_sessions
            SET
                last_activity_at_utc = @Now,
                expires_at_utc = DATEADD(MINUTE, 30, @Now)
            OUTPUT INSERTED.session_id
            WHERE session_id = ?
              AND status = 'ACTIVE'
              AND expires_at_utc > @Now;
            """,
            (str(session_id),),
        )

        if cursor.fetchone() is None:
            raise ReschedulingActionConflict(
                "Session expired during the operation. "
                "Changes were not committed."
            )

        result = _format_result(result)

        connection.commit()
        return result

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()


def prepare_reschedule(
    customer_code,
    session_id,
    appointment_id,
    new_slot_id,
):
    return _run_rescheduling_operation(
        customer_code=customer_code,
        session_id=session_id,
        operation=prepare_reschedule_in_transaction,
        appointment_id=appointment_id,
        new_slot_id=new_slot_id,
    )


def execute_reschedule_action(
    customer_code,
    session_id,
    action_id,
    confirmed,
):
    if confirmed is not True:
        raise ValueError(
            "Explicit confirmation is required before rescheduling."
        )

    return _run_rescheduling_operation(
        customer_code=customer_code,
        session_id=session_id,
        operation=execute_reschedule_in_transaction,
        action_id=action_id,
    )