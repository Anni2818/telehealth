import logging

from fastapi import APIRouter, Depends, HTTPException

from app.repositories.chat_repository import ChatSessionConflict
from app.schemas.chat import ChatRequest
from app.services.auth_service import get_current_customer
from app.services.chat_service import process_chat


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("")
def chat(
    request: ChatRequest,
    current_customer: dict = Depends(get_current_customer),
):
    try:
        return process_chat(
            current_customer=current_customer,
            session_id=request.session_id,
            message=request.message,
        )

    except ChatSessionConflict as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception("Chat operation failed.")

        raise HTTPException(
            status_code=502,
            detail=(
                "Chat could not be completed. "
                "The message may already have reached Foundry. "
                "Do not automatically resend it; "
                "check the backend logs."
            ),
        ) from error