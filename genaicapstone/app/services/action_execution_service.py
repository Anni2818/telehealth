from db import get_connection
from app.repositories.booking_repository import (
    WRITE_SETTINGS,
    insert_booking_in_transaction,
)


class ActionConflict(ValueError):
    pass


def execute_booking_action(
    customer_code,
    session_id,
    action_id,
    confirmed,
):
    customer_code = customer_code.strip()

    if not customer_code:
        raise ValueError("Customer code is required.")

    if confirmed is not True:
        raise ValueError(
            "Explicit confirmation is required before execution."
        )

    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()
        cursor.execute(WRITE_SETTINGS)

        # Lock customer first, matching our existing write order.
        cursor.execute(
            """
            SELECT customer_id
            FROM dbo.customers WITH (UPDLOCK, HOLDLOCK)
            WHERE customer_code = ?
              AND is_active = 1;
            """,
            (customer_code,),
        )

        customer = cursor.fetchone()

        if customer is None:
            raise ValueError("Active customer not found.")

        customer_id = customer[0]

        cursor.execute(
            """
            SELECT session_id
            FROM dbo.conversation_sessions WITH (UPDLOCK, HOLDLOCK)
            WHERE session_id = ?
              AND customer_id = ?
              AND status = 'ACTIVE'
              AND expires_at_utc > SYSUTCDATETIME();
            """,
            (str(session_id), customer_id),
        )

        if cursor.fetchone() is None:
            raise ActionConflict(
                "Session is expired, closed, or does not "
                "belong to this customer."
            )

        cursor.execute(
            """
            SELECT
                action_type,
                selected_slot_id,
                status,
                result_appointment_id,
                CASE
                    WHEN expires_at_utc <= SYSUTCDATETIME()
                    THEN 1
                    ELSE 0
                END AS is_expired
            FROM dbo.pending_actions WITH (UPDLOCK, HOLDLOCK)
            WHERE action_id = ?
              AND session_id = ?;
            """,
            (str(action_id), str(session_id)),
        )

        action = cursor.fetchone()

        if action is None:
            raise ActionConflict(
                "Action not found for this session."
            )

        action_type, slot_id, status, result_id, is_expired = action

        if action_type != "BOOK":
            raise ActionConflict(
                "This endpoint executes BOOK actions only."
            )

        # A completed action is never executed again.
        if status == "COMPLETED":
            connection.commit()

            return {
                "action_id": str(action_id),
                "action_status": "COMPLETED",
                "appointment_id": result_id,
                "already_processed": True,
            }

        if status != "PENDING":
            raise ActionConflict(
                f"Action cannot execute because its status is {status}."
            )

        if is_expired:
            cursor.execute(
                """
                UPDATE dbo.pending_actions
                SET status = 'EXPIRED'
                WHERE action_id = ?;
                """,
                (str(action_id),),
            )

            connection.commit()

            raise ActionConflict(
                "Action expired. Prepare a new booking action."
            )

        try:
            booking = insert_booking_in_transaction(
                cursor=cursor,
                customer_id=customer_id,
                customer_code=customer_code,
                slot_id=slot_id,
                booking_request_id=action_id,
            )

        except ValueError as error:
            # The booking helper raises these errors before insertion.
            # Persist invalidation so the old action cannot be confirmed.
            cursor.execute(
                """
                UPDATE dbo.pending_actions
                SET status = 'SUPERSEDED'
                WHERE action_id = ?
                  AND status = 'PENDING';
                """,
                (str(action_id),),
            )

            connection.commit()

            raise ActionConflict(
                f"{error} Prepare a new booking action."
            ) from error

        cursor.execute(
            """
            DECLARE @Now DATETIME2(3) = SYSUTCDATETIME();

            UPDATE a
            SET
                status = 'COMPLETED',
                confirmed_at_utc = @Now,
                executed_at_utc = @Now,
                result_appointment_id = ?
            OUTPUT INSERTED.result_appointment_id
            FROM dbo.pending_actions AS a
            INNER JOIN dbo.conversation_sessions AS s
                ON s.session_id = a.session_id
            WHERE a.action_id = ?
              AND a.session_id = ?
              AND a.status = 'PENDING'
              AND a.expires_at_utc > @Now
              AND s.status = 'ACTIVE'
              AND s.expires_at_utc > @Now;
            """,
            (
                booking["appointment_id"],
                str(action_id),
                str(session_id),
            ),
        )

        if cursor.fetchone() is None:
            raise ActionConflict(
                "Action or session expired during execution. "
                "No new booking was committed."
            )

        cursor.execute(
            """
            DECLARE @Now DATETIME2(3) = SYSUTCDATETIME();

            UPDATE dbo.conversation_sessions
            SET
                last_activity_at_utc = @Now,
                expires_at_utc = DATEADD(MINUTE, 30, @Now)
            WHERE session_id = ?;
            """,
            (str(session_id),),
        )

        connection.commit()

        return {
            "action_id": str(action_id),
            "action_status": "COMPLETED",
            "appointment_id": booking["appointment_id"],
            "slot_id": booking["slot_id"],
            "appointment_status": booking["status"],
            "already_processed": booking["already_processed"],
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()