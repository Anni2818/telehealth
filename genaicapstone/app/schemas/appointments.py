from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class BookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_code: str = Field(min_length=1, max_length=40)
    slot_id: int = Field(gt=0)
    booking_request_id: UUID
    confirmed: StrictBool


class CancellationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_code: str = Field(min_length=1, max_length=40)
    appointment_id: int = Field(gt=0)
    confirmed: StrictBool


class RescheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_code: str = Field(min_length=1, max_length=40)
    appointment_id: int = Field(gt=0)
    new_slot_id: int = Field(gt=0)
    expected_row_version: str = Field(
        pattern=r"^[0-9a-fA-F]{16}$"
    )
    confirmed: StrictBool