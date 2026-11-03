class CancellationActionConflict(ValueError):
    pass


def lock_customer_session(cursor, customer_code, session_id):
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
        raise CancellationActionConflict(
            "Session is expired, closed, or does not "
            "belong to this customer."
        )

    return customer_id


def prepare_cancellation_in_transaction(
    cursor,
    customer_id,
    session_id,
    appointment_id,
):
    cursor.execute(
        """
        SELECT
            a.slot_id,
            a.status,
            a.row_version,
            d.display_name,
            sl.starts_at_utc,
            CASE
                WHEN sl.starts_at_utc > SYSUTCDATETIME()
                THEN 1 ELSE 0
            END AS is_future
        FROM dbo.appointments AS a WITH (UPDLOCK, HOLDLOCK)
        INNER JOIN dbo.appointment_slots AS sl WITH (HOLDLOCK)
            ON sl.slot_id = a.slot_id
        INNER JOIN dbo.doctors AS d
            ON d.doctor_id = sl.doctor_id
        WHERE a.appointment_id = ?
          AND a.customer_id = ?;
        """,
        (appointment_id, customer_id),
    )

    appointment = cursor.fetchone()

    if appointment is None:
        raise ValueError("Appointment not found for this customer.")

    slot_id, status, version, doctor_name, starts_at, is_future = appointment

    if status != "CONFIRMED":
        raise CancellationActionConflict(
            "Only confirmed appointments can be cancelled."
        )

    if not is_future:
        raise CancellationActionConflict(
            "Cannot cancel an appointment that has started."
        )

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
            appointment_id,
            expected_appointment_version,
            created_at_utc,
            expires_at_utc
        )
        OUTPUT
            CONVERT(VARCHAR(36), INSERTED.action_id),
            INSERTED.expires_at_utc
        SELECT
            session_id,
            'CANCEL',
            ?,
            ?,
            @Now,
            DATEADD(MINUTE, 5, @Now)
        FROM dbo.conversation_sessions
        WHERE session_id = ?
          AND customer_id = ?
          AND status = 'ACTIVE'
          AND expires_at_utc > @Now;
        """,
        (
            appointment_id,
            bytes(version),
            str(session_id),
            customer_id,
        ),
    )

    action = cursor.fetchone()

    if action is None:
        raise CancellationActionConflict(
            "Session expired while preparing cancellation."
        )

    return {
        "action_id": action[0],
        "action_type": "CANCEL",
        "action_status": "PENDING",
        "appointment_id": appointment_id,
        "slot_id": slot_id,
        "doctor_name": doctor_name,
        "starts_at_utc": starts_at,
        "expires_at_utc": action[1],
        "expected_appointment_version": bytes(version).hex().upper(),
    }


def execute_cancellation_in_transaction(
    cursor,
    customer_id,
    session_id,
    action_id,
):
    cursor.execute(
        """
        SELECT
            action_type,
            appointment_id,
            expected_appointment_version,
            status,
            result_appointment_id,
            CASE
                WHEN expires_at_utc > SYSUTCDATETIME()
                THEN 1 ELSE 0
            END AS is_unexpired
        FROM dbo.pending_actions WITH (UPDLOCK, HOLDLOCK)
        WHERE action_id = ?
          AND session_id = ?;
        """,
        (str(action_id), str(session_id)),
    )

    action = cursor.fetchone()

    if action is None:
        raise CancellationActionConflict(
            "Action not found for this session."
        )

    action_type, appointment_id, version, status, result_id, unexpired = action

    if action_type != "CANCEL":
        raise CancellationActionConflict(
            "This endpoint executes CANCEL actions only."
        )

    if status == "COMPLETED":
        return {
            "action_id": str(action_id),
            "action_status": "COMPLETED",
            "appointment_id": result_id,
            "already_processed": True,
        }

    if status != "PENDING":
        raise CancellationActionConflict(
            f"Action cannot execute because its status is {status}."
        )

    if not unexpired:
        raise CancellationActionConflict(
            "Action expired. Prepare a new cancellation."
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
            INSERTED.cancelled_at_utc
        FROM dbo.appointments AS a
        INNER JOIN dbo.appointment_slots AS sl WITH (HOLDLOCK)
            ON sl.slot_id = a.slot_id
        WHERE a.appointment_id = ?
          AND a.customer_id = ?
          AND a.status = 'CONFIRMED'
          AND a.row_version = ?
          AND sl.starts_at_utc > SYSUTCDATETIME();
        """,
        (appointment_id, customer_id, bytes(version)),
    )

    cancelled = cursor.fetchone()

    if cancelled is None:
        raise CancellationActionConflict(
            "Appointment changed or is no longer eligible. "
            "Fetch its details and prepare a new cancellation."
        )

    cursor.execute(
        """
        DECLARE @Now DATETIME2(3) = SYSUTCDATETIME();

        UPDATE pa
        SET
            status = 'COMPLETED',
            confirmed_at_utc = @Now,
            executed_at_utc = @Now,
            result_appointment_id = ?
        OUTPUT INSERTED.action_id
        FROM dbo.pending_actions AS pa
        INNER JOIN dbo.conversation_sessions AS s
            ON s.session_id = pa.session_id
        WHERE pa.action_id = ?
          AND pa.session_id = ?
          AND pa.status = 'PENDING'
          AND pa.expires_at_utc > @Now
          AND s.status = 'ACTIVE'
          AND s.expires_at_utc > @Now;
        """,
        (appointment_id, str(action_id), str(session_id)),
    )

    if cursor.fetchone() is None:
        raise CancellationActionConflict(
            "Action or session expired during execution. "
            "Cancellation was not committed."
        )

    return {
        "action_id": str(action_id),
        "action_status": "COMPLETED",
        "appointment_id": cancelled[0],
        "slot_id": cancelled[1],
        "appointment_status": "CANCELLED",
        "cancelled_at_utc": cancelled[2],
        "already_processed": False,
    }