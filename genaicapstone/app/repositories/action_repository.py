from db import get_connection


def insert_booking_action(customer_code, session_id, slot_id):
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
            raise ValueError(
                "Session is expired, closed, or does not "
                "belong to this customer."
            )

        cursor.execute(
            """
            SELECT
                sl.slot_id,
                d.doctor_code,
                d.display_name,
                sp.specialty_name,
                d.city,
                d.time_zone_id,
                sl.starts_at_utc,
                sl.ends_at_utc
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

        slot = cursor.fetchone()

        if slot is None:
            raise ValueError(
                "Slot is missing, disabled, past, or associated "
                "with an inactive doctor or specialty."
            )

        columns = [column[0] for column in cursor.description]
        slot_details = dict(zip(columns, slot))

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
            DECLARE @Now DATETIME2(3) = SYSUTCDATETIME();

            UPDATE dbo.pending_actions
            SET status = CASE
                WHEN expires_at_utc <= @Now THEN 'EXPIRED'
                ELSE 'SUPERSEDED'
            END
            WHERE session_id = ?
              AND status = 'PENDING';
            """,
            (str(session_id),),
        )

        cursor.execute(
            """
            DECLARE @Now DATETIME2(3) = SYSUTCDATETIME();

            INSERT INTO dbo.pending_actions (
                session_id,
                action_type,
                selected_slot_id,
                created_at_utc,
                expires_at_utc
            )
            OUTPUT
                CONVERT(VARCHAR(36), INSERTED.action_id) AS action_id,
                CONVERT(VARCHAR(36), INSERTED.session_id) AS session_id,
                INSERTED.action_type,
                INSERTED.selected_slot_id,
                INSERTED.status,
                INSERTED.expires_at_utc,
                CONVERT(VARCHAR(16), INSERTED.row_version, 2)
                    AS row_version
            SELECT
                session_id,
                'BOOK',
                ?,
                @Now,
                DATEADD(MINUTE, 5, @Now)
            FROM dbo.conversation_sessions
            WHERE session_id = ?
              AND customer_id = ?
              AND status = 'ACTIVE'
              AND expires_at_utc > @Now;
            """,
            (slot_id, str(session_id), customer_id),
        )

        action = cursor.fetchone()

        if action is None:
            raise ValueError(
                "Session expired while preparing the action."
            )

        columns = [column[0] for column in cursor.description]
        result = dict(zip(columns, action))
        result["booking_details"] = slot_details

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
        return result

    except Exception:
        connection.rollback()
        raise

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()