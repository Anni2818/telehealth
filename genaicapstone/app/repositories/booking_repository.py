from db import get_connection


def insert_booking(customer_code, slot_id, booking_request_id):
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
                customer_id,
                slot_id,
                status
            FROM dbo.appointments WITH (UPDLOCK, HOLDLOCK)
            WHERE booking_request_id = ?;
            """,
            (booking_request_id,),
        )

        existing = cursor.fetchone()

        if existing is not None:
            if existing[1] != customer_id or existing[2] != slot_id:
                raise ValueError(
                    "This request ID was already used for different booking details."
                )

            connection.commit()

            return {
                "appointment_id": existing[0],
                "customer_code": customer_code,
                "slot_id": existing[2],
                "status": existing[3],
                "already_processed": True,
            }

        cursor.execute(
            """
            SELECT sl.slot_id
            FROM dbo.appointment_slots AS sl WITH (UPDLOCK, HOLDLOCK)
            INNER JOIN dbo.doctors AS d WITH (HOLDLOCK)
                ON d.doctor_id = sl.doctor_id
            INNER JOIN dbo.specialties AS sp WITH (HOLDLOCK)
                ON sp.specialty_id = d.specialty_id
            WHERE sl.slot_id = ?
              AND sl.is_enabled = 1
              AND sl.starts_at_utc > SYSUTCDATETIME()
              AND d.is_active = 1
              AND sp.is_active = 1;
            """,
            (slot_id,),
        )

        if cursor.fetchone() is None:
            raise ValueError(
                "Slot does not exist, is disabled, has passed, "
                "or belongs to an inactive doctor or specialty."
            )

        cursor.execute(
            """
            SELECT appointment_id
            FROM dbo.appointments
            WHERE slot_id = ?
              AND status <> 'CANCELLED';
            """,
            (slot_id,),
        )

        if cursor.fetchone() is not None:
            raise ValueError("This slot is already booked.")

        cursor.execute(
            """
            INSERT INTO dbo.appointments (
                customer_id,
                slot_id,
                status,
                booking_request_id,
                confirmed_at_utc
            )
            OUTPUT
                INSERTED.appointment_id,
                INSERTED.slot_id,
                INSERTED.status
            VALUES (?, ?, 'CONFIRMED', ?, SYSUTCDATETIME());
            """,
            (customer_id, slot_id, booking_request_id),
        )

        appointment = cursor.fetchone()
        connection.commit()

        return {
            "appointment_id": appointment[0],
            "customer_code": customer_code,
            "slot_id": appointment[1],
            "status": appointment[2],
            "already_processed": False,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()


# In this proposed implementation, the slot is locked while checking and inserting, so competing requests using this function 
# cannot both proceed with that slot simultaneously. UPDLOCK holds update locks until the transaction ends; HOLDLOCK applies serializable semantics to the referenced table.

# Keep your existing unique filtered index too. It remains the database-level protection against multiple non-cancelled appointments occupying one slot.

# This is not a promise that concurrency can never produce an error: deadlocks or transient failures still need retry handling. For now, 
# a failed transaction rolls back; retry the same operation using its original request ID.