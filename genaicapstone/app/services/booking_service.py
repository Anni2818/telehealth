from app.repositories.booking_repository import insert_booking


def create_booking(
    customer_code,
    slot_id,
    booking_request_id,
    confirmed,
):
    customer_code = customer_code.strip()

    if not customer_code:
        raise ValueError("Customer code is required.")

    if confirmed is not True:
        raise ValueError(
            "Explicit confirmation is required before booking."
        )

    return insert_booking(
        customer_code=customer_code,
        slot_id=slot_id,
        booking_request_id=str(booking_request_id),
    )