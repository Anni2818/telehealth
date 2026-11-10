import logging
from datetime import date

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app.repositories.mcp_context_repository import (
    resolve_mcp_context,
)

from app.services.cancellation_action_service import (
    prepare_cancellation as prepare_cancellation_service,
)

from app.services.rescheduling_action_service import (
    prepare_reschedule as prepare_reschedule_service,
)

from app.services.appointment_service import list_available_slots

from app.repositories.mcp_context_repository import resolve_mcp_context
from app.services.appointment_service import (
    list_customer_appointments,
)
from app.services.action_service import (
    prepare_booking as prepare_booking_service,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



mcp = FastMCP(
    "telehealth-tools",
    host="127.0.0.1",
    port=8001,
    stateless_http=True,
    json_response=True,
)


@mcp.tool()
def search_available_slots(
    specialty: str,
    city: str,
    requested_date: date,
    doctor_code: str | None = None,
) -> dict:
    """
    Search the application's synthetic appointment inventory.

    requested_date is a calendar date in Asia/Kolkata.
    Optionally filter by an exact doctor_code, such as DOC-001.

    Returns actual available slots from the backend.
    An empty list means no matching slots were found.
    This tool does not reserve or book a slot.
    """
    try:
        slots = list_available_slots(
            specialty=specialty,
            city=city,
            requested_date=requested_date.isoformat(),
            time_zone_id="Asia/Kolkata",
            doctor_code=doctor_code,
        )

        return {
            "count": len(slots),
            "slots": slots,
        }

    except ValueError as error:
        raise ToolError(str(error)) from error

    except Exception as error:
        logger.exception("MCP slot search failed.")

        raise ToolError(
            "Slot search could not be completed. "
            "Do not interpret this failure as no availability."
        ) from error


@mcp.tool()
def list_my_appointments(conversation_id: str) -> dict:
    """
    List upcoming confirmed appointments for the customer
    associated with the current application conversation.

    Use the application-provided conversation_id exactly.
    Do not invent or substitute another conversation ID.
    """
    try:
        context = resolve_mcp_context(conversation_id)

        appointments = list_customer_appointments(
            customer_code=context["customer_code"],
        )

        return {
            "count": len(appointments),
            "appointments": appointments,
        }

    except ValueError as error:
        raise ToolError(str(error)) from error

    except Exception as error:
        logger.exception("MCP appointment listing failed.")

        raise ToolError(
            "Appointments could not be retrieved. "
            "Do not interpret this failure as no appointments."
        ) from error


@mcp.tool()
def prepare_booking(
    conversation_id: str,
    slot_id: int,
) -> dict:
    """
    Prepare a booking for a slot selected by the user.

    Use the application-provided conversation_id exactly.
    Use a slot_id returned by search_available_slots.

    Creates a pending action only.
    Does not reserve the slot or create an appointment.
    Actual execution requires confirmation through the application.
    """
    if slot_id <= 0:
        raise ToolError("slot_id must be positive.")

    try:
        context = resolve_mcp_context(conversation_id)

        return prepare_booking_service(
            customer_code=context["customer_code"],
            session_id=context["session_id"],
            slot_id=slot_id,
        )

    except ValueError as error:
        raise ToolError(str(error)) from error

    except Exception as error:
        logger.exception("MCP booking preparation failed.")

        raise ToolError(
            "Booking preparation could not be confirmed. "
            "Check the application before preparing another action."
        ) from error


@mcp.tool()
def prepare_cancellation(
    conversation_id: str,
    appointment_id: int,
) -> dict:
    """
    Prepare cancellation of an existing customer appointment.

    The conversation_id must come from the authenticated
    application conversation.

    The appointment_id must belong to the authenticated customer.

    This tool creates a pending cancellation action only.
    It does not cancel the appointment.

    The user must explicitly confirm through the application
    before the backend executes the cancellation.
    """
    if appointment_id <= 0:
        raise ToolError("appointment_id must be positive.")

    try:
        context = resolve_mcp_context(conversation_id)

        return prepare_cancellation_service(
            customer_code=context["customer_code"],
            session_id=context["session_id"],
            appointment_id=appointment_id,
        )

    except ValueError as error:
        raise ToolError(str(error)) from error

    except Exception as error:
        logger.exception("MCP cancellation preparation failed.")

        raise ToolError(
            "Cancellation could not be prepared. "
            "Check the application before retrying."
        ) from error


@mcp.tool()
def prepare_reschedule(
    conversation_id: str,
    appointment_id: int,
    new_slot_id: int,
) -> dict:
    """
    Prepare rescheduling of an existing appointment.

    The conversation_id must come from the authenticated
    application conversation.

    The appointment_id must belong to the authenticated customer.

    The replacement slot must be an eligible available slot
    for the same doctor.

    This tool creates a pending rescheduling action only.
    It does not change the appointment.

    Execution requires explicit user confirmation
    through the application.
    """
    if appointment_id <= 0:
        raise ToolError("appointment_id must be positive.")

    if new_slot_id <= 0:
        raise ToolError("new_slot_id must be positive.")

    try:
        context = resolve_mcp_context(conversation_id)

        return prepare_reschedule_service(
            customer_code=context["customer_code"],
            session_id=context["session_id"],
            appointment_id=appointment_id,
            new_slot_id=new_slot_id,
        )

    except ValueError as error:
        raise ToolError(str(error)) from error

    except Exception as error:
        logger.exception("MCP rescheduling preparation failed.")

        raise ToolError(
            "Rescheduling could not be prepared. "
            "Check the application before retrying."
        ) from error


if __name__ == "__main__":
    mcp.run(transport="streamable-http")