from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class PrepareBookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_code: str = Field(min_length=1, max_length=40)
    session_id: UUID
    slot_id: int = Field(gt=0)


class ExecuteBookingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_code: str = Field(min_length=1, max_length=40)
    session_id: UUID
    action_id: UUID
    confirmed: StrictBool

class PrepareCancellationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_code: str = Field(min_length=1, max_length=40)
    session_id: UUID
    appointment_id: int = Field(gt=0)


class ExecuteCancellationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_code: str = Field(min_length=1, max_length=40)
    session_id: UUID
    action_id: UUID
    confirmed: StrictBool