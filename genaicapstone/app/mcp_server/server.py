import logging
from datetime import date

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app.services.appointment_service import list_available_slots


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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")