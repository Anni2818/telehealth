import logging
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from app.services.auth_service import (
    get_current_customer,
)

from app.services.pending_action_service import (
    get_current_pending_action,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/actions",
    tags=["Actions"],
)


@router.get("/pending/{session_id}")
def get_pending_action(
    session_id: UUID,
    current_customer: dict = Depends(
        get_current_customer
    ),
):
    try:
        action = get_current_pending_action(
            session_id=session_id,
            customer_id=current_customer["customer_id"],
        )

        return {
            "has_pending_action": action is not None,
            "action": action,
        }

    except Exception as error:
        logger.exception(
            "Fetching pending action failed."
        )

        raise HTTPException(
            status_code=503,
            detail="Could not retrieve pending action.",
        ) from error