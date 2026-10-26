from db import get_connection


class RescheduleConflict(ValueError):
    pass


def fetch_appointment(customer_code, appointment_id):
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                a.appointment_id,
                c.customer_code,
                a.slot_id,
                a.status,
                d.doctor_code,
                d.display_name,
                sp.specialty_name,
                d.city,
                d.time_zone_id,
                sl.starts_at_utc,
                sl.ends_at_utc,
                CONVERT(VARCHAR(16), a.row_version, 2)
                    AS row_version
            FROM dbo.appointments AS a
            INNER JOIN dbo.customers AS c
                ON c.customer_id = a.customer_id
            INNER JOIN dbo.appointment_slots AS sl
                ON sl.slot_id = a.slot_id
            INNER JOIN dbo.doctors AS d
                ON d.doctor_id = sl.doctor_id
            INNER JOIN dbo.specialties AS sp
                ON sp.specialty_id = d.specialty_id
            WHERE a.appointment_id = ?
              AND c.customer_code = ?
              AND c.is_active = 1;
            """,
            (appointment_id, customer_code),
        )

        row = cursor.fetchone()

        if row is None:
            raise ValueError(
                "Appointment not found for this active customer."
            )

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


def update_appointment_slot(
    customer_code,
    appointment_id,
    new_slot_id,
    expected_row_version,
):
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
                slot_id,
                status,
                CONVERT(VARCHAR(16), row_version, 2)
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

        old_slot_id, status, current_version = appointment

        if current_version.upper() != expected_row_version.upper():
            raise RescheduleConflict(
                "Appointment has changed. Fetch its latest details "
                "and confirm the change again."
            )

        if status != "CONFIRMED":
            raise ValueError(
                "Only confirmed appointments can be rescheduled."
            )

        cursor.execute(
            """
            SELECT doctor_id
            FROM dbo.appointment_slots WITH (HOLDLOCK)
            WHERE slot_id = ?
              AND starts_at_utc > SYSUTCDATETIME();
            """,
            (old_slot_id,),
        )

        original_slot = cursor.fetchone()

        if original_slot is None:
            raise ValueError(
                "Cannot reschedule an appointment that has started."
            )

        doctor_id = original_slot[0]

        cursor.execute(
            """
            SELECT sl.slot_id
            FROM dbo.appointment_slots AS sl WITH (UPDLOCK, HOLDLOCK)
            INNER JOIN dbo.doctors AS d WITH (HOLDLOCK)
                ON d.doctor_id = sl.doctor_id
            INNER JOIN dbo.specialties AS sp WITH (HOLDLOCK)
                ON sp.specialty_id = d.specialty_id
            WHERE sl.slot_id = ?
              AND sl.doctor_id = ?
              AND sl.is_enabled = 1
              AND sl.starts_at_utc > SYSUTCDATETIME()
              AND d.is_active = 1
              AND sp.is_active = 1;
            """,
            (new_slot_id, doctor_id),
        )

        if cursor.fetchone() is None:
            raise ValueError(
                "Choose an enabled future slot for the same active doctor."
            )

        if new_slot_id == old_slot_id:
            connection.commit()

            return {
                "appointment_id": appointment_id,
                "customer_code": customer_code,
                "slot_id": old_slot_id,
                "status": status,
                "row_version": current_version,
                "already_on_slot": True,
            }

        cursor.execute(
            """
            SELECT appointment_id
            FROM dbo.appointments
            WHERE slot_id = ?
              AND status <> 'CANCELLED';
            """,
            (new_slot_id,),
        )

        if cursor.fetchone() is not None:
            raise RescheduleConflict(
                "The selected slot is already booked. Search again."
            )

        cursor.execute(
            """
            UPDATE a
            SET
                slot_id = ?,
                updated_at_utc = SYSUTCDATETIME()
            OUTPUT
                INSERTED.appointment_id,
                INSERTED.slot_id,
                INSERTED.status,
                CONVERT(VARCHAR(16), INSERTED.row_version, 2)
            FROM dbo.appointments AS a
            INNER JOIN dbo.appointment_slots AS old_sl
                ON old_sl.slot_id = a.slot_id
            INNER JOIN dbo.appointment_slots AS new_sl
                ON new_sl.slot_id = ?
            WHERE a.appointment_id = ?
              AND a.customer_id = ?
              AND a.status = 'CONFIRMED'
              AND a.row_version = CONVERT(BINARY(8), ?, 2)
              AND old_sl.starts_at_utc > SYSUTCDATETIME()
              AND new_sl.starts_at_utc > SYSUTCDATETIME();
            """,
            (
                new_slot_id,
                new_slot_id,
                appointment_id,
                customer_id,
                expected_row_version,
            ),
        )

        updated = cursor.fetchone()

        if updated is None:
            raise RescheduleConflict(
                "Appointment changed or a slot start time passed. "
                "Fetch current details before trying again."
            )

        connection.commit()

        return {
            "appointment_id": updated[0],
            "customer_code": customer_code,
            "previous_slot_id": old_slot_id,
            "slot_id": updated[1],
            "status": updated[2],
            "row_version": updated[3],
            "already_on_slot": False,
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()