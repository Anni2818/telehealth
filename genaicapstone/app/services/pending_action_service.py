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

    if not action["is_valid"]:
        return None

    for field in (
        "created_at_utc",
        "expires_at_utc",
        "starts_at_utc",
        "ends_at_utc",
    ):
        value = action.get(field)

        if isinstance(value, datetime):
            action[field] = value.replace(
                tzinfo=timezone.utc
            ).isoformat()

    if (
        action["action_type"] == "BOOK"
        and action.get("time_zone_id")
        and action.get("starts_at_utc")
    ):
        local_timezone = ZoneInfo(
            action["time_zone_id"]
        )

        for field in (
            "starts_at_utc",
            "ends_at_utc",
        ):
            value = action.get(field)

            if value:
                local_field = field.replace(
                    "_utc",
                    "_local",
                )

                action[local_field] = (
                    datetime.fromisoformat(value)
                    .astimezone(local_timezone)
                    .isoformat()
                )

    action["action_id"] = str(action["action_id"])

    return action