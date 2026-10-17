from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class ERPStatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: dict[str, Any]

class RecordPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=160)
