import json
from datetime import timezone

from app.repositories.session_repository import (
    close_session_record,
    insert_session,
    refresh_session,
)


def _validate_customer_code(customer_code):
    customer_code = customer_code.strip()

    if not customer_code:
        raise ValueError("Customer code is required.")

    return customer_code


def _format_session(session):
    session["context"] = json.loads(
        session.pop("context_json")
    )

    timestamp_fields = (
        "created_at_utc",
        "last_activity_at_utc",
        "expires_at_utc",
        "closed_at_utc",
    )

    for field in timestamp_fields:
        value = session[field]

        if value is not None:
            session[field] = value.replace(
                tzinfo=timezone.utc
            ).isoformat()

    return session


def create_session(customer_code):
    customer_code = _validate_customer_code(customer_code)

    return _format_session(
        insert_session(customer_code)
    )


def get_session(session_id, customer_code):
    customer_code = _validate_customer_code(customer_code)

    return _format_session(
        refresh_session(session_id, customer_code)
    )


def close_session(session_id, customer_code):
    customer_code = _validate_customer_code(customer_code)

    return _format_session(
        close_session_record(session_id, customer_code)
    )