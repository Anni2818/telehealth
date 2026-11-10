import os
import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from azure.ai.projects import AIProjectClient
from azure.identity import ClientSecretCredential
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

SEARCH_TOOL = (
    "slot-search",
    "search_available_slots",
)

CUSTOMER_TOOLS = {
    ("slot-search", "list_my_appointments"),
    ("slot-search", "prepare_booking"),
    ("slot-search", "prepare_cancellation"),
    ("slot-search", "prepare_reschedule"),
}

MAX_APPROVAL_ROUNDS = 5


class FoundryChatError(RuntimeError):
    pass


def _setting(name):
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(f"{name} is missing from .env.")

    return value


@contextmanager
def open_foundry_client():
    with (
        ClientSecretCredential(
            tenant_id=_setting("FOUNDRY_TENANT_ID"),
            client_id=_setting("FOUNDRY_CLIENT_ID"),
            client_secret=_setting("FOUNDRY_CLIENT_SECRET"),
        ) as credential,
        AIProjectClient(
            endpoint=_setting("FOUNDRY_PROJECT_ENDPOINT"),
            credential=credential,
            allow_preview=True,
        ) as project_client,
    ):
        with project_client.get_openai_client(
            agent_name=_setting("FOUNDRY_AGENT_NAME"),
            timeout=60.0,
            max_retries=0,
        ) as client:
            yield client


def approve_tool_request(request, conversation_id):
    tool_identity = (
        request.server_label,
        request.name,
    )

    if tool_identity == SEARCH_TOOL:
        return True

    if tool_identity not in CUSTOMER_TOOLS:
        return False

    try:
        arguments = json.loads(request.arguments)
    except (TypeError, json.JSONDecodeError):
        return False

    if not isinstance(arguments, dict):
        return False

    if arguments.get("conversation_id") != conversation_id:
        return False

    if request.name == "list_my_appointments":
        return set(arguments) == {
            "conversation_id",
        }

    if request.name == "prepare_booking":
        slot_id = arguments.get("slot_id")

        return (
            set(arguments) == {
                "conversation_id",
                "slot_id",
            }
            and type(slot_id) is int
            and slot_id > 0
        )

    if request.name == "prepare_cancellation":
        appointment_id = arguments.get("appointment_id")

        return (
            set(arguments) == {
                "conversation_id",
                "appointment_id",
            }
            and type(appointment_id) is int
            and appointment_id > 0
        )

    if request.name == "prepare_reschedule":
        appointment_id = arguments.get("appointment_id")
        new_slot_id = arguments.get("new_slot_id")

        return (
            set(arguments) == {
                "conversation_id",
                "appointment_id",
                "new_slot_id",
            }
            and type(appointment_id) is int
            and appointment_id > 0
            and type(new_slot_id) is int
            and new_slot_id > 0
        )

    return False


def send_chat_turn(client, conversation_id, message):
    now = datetime.now(ZoneInfo("Asia/Kolkata"))

    context = (
        "Application-provided context:\n"
        f"Current India date: {now.date().isoformat()}.\n"
        f"Current India timestamp: {now.isoformat()}.\n"
        f"Current application conversation_id: {conversation_id}.\n"
        "Use this exact conversation_id for customer-specific tools. "
        "Never invent or substitute a customer identity or conversation ID. "
        "Resolve relative dates using Asia/Kolkata. "
        "Ask for clarification when a date is ambiguous. "
        "Use search_available_slots for actual availability. "
        "Use list_my_appointments to retrieve existing appointments. "
        "When the user selects a returned slot and wants to book it, "
        "use prepare_booking with that actual slot_id. "
        "Booking preparation creates a pending action only. "
        "It does not reserve a slot or create an appointment. "
        "Tell the user to review and confirm the prepared action "
        "through the application's confirmation control. "
        "Never claim that booking succeeded from preparation alone. "
        "Use doctor names exactly as returned. "
        "Label appointment times IST (UTC+05:30). "
        "A tool error is not evidence of zero availability."

        "For cancellation requests, first retrieve the customer's "
        "appointments using list_my_appointments. "
        "Resolve the user's selection to an actual appointment_id. "
        "Then call prepare_cancellation. "
        "Never invent an appointment_id. "

        "For rescheduling requests, retrieve the customer's "
        "existing appointments first. "
        "Identify the appointment and its doctor_code. "
        "Search available replacement slots for that same doctor. "
        "Resolve the selected replacement to a real slot_id. "
        "Then call prepare_reschedule. "

        "Preparation does not execute cancellation or rescheduling. "
        "The user must confirm the prepared action through "
        "the application's confirmation control. "
        "Never claim an appointment was cancelled or rescheduled "
        "unless the backend confirms successful execution. "
    )

    response = client.responses.create(
        conversation=conversation_id,
        input=[
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    f"User request:\n{message}"
                ),
            }
        ],
    )

    tool_calls = []

    for round_number in range(MAX_APPROVAL_ROUNDS + 1):
        for item in response.output:
            if item.type == "mcp_call":
                tool_calls.append(
                    {
                        "name": getattr(item, "name", None),
                        "server_label": getattr(
                            item, "server_label", None
                        ),
                    }
                )

        approvals = [
            item
            for item in response.output
            if item.type == "mcp_approval_request"
        ]

        if not approvals:
            break

        if round_number == MAX_APPROVAL_ROUNDS:
            raise FoundryChatError(
                "Tool approval-round limit reached."
            )

        approval_responses = []

        for request in approvals:
            approved = approve_tool_request(
                request,
                conversation_id,
            )

            approval_responses.append(
                {
                    "type": "mcp_approval_response",
                    "approval_request_id": request.id,
                    "approve": approved,
                }
            )

        response = client.responses.create(
            conversation=conversation_id,
            input=approval_responses,
        )

    if response.status != "completed":
        raise FoundryChatError(
            "Foundry did not complete the response."
        )

    if not response.output_text:
        raise FoundryChatError(
            "Foundry returned no assistant text."
        )

    return {
        "reply": response.output_text,
        "response_id": response.id,
        "tool_calls": tool_calls,
    }