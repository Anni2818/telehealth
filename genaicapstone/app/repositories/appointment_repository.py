from db import get_connection


def find_available_slots(
    specialty,
    city,
    start_utc,
    end_utc,
    time_zone_id,
):
    query = """
        SELECT
            sl.slot_id,
            d.doctor_code,
            d.display_name,
            sp.specialty_name,
            d.city,
            sl.starts_at_utc,
            sl.ends_at_utc
        FROM dbo.appointment_slots AS sl
        INNER JOIN dbo.doctors AS d
            ON d.doctor_id = sl.doctor_id
        INNER JOIN dbo.specialties AS sp
            ON sp.specialty_id = d.specialty_id
        WHERE sp.specialty_name = ?
          AND d.city = ?
          AND d.time_zone_id = ?
          AND sp.is_active = 1
          AND d.is_active = 1
          AND sl.is_enabled = 1
          AND sl.starts_at_utc >= ?
          AND sl.starts_at_utc < ?
          AND sl.starts_at_utc > SYSUTCDATETIME()
          AND NOT EXISTS (
              SELECT 1
              FROM dbo.appointments AS a
              WHERE a.slot_id = sl.slot_id
                AND a.status <> 'CANCELLED'
          )
        ORDER BY sl.starts_at_utc, d.doctor_code;
    """

    connection = get_connection()

    try:
        cursor = connection.cursor()

        try:
            cursor.execute(
                query,
                (
                    specialty,
                    city,
                    time_zone_id,
                    start_utc,
                    end_utc,
                ),
            )

            columns = [column[0] for column in cursor.description]

            return [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

        finally:
            cursor.close()

    finally:
        connection.close()