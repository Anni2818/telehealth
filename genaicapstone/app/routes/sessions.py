import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.repositories.session_repository import SessionUnavailable
from app.schemas.sessions import SessionCreateRequest
from app.services.session_service import (
    close_session,
    create_session,
    get_session,
)


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sessions",
    tags=["Sessions"],
)


def _run_session_operation(operation, *args):
    try:
        return operation(*args)

    except SessionUnavailable as error:
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
        logger.exception("Session operation failed.")

        raise HTTPException(
            status_code=503,
            detail=(
                "Session operation could not be completed. "
                "Check the backend logs."
            ),
        ) from error


@router.post("", status_code=201)
def start_session(request: SessionCreateRequest):
    return _run_session_operation(
        create_session,
        request.customer_code,
    )


@router.post("/{session_id}/resume")
def resume_session(
    session_id: UUID,
    customer_code: str = Query(min_length=1, max_length=40),
):
    return _run_session_operation(
        get_session,
        session_id,
        customer_code,
    )


@router.post("/{session_id}/close")
def end_session(
    session_id: UUID,
    customer_code: str = Query(min_length=1, max_length=40),
):
    return _run_session_operation(
        close_session,
        session_id,
        customer_code,
    )