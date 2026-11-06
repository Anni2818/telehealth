class ReschedulingActionConflict(ValueError):
    pass


def _get_eligible_appointment(cursor, customer_id, appointment_id):
    cursor.execute(
        """
        SELECT
            a.slot_id,
            a.status,
            a.row_version,
            sl.doctor_id,
            sl.starts_at_utc,
            CASE
                WHEN sl.starts_at_utc > SYSUTCDATETIME()
                THEN 1 ELSE 0
            END AS is_future
        FROM dbo.appointments AS a WITH (UPDLOCK, HOLDLOCK)
        INNER JOIN dbo.appointment_slots AS sl WITH (HOLDLOCK)
            ON sl.slot_id = a.slot_id
        WHERE a.appointment_id = ?
          AND a.customer_id = ?;
        """,
        (appointment_id, customer_id),
    )

    appointment = cursor.fetchone()

    if appointment is None:
        raise ValueError(
            "Appointment not found for this customer."
        )

    current_status = appointment[1]
    is_future = appointment[5]

    if current_status != "CONFIRMED":
        raise ReschedulingActionConflict(
            "Only confirmed appointments can be rescheduled."
        )

    if is_future == 0:
        raise ReschedulingActionConflict(
            "Cannot reschedule an appointment that has started."
        )

    return appointment


def _get_eligible_target(cursor, doctor_id, new_slot_id):
    cursor.execute(
        """
        SELECT
            sl.slot_id,
            d.doctor_code,
            d.display_name,
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
          AND sl.doctor_id = ?
          AND sl.is_enabled = 1
          AND sl.starts_at_utc > SYSUTCDATETIME()
          AND d.is_active = 1
          AND sp.is_active = 1;
        """,
        (new_slot_id, doctor_id),
    )

    target = cursor.fetchone()

    if target is None:
        raise ReschedulingActionConflict(
            "Choose an enabled future slot for the same active doctor."
        )

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
        raise ReschedulingActionConflict(
            "The replacement slot is already booked."
        )

    return target


def prepare_reschedule_in_transaction(
    cursor,
    customer_id,
    session_id,
    appointment_id,
    new_slot_id,
):
    appointment = _get_eligible_appointment(
        cursor,
        customer_id,
        appointment_id,
    )

    old_slot_id = appointment[0]
    version = bytes(appointment[2])
    doctor_id = appointment[3]

    if old_slot_id == new_slot_id:
        raise ValueError(
            "Select a different slot from the current appointment."
        )

    target = _get_eligible_target(
        cursor,
        doctor_id,
        new_slot_id,
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
            selected_slot_id,
            expected_appointment_version,
            created_at_utc,
            expires_at_utc
        )
        OUTPUT
            CONVERT(VARCHAR(36), INSERTED.action_id),
            INSERTED.expires_at_utc
        SELECT
            session_id,
            'RESCHEDULE',
            ?,
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
            new_slot_id,
            version,
            str(session_id),
            customer_id,
        ),
    )

    action = cursor.fetchone()

    if action is None:
        raise ReschedulingActionConflict(
            "Session expired while preparing rescheduling."
        )

    return {
        "action_id": action[0],
        "action_type": "RESCHEDULE",
        "action_status": "PENDING",
        "appointment_id": appointment_id,
        "current_slot_id": old_slot_id,
        "new_slot_id": new_slot_id,
        "expected_appointment_version": version.hex().upper(),
        "expires_at_utc": action[1],
        "doctor_code": target[1],
        "doctor_name": target[2],
        "city": target[3],
        "time_zone_id": target[4],
        "current_starts_at_utc": appointment[4],
        "new_starts_at_utc": target[5],
        "new_ends_at_utc": target[6],
    }


def execute_reschedule_in_transaction(
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
            selected_slot_id,
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
        raise ReschedulingActionConflict(
            "Action not found for this session."
        )

    (
        action_type,
        appointment_id,
        new_slot_id,
        expected_version,
        status,
        result_id,
        is_unexpired,
    ) = action

    if action_type != "RESCHEDULE":
        raise ReschedulingActionConflict(
            "This endpoint executes RESCHEDULE actions only."
        )

    if status == "COMPLETED":
        return {
            "action_id": str(action_id),
            "action_status": "COMPLETED",
            "appointment_id": result_id,
            "already_processed": True,
        }

    if status != "PENDING":
        raise ReschedulingActionConflict(
            f"Action cannot execute because its status is {status}."
        )

    if not is_unexpired:
        raise ReschedulingActionConflict(
            "Action expired. Prepare a new rescheduling action."
        )

    appointment = _get_eligible_appointment(
        cursor,
        customer_id,
        appointment_id,
    )

    old_slot_id = appointment[0]
    current_version = bytes(appointment[2])
    doctor_id = appointment[3]

    if current_version != bytes(expected_version):
        raise ReschedulingActionConflict(
            "Appointment changed after preparation. "
            "Review its latest details and prepare a new action."
        )

    if old_slot_id == new_slot_id:
        raise ReschedulingActionConflict(
            "Replacement slot matches the current slot. "
            "Prepare a new action if a change is needed."
        )

    _get_eligible_target(cursor, doctor_id, new_slot_id)

    cursor.execute(
        """
        UPDATE a
        SET
            slot_id = ?,
            updated_at_utc = SYSUTCDATETIME()
        OUTPUT
            INSERTED.appointment_id,
            INSERTED.slot_id,
            CONVERT(VARCHAR(16), INSERTED.row_version, 2)
        FROM dbo.appointments AS a
        INNER JOIN dbo.appointment_slots AS old_sl
            ON old_sl.slot_id = a.slot_id
        INNER JOIN dbo.appointment_slots AS new_sl
            ON new_sl.slot_id = ?
        WHERE a.appointment_id = ?
          AND a.customer_id = ?
          AND a.status = 'CONFIRMED'
          AND a.row_version = ?
          AND old_sl.starts_at_utc > SYSUTCDATETIME()
          AND new_sl.starts_at_utc > SYSUTCDATETIME();
        """,
        (
            new_slot_id,
            new_slot_id,
            appointment_id,
            customer_id,
            bytes(expected_version),
        ),
    )

    updated = cursor.fetchone()

    if updated is None:
        raise ReschedulingActionConflict(
            "Appointment changed or a slot start time passed. "
            "Rescheduling was not committed."
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
        raise ReschedulingActionConflict(
            "Action or session expired during execution. "
            "Rescheduling was not committed."
        )

    return {
        "action_id": str(action_id),
        "action_status": "COMPLETED",
        "appointment_id": updated[0],
        "previous_slot_id": old_slot_id,
        "slot_id": updated[1],
        "appointment_status": "CONFIRMED",
        "row_version": updated[2],
        "already_processed": False,
    }