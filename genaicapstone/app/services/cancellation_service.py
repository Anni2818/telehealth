from app.repositories.cancellation_repository import (
    update_appointment_to_cancelled,
)


def cancel_booking(customer_code, appointment_id, confirmed):
    customer_code = customer_code.strip()

    if not customer_code:
        raise ValueError("Customer code is required.")

    if confirmed is not True:
        raise ValueError(
            "Explicit confirmation is required before cancellation."
        )

    return update_appointment_to_cancelled(
        customer_code=customer_code,
        appointment_id=appointment_id,
    )