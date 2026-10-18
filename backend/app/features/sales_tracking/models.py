from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobCreate(BaseModel):
    salesman_id: str = Field(min_length=1, max_length=160)
    work_date: date
    starts_at: str = Field(min_length=1, max_length=40)
    ends_at: str = Field(min_length=1, max_length=40)
    territory: str = Field(min_length=1, max_length=160)
    instructions: str = Field(default="", max_length=2000)
    shop_ids: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def validate_schedule(self):
        try:
            starts = time.fromisoformat(self.starts_at)
            ends = time.fromisoformat(self.ends_at)
        except ValueError as exc:
            raise ValueError("Enter valid 24-hour job start and end times.") from exc
        if ends <= starts:
            raise ValueError("Job end time must be after its start time.")
        if len(set(self.shop_ids)) != len(self.shop_ids):
            raise ValueError("A shop can only appear once in an assigned job.")
        return self


class JobUpdate(BaseModel):
    status: Literal["assigned", "cancelled"]


class LocationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(gt=0, le=10000)
    client_timestamp: datetime
    sequence_number: int = Field(ge=0)
    speed_mps: float | None = Field(default=None, ge=0, le=150)
    heading_deg: float | None = Field(default=None, ge=0, lt=360)
    altitude_m: float | None = Field(default=None, ge=-1000, le=100000)
    device_info: dict = Field(default_factory=dict, max_length=20)


class PointBatch(BaseModel):
    points: list[LocationPoint] = Field(min_length=1, max_length=100)


class DeviceHeartbeat(BaseModel):
    device_info: dict = Field(default_factory=dict, max_length=20)


class VisitCreate(BaseModel):
    shop_id: str = Field(min_length=1, max_length=160)
    outcome: str = Field(default="In progress", max_length=80)
    notes: str = Field(default="", max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    sales_order_id: str | None = Field(default=None, max_length=160)

    @model_validator(mode="after")
    def validate_gps_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Both visit coordinates must be supplied together.")
        return self


class VisitUpdate(BaseModel):
    outcome: str = Field(min_length=1, max_length=80)
    notes: str = Field(default="", max_length=2000)
    sales_order_id: str | None = Field(default=None, max_length=160)


class ShipmentDeliveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["DELIVERED", "PARTIALLY_DELIVERED", "DELIVERY_FAILED", "RETURNING"]
    recipient_name: str = Field(default="", max_length=200)
    quantities: dict[str, Decimal] = Field(default_factory=dict, max_length=200)
    remarks: str = Field(default="", max_length=2000)

