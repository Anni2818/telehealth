from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.repositories.appointment_repository import find_available_slots, find_customer_appointments


def list_available_slots(
    specialty,
    city,
    requested_date,
    time_zone_id="Asia/Kolkata",
    doctor_code=None,
):
    specialty = specialty.strip()
    city = city.strip()

    if not specialty or not city:
        raise ValueError("Specialty and city are required.")

    if doctor_code is not None:
        doctor_code = doctor_code.strip()

        if not doctor_code:
            raise ValueError(
                "Doctor code cannot be blank when provided."
            )

        if len(doctor_code) > 30:
            raise ValueError(
                "Doctor code cannot exceed 30 characters."
            )

    try:
        search_date = date.fromisoformat(requested_date)
    except ValueError as error:
        raise ValueError(
            "Date must be a valid date in YYYY-MM-DD format."
        ) from error

    local_timezone = ZoneInfo(time_zone_id)
    today_local = datetime.now(local_timezone).date()

    if search_date < today_local:
        raise ValueError("Cannot search for slots on a past date.")

    start_local = datetime.combine(
        search_date,
        time.min,
        tzinfo=local_timezone,
    )

    end_local = datetime.combine(
        search_date + timedelta(days=1),
        time.min,
        tzinfo=local_timezone,
    )

    start_utc = start_local.astimezone(timezone.utc).replace(
        tzinfo=None
    )

    end_utc = end_local.astimezone(timezone.utc).replace(
        tzinfo=None
    )

    slots = find_available_slots(
        specialty=specialty,
        city=city,
        start_utc=start_utc,
        end_utc=end_utc,
        time_zone_id=time_zone_id,
        doctor_code=doctor_code,
    )

    for slot in slots:
        starts_at_utc = slot["starts_at_utc"].replace(
            tzinfo=timezone.utc
        )

        ends_at_utc = slot["ends_at_utc"].replace(
            tzinfo=timezone.utc
        )

        slot["starts_at_local"] = starts_at_utc.astimezone(
            local_timezone
        ).isoformat()

        slot["ends_at_local"] = ends_at_utc.astimezone(
            local_timezone
        ).isoformat()

        slot["starts_at_utc"] = starts_at_utc.isoformat()
        slot["ends_at_utc"] = ends_at_utc.isoformat()

    return slots

def list_customer_appointments(customer_code):
    customer_code = customer_code.strip()

    if not customer_code:
        raise ValueError("Customer code is required.")

    appointments = find_customer_appointments(customer_code)

    for appointment in appointments:
        local_timezone = ZoneInfo(
            appointment["time_zone_id"]
        )

        starts_at_utc = appointment["starts_at_utc"].replace(
            tzinfo=timezone.utc
        )

        ends_at_utc = appointment["ends_at_utc"].replace(
            tzinfo=timezone.utc
        )

        appointment["starts_at_local"] = (
            starts_at_utc.astimezone(local_timezone).isoformat()
        )

        appointment["ends_at_local"] = (
            ends_at_utc.astimezone(local_timezone).isoformat()
        )

        appointment["starts_at_utc"] = starts_at_utc.isoformat()
        appointment["ends_at_utc"] = ends_at_utc.isoformat()

    return appointments