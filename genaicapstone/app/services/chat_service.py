from app.repositories.chat_repository import (
    open_chat_session,
    save_conversation_reference,
    verify_session_still_active,
)
from app.services.foundry_service import (
    open_foundry_client,
    send_chat_turn,
)


def process_chat(current_customer, session_id, message):
    message = message.strip()

    if not message:
        raise ValueError("Message cannot be blank.")

    customer_id = current_customer["customer_id"]

    with open_chat_session(
        session_id,
        customer_id,
    ) as (connection, context):
        with open_foundry_client() as client:
            conversation_id = context.get(
                "foundry_conversation_id"
            )

            if conversation_id is not None and (
                not isinstance(conversation_id, str)
                or not conversation_id.strip()
            ):
                raise ValueError(
                    "Stored Foundry conversation reference is invalid."
                )

            if conversation_id is None:
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
            )

            verify_session_still_active(
                connection,
                session_id,
                customer_id,
            )

    return {
        "session_id": str(session_id),
        **result,
    }