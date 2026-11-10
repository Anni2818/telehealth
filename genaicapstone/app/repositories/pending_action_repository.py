from db import get_connection


def find_current_pending_action(session_id, customer_id):
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                pa.action_id,
                pa.action_type,
                pa.status,
                pa.appointment_id,
                pa.selected_slot_id,
                pa.created_at_utc,
                pa.expires_at_utc,

                d.doctor_code,
                d.display_name,
                sp.specialty_name,
                d.city,
                d.time_zone_id,

                sl.starts_at_utc,
                sl.ends_at_utc,

                CASE
                    WHEN pa.expires_at_utc > SYSUTCDATETIME()
                    THEN 1
                    ELSE 0
                END AS is_valid

            FROM dbo.pending_actions AS pa

            INNER JOIN dbo.conversation_sessions AS cs
                ON cs.session_id = pa.session_id

            INNER JOIN dbo.app_users AS u
                ON u.customer_id = cs.customer_id

            INNER JOIN dbo.customers AS c
                ON c.customer_id = cs.customer_id

            LEFT JOIN dbo.appointment_slots AS sl
                ON sl.slot_id = pa.selected_slot_id

            LEFT JOIN dbo.doctors AS d
                ON d.doctor_id = sl.doctor_id

            LEFT JOIN dbo.specialties AS sp
                ON sp.specialty_id = d.specialty_id

            WHERE pa.session_id = ?
              AND cs.customer_id = ?
              AND cs.status = 'ACTIVE'
              AND cs.expires_at_utc > SYSUTCDATETIME()
              AND c.is_active = 1
              AND u.is_active = 1
              AND pa.status = 'PENDING'

            ORDER BY pa.created_at_utc DESC;
            """,
            (str(session_id), customer_id),
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