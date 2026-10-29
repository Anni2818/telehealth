from pydantic import BaseModel, ConfigDict, Field


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_code: str = Field(min_length=1, max_length=40)