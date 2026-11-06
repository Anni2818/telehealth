import logging

from fastapi import APIRouter, HTTPException

from app.schemas.actions import PrepareBookingRequest, ExecuteBookingRequest
from app.services.action_service import prepare_booking

from app.schemas.actions import (
    ExecuteCancellationRequest,
    PrepareCancellationRequest,
)
from app.repositories.cancellation_action_repository import (
    CancellationActionConflict,
)
from app.services.cancellation_action_service import (
    execute_cancellation_action,
    prepare_cancellation,
)

from app.services.action_execution_service import (
    ActionConflict,
    execute_booking_action,
)

from app.schemas.actions import (
    ExecuteRescheduleRequest,
    PrepareRescheduleRequest,
)

from app.repositories.rescheduling_action_repository import (
    ReschedulingActionConflict,
)
from app.services.rescheduling_action_service import (
    execute_reschedule_action,
    prepare_reschedule,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/actions",
    tags=["Actions"],
)


@router.post("/bookings/prepare", status_code=201)
def prepare_booking_action(request: PrepareBookingRequest):
    try:
        return prepare_booking(
            customer_code=request.customer_code,
            session_id=request.session_id,
            slot_id=request.slot_id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception("Preparing booking action failed.")

        raise HTTPException(
            status_code=503,
            detail=(
                "Booking action could not be prepared. "
                "Check the backend logs before retrying."
            ),
        ) from error

@router.post("/bookings/execute")
def execute_prepared_booking(request: ExecuteBookingRequest):
    try:
        return execute_booking_action(
            customer_code=request.customer_code,
            session_id=request.session_id,
            action_id=request.action_id,
            confirmed=request.confirmed,
        )

    except ActionConflict as error:
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
        logger.exception("Booking action execution failed.")

        raise HTTPException(
            status_code=503,
            detail=(
                "Booking result could not be confirmed. "
                "Retry with the same session_id and action_id. "
                "Do not prepare a replacement action yet."
            ),
        ) from error


def _run_cancellation_route(operation, **arguments):
    try:
        return operation(**arguments)

    except CancellationActionConflict as error:
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
        logger.exception("Cancellation action operation failed.")

        raise HTTPException(
            status_code=503,
            detail=(
                "Cancellation action could not be completed. "
                "For an execution retry, reuse the same action_id "
                "and session_id."
            ),
        ) from error


@router.post("/cancellations/prepare", status_code=201)
def prepare_cancellation_action(request: PrepareCancellationRequest):
    return _run_cancellation_route(
        prepare_cancellation,
        customer_code=request.customer_code,
        session_id=request.session_id,
        appointment_id=request.appointment_id,
    )


@router.post("/cancellations/execute")
def execute_prepared_cancellation(request: ExecuteCancellationRequest):
    return _run_cancellation_route(
        execute_cancellation_action,
        customer_code=request.customer_code,
        session_id=request.session_id,
        action_id=request.action_id,
        confirmed=request.confirmed,
    )


def _run_rescheduling_route(operation, **arguments):
    try:
        return operation(**arguments)

    except (
        ReschedulingActionConflict,
        CancellationActionConflict,
    ) as error:
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
        logger.exception("Rescheduling action operation failed.")

        raise HTTPException(
            status_code=503,
            detail=(
                "Rescheduling result could not be confirmed. "
                "For an execution retry, reuse the same "
                "session_id and action_id."
            ),
        ) from error


@router.post("/reschedules/prepare", status_code=201)
def prepare_rescheduling_action(request: PrepareRescheduleRequest):
    return _run_rescheduling_route(
        prepare_reschedule,
        customer_code=request.customer_code,
        session_id=request.session_id,
        appointment_id=request.appointment_id,
        new_slot_id=request.new_slot_id,
    )


@router.post("/reschedules/execute")
def execute_prepared_reschedule(request: ExecuteRescheduleRequest):
    return _run_rescheduling_route(
        execute_reschedule_action,
        customer_code=request.customer_code,
        session_id=request.session_id,
        action_id=request.action_id,
        confirmed=request.confirmed,
    )