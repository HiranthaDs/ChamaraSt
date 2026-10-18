from pydantic import BaseModel, ConfigDict, Field


class NotificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_employee_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=4000)
    entity_type: str | None = Field(default=None, max_length=80)
    entity_id: str | None = Field(default=None, max_length=160)
    recipient_role: str | None = Field(default=None, max_length=80)
    metadata: dict = Field(default_factory=dict)


class Acknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str = Field(default="", max_length=1000)

