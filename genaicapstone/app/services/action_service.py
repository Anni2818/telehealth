from datetime import timezone
from zoneinfo import ZoneInfo

from app.repositories.action_repository import insert_booking_action


def prepare_booking(customer_code, session_id, slot_id):
    customer_code = customer_code.strip()

    if not customer_code:
        raise ValueError("Customer code is required.")

    result = insert_booking_action(
        customer_code=customer_code,
        session_id=session_id,
        slot_id=slot_id,
    )

    result["expires_at_utc"] = result["expires_at_utc"].replace(
        tzinfo=timezone.utc
    ).isoformat()

    details = result["booking_details"]
    local_timezone = ZoneInfo(details["time_zone_id"])

    for field in ("starts_at_utc", "ends_at_utc"):
        utc_value = details[field].replace(tzinfo=timezone.utc)
        local_field = field.replace("_utc", "_local")

        details[field] = utc_value.isoformat()
        details[local_field] = utc_value.astimezone(
            local_timezone
        ).isoformat()

    return result