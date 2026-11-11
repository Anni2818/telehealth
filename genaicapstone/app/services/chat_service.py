from app.repositories.chat_repository import (
    open_chat_session,
    save_conversation_reference,
    verify_session_still_active,
)

from app.repositories.workflow_repository import (
    get_session_workflow,
)

from app.services.emergency_service import (
    screen_emergency,
)

from app.services.semantic_emergency_service import (
    screen_semantic_emergency,
)

from app.services.foundry_service import (
    open_foundry_client,
    send_chat_turn,
)


def process_chat(
    current_customer,
    session_id,
    message,
):
    message = message.strip()

    if not message:
        raise ValueError("Message cannot be empty.")

    customer_id = current_customer["customer_id"]

    with open_chat_session(
        session_id,
        customer_id,
    ) as (connection, context):

        safety_result = screen_emergency(message)

        if safety_result is not None:
            return {
                "session_id": str(session_id),
                "reply": safety_result.reply,
                "response_id": None,
                "tool_calls": [],
                "safety_status": safety_result.status,
                "safety_category": safety_result.category,
                "current_workflow": None,
            }

        semantic_result = screen_semantic_emergency(message)

        if semantic_result is not None and semantic_result.status != "NORMAL":
            return {
                "session_id": str(session_id),
                "reply": semantic_result.reply,
                "response_id": None,
                "tool_calls": [],
                "safety_status": semantic_result.status,
                "safety_category": semantic_result.category,
                "current_workflow": None,
            }

        current_workflow = get_session_workflow(
            session_id=session_id,
            customer_id=customer_id,
        )

        with open_foundry_client() as client:

            conversation_id = context.get(
                "foundry_conversation_id"
            )

            if conversation_id is not None:
                if (
                    not isinstance(conversation_id, str)
                    or not conversation_id.strip()
                ):
                    raise ValueError(
                        "Invalid Foundry conversation reference."
                    )

            else:
                conversation = client.conversations.create()
                conversation_id = conversation.id

                save_conversation_reference(
                    connection=connection,
                    session_id=session_id,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                )

            result = send_chat_turn(
                client=client,
                conversation_id=conversation_id,
                message=message,
                current_workflow=current_workflow,
            )

            verify_session_still_active(
                connection=connection,
                session_id=session_id,
                customer_id=customer_id,
            )

    return {
        "session_id": str(session_id),
        "current_workflow": current_workflow,
        "safety_status": "NORMAL",
        "safety_category": None,
        **result,
    }