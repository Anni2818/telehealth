from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    message: str = Field(min_length=1, max_length=4000)