from pydantic import BaseModel, ConfigDict, Field

class InvoiceRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=160)
    client: str
    amount: float = Field(ge=0)
    currency: str = "USD"
    status: str

class ExpenseRecord(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(min_length=1, max_length=160)
    employeeId: str
    category: str
    amount: float = Field(ge=0)
    status: str
