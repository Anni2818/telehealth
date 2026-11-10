from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.repositories.pending_action_repository import (
    find_current_pending_action,
)


def get_current_pending_action(
    session_id,
    customer_id,
):

    action = find_current_pending_action(
        session_id=session_id,
        customer_id=customer_id,
    )

    if action is None:
        return None

    timezone_id = (
        action.get("time_zone_id")
        or "Asia/Kolkata"
    )

    local_timezone = ZoneInfo(timezone_id)

    datetime_fields = [
        "created_at_utc",
        "expires_at_utc",
        "current_starts_at_utc",
        "current_ends_at_utc",
        "target_starts_at_utc",
        "target_ends_at_utc",
    ]

    for field in datetime_fields:

        value = action.get(field)

        if not isinstance(value, datetime):
            continue

        utc_value = value.replace(
            tzinfo=timezone.utc
        )

        action[field] = utc_value.isoformat()

        if field.startswith(("current_", "target_")):

            local_field = field.replace(
                "_utc",
                "_local",
            )

            action[local_field] = (
                utc_value.astimezone(
                    local_timezone
                ).isoformat()
            )

    action["action_id"] = str(
        action["action_id"]
    )

    action["session_id"] = str(
        action["session_id"]
    )

    return action