from app.repositories.rescheduling_repository import (
    fetch_appointment,
    update_appointment_slot,
)


def get_booking_details(customer_code, appointment_id):
    customer_code = customer_code.strip()

    if not customer_code:
        raise ValueError("Customer code is required.")

    return fetch_appointment(
        customer_code=customer_code,
        appointment_id=appointment_id,
    )


def reschedule_booking(
    customer_code,
    appointment_id,
    new_slot_id,
    expected_row_version,
    confirmed,
):
    customer_code = customer_code.strip()

    if not customer_code:
        raise ValueError("Customer code is required.")

    if confirmed is not True:
        raise ValueError(
            "Explicit confirmation is required before rescheduling."
        )

    return update_appointment_slot(
        customer_code=customer_code,
        appointment_id=appointment_id,
        new_slot_id=new_slot_id,
        expected_row_version=expected_row_version,
    )