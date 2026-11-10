import json
import logging
import os

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from azure.ai.projects import AIProjectClient
from azure.identity import ClientSecretCredential
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

MAX_APPROVAL_ROUNDS = 5

MCP_SERVER_LABEL = "slot-search"

SEARCH_TOOL = "search_available_slots"

CUSTOMER_TOOLS = {
    "list_my_appointments",
    "prepare_booking",
    "prepare_cancellation",
    "prepare_reschedule",
}

WORKFLOW_TOOLS = {
    "BOOK": "prepare_booking",
    "CANCEL": "prepare_cancellation",
    "RESCHEDULE": "prepare_reschedule",
}


class FoundryChatError(RuntimeError):
    pass


def required_setting(name):
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"{name} is missing from .env"
        )

    return value


@contextmanager
def open_foundry_client():

    with (
        ClientSecretCredential(
            tenant_id=required_setting("FOUNDRY_TENANT_ID"),
            client_id=required_setting("FOUNDRY_CLIENT_ID"),
            client_secret=required_setting("FOUNDRY_CLIENT_SECRET"),
        ) as credential,

        AIProjectClient(
            endpoint=required_setting(
                "FOUNDRY_PROJECT_ENDPOINT"
            ),
            credential=credential,
            allow_preview=True,
        ) as project_client,
    ):

        with project_client.get_openai_client(
            agent_name=required_setting(
                "FOUNDRY_AGENT_NAME"
            ),
            timeout=60.0,
            max_retries=0,
        ) as client:

            yield client


def positive_integer(value):
    return type(value) is int and value > 0


def approve_tool_request(
    request,
    conversation_id,
    current_workflow,
):

    if request.server_label != MCP_SERVER_LABEL:
        return False

    tool_name = request.name

    if tool_name == SEARCH_TOOL:
        return True

    if tool_name not in CUSTOMER_TOOLS:
        return False

    try:
        arguments = json.loads(request.arguments)
    except (TypeError, json.JSONDecodeError):
        return False

    if not isinstance(arguments, dict):
        return False

    if arguments.get("conversation_id") != conversation_id:
        return False

    if tool_name == "list_my_appointments":

        return set(arguments) == {
            "conversation_id"
        }

    expected_tool = WORKFLOW_TOOLS.get(
        current_workflow
    )

    if tool_name != expected_tool:
        logger.warning(
            "Rejected tool %s for workflow %s",
            tool_name,
            current_workflow,
        )

        return False

    if tool_name == "prepare_booking":

        return (
            set(arguments)
            == {"conversation_id", "slot_id"}
            and positive_integer(
                arguments.get("slot_id")
            )
        )

    if tool_name == "prepare_cancellation":

        return (
            set(arguments)
            == {"conversation_id", "appointment_id"}
            and positive_integer(
                arguments.get("appointment_id")
            )
        )

    if tool_name == "prepare_reschedule":

        return (
            set(arguments)
            == {
                "conversation_id",
                "appointment_id",
                "new_slot_id",
            }
            and positive_integer(
                arguments.get("appointment_id")
            )
            and positive_integer(
                arguments.get("new_slot_id")
            )
        )

    return False


def build_application_context(
    conversation_id,
    current_workflow,
):

    now = datetime.now(IST)

    workflow = current_workflow or "NONE"

    return (
        "APPLICATION CONTEXT\n"
        f"Current date: {now.date().isoformat()}\n"
        f"Current timestamp: {now.isoformat()}\n"
        "Timezone: Asia/Kolkata\n"
        f"Conversation ID: {conversation_id}\n"
        f"Selected workflow: {workflow}\n\n"

        "IMPORTANT RULES:\n"

        "Use the provided current date to resolve "
        "today and tomorrow.\n"

        "Never invent appointment IDs, slot IDs, "
        "doctor IDs or customer information.\n"

        "For customer-specific tools, use the exact "
        "application-provided conversation ID.\n"

        "BOOK means creating a NEW appointment.\n"

        "CANCEL means cancelling an EXISTING appointment.\n"

        "RESCHEDULE means changing the slot of an "
        "EXISTING appointment.\n"

        "Searching replacement slots must never "
        "change RESCHEDULE into BOOK.\n"

        "If RESCHEDULE is selected, use "
        "prepare_reschedule, never prepare_booking.\n"

        "If CANCEL is selected, use "
        "prepare_cancellation.\n"

        "If BOOK is selected, use prepare_booking.\n"

        "If no workflow is selected, ask the user "
        "to select one before preparing changes.\n"

        "For cancellation and rescheduling, identify "
        "the existing appointment from "
        "list_my_appointments.\n"

        "For rescheduling, search replacement slots "
        "for the same doctor.\n"

        "Never claim that preparing an action means "
        "the appointment was changed.\n"

        "All state-changing operations require "
        "confirmation through the application UI.\n"

        "Do not claim booking, cancellation or "
        "rescheduling succeeded without a successful "
        "backend execution result.\n"

        "Present appointment times in IST.\n"

        "A tool error does not mean that no "
        "appointments exist.\n"
    )


def send_chat_turn(
    client,
    conversation_id,
    message,
    current_workflow=None,
):

    context = build_application_context(
        conversation_id,
        current_workflow,
    )

    response = client.responses.create(
        conversation=conversation_id,
        input=[
            {
                "role": "user",
                "content": (
                    f"{context}\n\n"
                    f"USER MESSAGE:\n{message}"
                ),
            }
        ],
    )

    tool_calls = []

    for round_number in range(
        MAX_APPROVAL_ROUNDS + 1
    ):

        for item in response.output:

            if item.type == "mcp_call":

                tool_calls.append({
                    "name": getattr(
                        item,
                        "name",
                        None,
                    ),
                    "server_label": getattr(
                        item,
                        "server_label",
                        None,
                    ),
                })

        approvals = [
            item
            for item in response.output
            if item.type == "mcp_approval_request"
        ]

        if not approvals:
            break

        if round_number == MAX_APPROVAL_ROUNDS:
            raise FoundryChatError(
                "Maximum MCP approval rounds reached."
            )

        approval_responses = []

        for request in approvals:

            approved = approve_tool_request(
                request=request,
                conversation_id=conversation_id,
                current_workflow=current_workflow,
            )

            logger.info(
                "MCP approval: tool=%s workflow=%s approved=%s",
                request.name,
                current_workflow,
                approved,
            )

            approval_responses.append({
                "type": "mcp_approval_response",
                "approval_request_id": request.id,
                "approve": approved,
            })

        response = client.responses.create(
            conversation=conversation_id,
            input=approval_responses,
        )

    if response.status != "completed":
        raise FoundryChatError(
            "Foundry response did not complete."
        )

    if not response.output_text:
        raise FoundryChatError(
            "Foundry returned no assistant response."
        )

    return {
        "reply": response.output_text,
        "response_id": response.id,
        "tool_calls": tool_calls,
    }