from typing import Any
from pydantic import BaseModel, ConfigDict

class StateWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: dict[str, Any]
