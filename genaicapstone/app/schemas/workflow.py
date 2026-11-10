from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID

    workflow: Literal[
        "BOOK",
        "CANCEL",
        "RESCHEDULE",
    ]