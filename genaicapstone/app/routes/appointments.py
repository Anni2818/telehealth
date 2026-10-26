import logging
from datetime import date
from fastapi import Path
from fastapi import APIRouter, HTTPException, Query


#rescheduling requirments
from app.schemas.appointments import RescheduleRequest
from app.services.rescheduling_service import (
    get_booking_details,
    reschedule_booking,
)
from app.repositories.rescheduling_repository import RescheduleConflict

#booking requirments
from app.schemas.appointments import BookingRequest
from app.services.booking_service import create_booking
from app.services.appointment_service import list_available_slots

#cancellation requirments
from app.schemas.appointments import CancellationRequest
from app.services.cancellation_service import cancel_booking


router = APIRouter(
    prefix="/appointments",
    tags=["Appointments"],
)


@router.get("/slots")
def get_available_slots(
    specialty: str = Query(min_length=1, max_length=100),
    city: str = Query(min_length=1, max_length=100),
    requested_date: date = Query(
        description="Appointment date in India time, YYYY-MM-DD"
    ),
):
    try:
        slots = list_available_slots(
            specialty=specialty,
            city=city,
            requested_date=requested_date.isoformat(),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return {
        "count": len(slots),
        "slots": slots,
    }

logger = logging.getLogger(__name__)


@router.post("/bookings")
def book_appointment(request: BookingRequest):
    try:
        return create_booking(
            customer_code=request.customer_code,
            slot_id=request.slot_id,
            booking_request_id=request.booking_request_id,
            confirmed=request.confirmed,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception("Booking operation failed.")

        raise HTTPException(
            status_code=503,
            detail=(
                "Booking could not be completed. "
                "Retry with the same booking_request_id."
            ),
        ) from error


@router.post("/cancellations")
def cancel_appointment(request: CancellationRequest):
    try:
        return cancel_booking(
            customer_code=request.customer_code,
            appointment_id=request.appointment_id,
            confirmed=request.confirmed,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception("Cancellation operation failed.")

        raise HTTPException(
            status_code=503,
            detail=(
                "Cancellation could not be completed. "
                "Retry the same cancellation request."
            ),
        ) from error


@router.get("/bookings/{appointment_id}")
def get_appointment_details(
    appointment_id: int = Path(gt=0),
    customer_code: str = Query(min_length=1, max_length=40),
):
    try:
        return get_booking_details(
            customer_code=customer_code,
            appointment_id=appointment_id,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception as error:
        logger.exception("Fetching appointment details failed.")

        raise HTTPException(
            status_code=503,
            detail="Appointment details could not be retrieved.",
        ) from error


@router.post("/reschedules")
def reschedule_appointment(request: RescheduleRequest):
    try:
        return reschedule_booking(
            customer_code=request.customer_code,
            appointment_id=request.appointment_id,
            new_slot_id=request.new_slot_id,
            expected_row_version=request.expected_row_version,
            confirmed=request.confirmed,
        )

    except RescheduleConflict as error:
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
        logger.exception("Rescheduling operation failed.")

        raise HTTPException(
            status_code=503,
            detail=(
                "Rescheduling could not be completed. "
                "Fetch the appointment's current details "
                "before deciding whether to retry."
            ),
        ) from error