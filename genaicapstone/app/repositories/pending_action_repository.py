from db import get_connection


def find_current_pending_action(
    session_id,
    customer_id,
):

    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT TOP 1

                pa.action_id,
                pa.session_id,
                pa.action_type,
                pa.status,

                pa.appointment_id,
                pa.selected_slot_id,

                pa.created_at_utc,
                pa.expires_at_utc,

                current_appt.slot_id
                    AS current_slot_id,

                current_slot.starts_at_utc
                    AS current_starts_at_utc,

                current_slot.ends_at_utc
                    AS current_ends_at_utc,

                target_slot.starts_at_utc
                    AS target_starts_at_utc,

                target_slot.ends_at_utc
                    AS target_ends_at_utc,

                COALESCE(
                    target_doctor.doctor_code,
                    current_doctor.doctor_code
                ) AS doctor_code,

                COALESCE(
                    target_doctor.display_name,
                    current_doctor.display_name
                ) AS display_name,

                COALESCE(
                    target_specialty.specialty_name,
                    current_specialty.specialty_name
                ) AS specialty_name,

                COALESCE(
                    target_doctor.city,
                    current_doctor.city
                ) AS city,

                COALESCE(
                    target_doctor.time_zone_id,
                    current_doctor.time_zone_id
                ) AS time_zone_id

            FROM dbo.pending_actions AS pa

            INNER JOIN dbo.conversation_sessions AS cs
                ON cs.session_id = pa.session_id

            INNER JOIN dbo.customers AS customer
                ON customer.customer_id = cs.customer_id

            INNER JOIN dbo.app_users AS app_user
                ON app_user.customer_id = customer.customer_id

            LEFT JOIN dbo.appointments AS current_appt
                ON current_appt.appointment_id = pa.appointment_id
               AND current_appt.customer_id = cs.customer_id

            LEFT JOIN dbo.appointment_slots AS current_slot
                ON current_slot.slot_id = current_appt.slot_id

            LEFT JOIN dbo.doctors AS current_doctor
                ON current_doctor.doctor_id = current_slot.doctor_id

            LEFT JOIN dbo.specialties AS current_specialty
                ON current_specialty.specialty_id =
                    current_doctor.specialty_id

            LEFT JOIN dbo.appointment_slots AS target_slot
                ON target_slot.slot_id = pa.selected_slot_id

            LEFT JOIN dbo.doctors AS target_doctor
                ON target_doctor.doctor_id = target_slot.doctor_id

            LEFT JOIN dbo.specialties AS target_specialty
                ON target_specialty.specialty_id =
                    target_doctor.specialty_id

            WHERE pa.session_id = ?
              AND cs.customer_id = ?
              AND cs.status = 'ACTIVE'
              AND cs.expires_at_utc > SYSUTCDATETIME()
              AND customer.is_active = 1
              AND app_user.is_active = 1
              AND pa.status = 'PENDING'
              AND pa.expires_at_utc > SYSUTCDATETIME()

            ORDER BY pa.created_at_utc DESC;
            """,
            (
                str(session_id),
                customer_id,
            ),
        )

        row = cursor.fetchone()

        if row is None:
            connection.commit()
            return None

        columns = [
            column[0]
            for column in cursor.description
        ]

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