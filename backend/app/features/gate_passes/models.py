from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ItemInput(Input):
    kind: Literal['material', 'product', 'good', 'sheet', 'asset']
    reference_id: str = Field(min_length=1, max_length=160)
    quantity: Decimal = Field(gt=0, le=10000000, decimal_places=3)
    condition: str = Field(default='Good', max_length=120)
    original_item_id: str | None = Field(default=None, max_length=160)


class PassInput(Input):
    type_code: str = Field(min_length=1, max_length=60)
    purpose: str = Field(min_length=5, max_length=2000)
    origin: str = Field(min_length=2, max_length=200)
    destination: str = Field(min_length=2, max_length=200)
    expected_at: datetime
    valid_until: datetime
    return_due_at: datetime | None = None
    checkpoint_id: str = Field(min_length=1, max_length=80)
    vehicle_number: str = Field(min_length=2, max_length=80)
    driver_name: str = Field(min_length=2, max_length=160)
    driver_identity: str = Field(default='', max_length=120)
    sales_order_id: str | None = None
    purchase_id: str | None = None
    production_order_id: str | None = None
    invoice_id: str | None = None
    field_job_id: str | None = None
    parent_pass_id: str | None = None
    document_reference: str = Field(default='', max_length=500)
    declared_value: Decimal = Field(default=0, ge=0, le=100000000000, decimal_places=2)
    items: list[ItemInput] = Field(min_length=1, max_length=200)

    @model_validator(mode='after')
    def dates_and_items(self):
        for d in (self.expected_at, self.valid_until, self.return_due_at):
            if d and d.utcoffset() is None:
                raise ValueError('Dates must include a timezone.')
        if self.valid_until <= self.expected_at:
            raise ValueError('Expiry must be after the expected movement time.')
        if self.return_due_at and self.return_due_at <= self.expected_at:
            raise ValueError('Return due date must be after the expected movement.')
        refs = [(x.kind, x.reference_id) for x in self.items]
        if len(set(refs)) != len(refs):
            raise ValueError('Combine duplicate item lines.')
        return self


class ActionInput(Input):
    action: Literal['submit', 'verify', 'approve', 'reject', 'cancel', 'ready', 'inspect', 'confirm', 'exception', 'resolve_exception', 'write_off']
    reason: str = Field(default='', max_length=2000)
    checkpoint_id: str | None = None
    token: str | None = Field(default=None, max_length=300)
    checks: dict[str, bool] = Field(default_factory=dict)
    quantities: dict[str, Decimal] = Field(default_factory=dict)

    @model_validator(mode='after')
    def quantities_valid(self):
        if any(not x.is_finite() or x < 0 or x > 10000000 or x.as_tuple().exponent < -3 for x in self.quantities.values()):
            raise ValueError('Quantities must be nonnegative, with at most three decimal places.')
        return self


class ScanInput(Input):
    code: str = Field(min_length=1, max_length=300)
    checkpoint_id: str = Field(min_length=1, max_length=80)
    direction: Literal['inward', 'outward']


class TypePolicy(Input):
    enabled: bool
    require_document: bool
    require_invoice: bool
    approval_roles: list[Literal['Supervisor', 'Factory Manager', 'Finance Officer']] = Field(min_length=1, max_length=3)
    high_value_threshold: Decimal = Field(ge=0, le=100000000000)
    allow_partial: bool

    @model_validator(mode='after')
    def distinct_roles(self):
        if len(set(self.approval_roles)) != len(self.approval_roles):
            raise ValueError('Each approval role can appear only once.')
        return self


class CheckpointInput(Input):
    name: str = Field(min_length=2, max_length=100)
    direction: Literal['both', 'inward', 'outward'] = 'both'
    active: bool = True


class AttachmentInput(Input):
    filename: str = Field(min_length=1, max_length=160)
    mime_type: Literal['application/pdf', 'image/png', 'image/jpeg']
    content_base64: str = Field(min_length=4, max_length=7000000)
