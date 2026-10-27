from db import get_connection

#this is to get empty valid slots form the db.
def find_available_slots(
    specialty,
    city,
    start_utc,
    end_utc,
    time_zone_id,
    doctor_code=None,
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
    """

    parameters = [
        specialty,
        city,
        time_zone_id,
        start_utc,
        end_utc,
    ]

    if doctor_code is not None:
        query += " AND d.doctor_code = ?"
        parameters.append(doctor_code)

    query += " ORDER BY sl.starts_at_utc, d.doctor_code;"

    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()
        cursor.execute(query, tuple(parameters))

        columns = [column[0] for column in cursor.description]

        slots = [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

        connection.commit()
        return slots

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()


#this is to return the appointments of the particular customer which are confirmed and in future.
def find_customer_appointments(customer_code):
    connection = get_connection()
    cursor = None

    try:
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT customer_id
            FROM dbo.customers
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
                a.appointment_id,
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
            INNER JOIN dbo.appointment_slots AS sl
                ON sl.slot_id = a.slot_id
            INNER JOIN dbo.doctors AS d
                ON d.doctor_id = sl.doctor_id
            INNER JOIN dbo.specialties AS sp
                ON sp.specialty_id = d.specialty_id
            WHERE a.customer_id = ?
              AND a.status = 'CONFIRMED'
              AND sl.starts_at_utc > SYSUTCDATETIME()
            ORDER BY
                sl.starts_at_utc,
                a.appointment_id;
            """,
            (customer_id,),
        )

        columns = [column[0] for column in cursor.description]

        appointments = [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

        connection.commit()
        return appointments

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()