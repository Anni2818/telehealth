import logging

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.workflow import WorkflowRequest
from app.repositories.workflow_repository import (
    WorkflowConflict,
    set_session_workflow,
)
from app.services.auth_service import get_current_customer


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workflow",
    tags=["Workflow"],
)


@router.post("/select")
def select_workflow(
    request: WorkflowRequest,
    current_customer: dict = Depends(get_current_customer),
):
    try:
        return set_session_workflow(
            session_id=request.session_id,
            customer_id=current_customer["customer_id"],
            workflow=request.workflow,
        )

    except WorkflowConflict as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception("Workflow selection failed.")

        raise HTTPException(
            status_code=503,
            detail="Unable to select workflow.",
        ) from error