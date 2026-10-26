from datetime import timezone

from db import get_connection


def update_appointment_to_cancelled(customer_code, appointment_id):
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SET ANSI_NULLS ON;
            SET QUOTED_IDENTIFIER ON;
            SET ANSI_PADDING ON;
            SET ANSI_WARNINGS ON;
            SET ARITHABORT ON;
            SET CONCAT_NULL_YIELDS_NULL ON;
            SET NUMERIC_ROUNDABORT OFF;
            SET XACT_ABORT ON;
        """)

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
            SELECT
                appointment_id,
                slot_id,
                status,
                cancelled_at_utc
            FROM dbo.appointments WITH (UPDLOCK, HOLDLOCK)
            WHERE appointment_id = ?
              AND customer_id = ?;
            """,
            (appointment_id, customer_id),
        )

        appointment = cursor.fetchone()

        if appointment is None:
            raise ValueError(
                "Appointment not found for this customer."
            )

        slot_id = appointment[1]
        status = appointment[2]
        cancelled_at = appointment[3]

        if status == "CANCELLED":
            connection.commit()

            return {
                "appointment_id": appointment_id,
                "customer_code": customer_code,
                "slot_id": slot_id,
                "status": "CANCELLED",
                "cancelled_at_utc": cancelled_at.replace(
                    tzinfo=timezone.utc
                ).isoformat(),
                "already_cancelled": True,
            }

        if status != "CONFIRMED":
            raise ValueError(
                "Only confirmed appointments can be cancelled."
            )

        cursor.execute(
            """
            UPDATE a
            SET
                status = 'CANCELLED',
                cancelled_at_utc = SYSUTCDATETIME(),
                updated_at_utc = SYSUTCDATETIME()
            OUTPUT
                INSERTED.appointment_id,
                INSERTED.slot_id,
                INSERTED.status,
                INSERTED.cancelled_at_utc
            FROM dbo.appointments AS a
            INNER JOIN dbo.appointment_slots AS sl
                ON sl.slot_id = a.slot_id
            WHERE a.appointment_id = ?
              AND a.customer_id = ?
              AND a.status = 'CONFIRMED'
              AND sl.starts_at_utc > SYSUTCDATETIME();
            """,
            (appointment_id, customer_id),
        )

        cancelled = cursor.fetchone()

        if cancelled is None:
            raise ValueError(
                "Cancellation is allowed only before "
                "the appointment starts."
            )

        connection.commit()

        return {
            "appointment_id": cancelled[0],
            "customer_code": customer_code,
            "slot_id": cancelled[1],
            "status": cancelled[2],
            "cancelled_at_utc": cancelled[3].replace(
                tzinfo=timezone.utc
            ).isoformat(),
            "already_cancelled": False,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()