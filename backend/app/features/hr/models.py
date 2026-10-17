from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class EmployeeRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=160)
    email: str
    department: str
    role: str
    status: str
    salary: float = Field(ge=0)

class LeaveRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=160)
    employeeId: str
    start: str
    end: str
    status: str
