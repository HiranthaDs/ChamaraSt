from pydantic import BaseModel, ConfigDict, Field

class ManufacturingRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=160)
