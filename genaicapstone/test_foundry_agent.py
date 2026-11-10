import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from azure.ai.projects import AIProjectClient
from azure.identity import ClientSecretCredential
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")

ALLOWED_TOOLS = {"search_available_slots"}
MAX_APPROVAL_ROUNDS = 5
APPLICATION_TIMEZONE = ZoneInfo("Asia/Kolkata")


def required_setting(name):
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"{name} is missing from your .env file."
        )

    return value


def build_date_instructions():
    current_time = datetime.now(APPLICATION_TIMEZONE)

    return (
        "Apply the following application-provided context alongside "
        "the agent's configured receptionist and safety rules. "
        f"The current date in Asia/Kolkata is "
        f"{current_time.date().isoformat()}. "
        f"The current local timestamp is {current_time.isoformat()}. "
        "Resolve relative dates such as today and tomorrow using "
        "this date and timezone. "
        "If a date is ambiguous, ask the user for clarification. "
        "Do not guess a historical date. "
        "Use the appointment search tool for actual availability. "
        "Present returned appointment times in India time and "
        "explicitly label them IST (UTC+05:30). "
        "Use doctor names exactly as returned by the tool; "
        "do not add titles that are not present in the data. "
        "Only read-only slot search is enabled in this test. "
        "Do not claim that booking, cancellation, or rescheduling "
        "can be completed through this test. "
        "Do not ask for booking confirmation as though booking "
        "execution were available. "
        "A tool error means availability could not be checked, "
        "not that no slots exist."
    )


def display_response(response):
    print("\nResponse status:", response.status)

    print(
        "Output item types:",
        [item.type for item in response.output],
    )

    if response.output_text:
        print("\nAgent:", response.output_text)


def display_arguments(arguments):
    try:
        parsed_arguments = json.loads(arguments)
    except (TypeError, json.JSONDecodeError):
        parsed_arguments = arguments

    print(
        "Arguments:",
        json.dumps(
            parsed_arguments,
            indent=2,
            default=str,
        ),
    )


def handle_tool_approvals(
    client,
    conversation_id,
    response,
    date_instructions,
):
    for _ in range(MAX_APPROVAL_ROUNDS):
        display_response(response)

        approval_requests = [
            item
            for item in response.output
            if item.type == "mcp_approval_request"
        ]

        if not approval_requests:
            return response

        approval_responses = []

        for request in approval_requests:
            print("\nMCP tool approval requested")
            print("Server:", request.server_label)
            print("Tool:", request.name)

            display_arguments(request.arguments)

            if request.name not in ALLOWED_TOOLS:
                approved = False

                print(
                    "Denied: this test permits "
                    "search_available_slots only."
                )

            else:
                answer = input(
                    "Approve this read-only search? (y/N): "
                ).strip().lower()

                approved = answer == "y"

                if not approved:
                    print("Tool call denied.")

            approval_responses.append(
                {
                    "type": "mcp_approval_response",
                    "approval_request_id": request.id,
                    "approve": approved,
                }
            )

        response = client.responses.create(
            conversation=conversation_id,
            # instructions=date_instructions,
            input=approval_responses,
        )

    display_response(response)

    if any(
        item.type == "mcp_approval_request"
        for item in response.output
    ):
        raise RuntimeError(
            "Approval-round limit reached. "
            "Stop and inspect the agent trace."
        )

    return response


def main():
    endpoint = required_setting("FOUNDRY_PROJECT_ENDPOINT")
    agent_name = required_setting("FOUNDRY_AGENT_NAME")

    tenant_id = required_setting("FOUNDRY_TENANT_ID")
    client_id = required_setting("FOUNDRY_CLIENT_ID")
    client_secret = required_setting("FOUNDRY_CLIENT_SECRET")

    with (
        ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        ) as credential,
        AIProjectClient(
            endpoint=endpoint,
            credential=credential,
            allow_preview=True,
        ) as project_client,
    ):
        with project_client.get_openai_client(
            agent_name=agent_name
        ) as client:
            conversation = client.conversations.create()

            print("Foundry test conversation created.")
            print("Only read-only slot search is enabled.")
            print("Enter y to approve a tool call.")
            print("Pressing Enter denies a tool call.")
            print("Type exit to stop.\n")

            while True:
                message = input("You: ").strip()

                if message.lower() in {"exit", "quit"}:
                    break

                if not message:
                    continue

                date_instructions = build_date_instructions()

                response = client.responses.create(
                    conversation=conversation.id,
                    input=[
                        {
                            "role": "user",
                            "content": (
                                f"Application-provided context:\n"
                                f"{date_instructions}\n\n"
                                f"User request:\n{message}"
                            ),
                        }
                    ],
                )

                final_response = handle_tool_approvals(
                    client=client,
                    conversation_id=conversation.id,
                    response=response,
                    date_instructions=date_instructions,
                )

                if final_response.status != "completed":
                    print(
                        "\nThe response did not complete. "
                        "Inspect the agent trace before continuing."
                    )
                    break

                print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest stopped.")