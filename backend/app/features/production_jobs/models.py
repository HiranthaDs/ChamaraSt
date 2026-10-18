from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

Priority = Literal['Low','Normal','High','Urgent']

class JobCreate(Input):
    request_id: str = Field(min_length=8, max_length=80)
    purpose: Literal['stock', 'order'] = 'stock'
    sales_order_id: str | None = None
    product_id: str
    quantity: int = Field(ge=1, le=500)
    operator_id: str
    machine_id: str
    start: date
    due: date
    priority: Priority = 'Normal'
    notes: str = Field(default='', max_length=4000)

    @model_validator(mode='after')
    def valid_plan(self):
        if self.due < self.start:
            raise ValueError('Due date cannot precede start.')
        if self.purpose == 'order' and not self.sales_order_id:
            raise ValueError('Choose a shop order for order production.')
        if self.purpose == 'stock' and self.sales_order_id:
            raise ValueError('Stock production cannot have a shop order link.')
        return self

class VersionInput(Input):
    version: int = Field(ge=1)

class JobPlan(VersionInput):
    supervisor_id: str | None = None
    priority: Priority = 'Normal'
    planned_start: date | None = None
    due_date: date | None = None
    dispatch_required: bool = False
    sales_order_id: str | None = None
    @model_validator(mode='after')
    def dates(self):
        if self.planned_start and self.due_date and self.due_date < self.planned_start:
            raise ValueError('Due date cannot precede start.')
        if self.dispatch_required and not self.sales_order_id:
            raise ValueError('A customer sales order is required for dispatch jobs.')
        return self

class Action(VersionInput):
    status: str = Field(min_length=1,max_length=50)
    reason: str = Field(default='',max_length=4000)

class ChecklistItem(Input):
    title: str = Field(min_length=1,max_length=200)
    done: bool = False

class TaskInput(Input):
    title: str = Field(min_length=1,max_length=200)
    description: str = Field(default='',max_length=6000)
    parent_task_id: str | None = None
    assigned_employee_id: str | None = None
    supervisor_id: str | None = None
    stage: str | None = None
    priority: Priority = 'Normal'
    planned_start: date | None = None
    due_date: date | None = None
    estimated_hours: float = Field(default=0,ge=0,le=10000)
    approval_required: bool = True
    dependencies: list[str] = Field(default_factory=list,max_length=100)
    checklist: list[ChecklistItem] = Field(default_factory=list,max_length=100)
    @model_validator(mode='after')
    def dates(self):
        if self.planned_start and self.due_date and self.due_date < self.planned_start:
            raise ValueError('Due date cannot precede start.')
        return self

class TaskEdit(TaskInput, VersionInput):
    pass

class TaskAction(Action):
    actual_hours: float = Field(default=0,ge=0,le=10000)
    checklist: list[ChecklistItem] = Field(default_factory=list,max_length=100)

class BlockerInput(Input):
    task_id: str | None = None
    blocker_type: Literal['Material shortage','Machine breakdown','Employee unavailable','Pending approval','Quality failure','Missing technical drawing','Supplier delay','Equipment maintenance','Other operational issue']
    description: str = Field(min_length=3,max_length=4000)
    severity: Literal['Low','Medium','High','Critical'] = 'Medium'
    assigned_to: str
    expected_resolution: date | None = None

class Note(Input):
    text: str = Field(min_length=3,max_length=6000)

class DocumentInput(Input):
    filename: str = Field(min_length=1,max_length=160,pattern=r'^[^/\\\x00-\x1f]+$')
    mime_type: Literal['application/pdf','image/png','image/jpeg','application/step','application/dxf']
    content_base64: str = Field(min_length=4,max_length=7000000)

class WorkflowConfig(Input):
    column_labels: dict[str,str] = Field(default_factory=dict)
    column_order: list[str] = Field(default_factory=list)
    stage_weights: dict[str,float] = Field(default_factory=dict)
    review_roles: dict[str,list[str]] = Field(default_factory=dict)

class ManufacturingAction(Input):
    action: Literal['job-reserve','job-start','job-pause','job-complete','job-review','qc','goods-move']
    id: str
    hours: float = Field(default=0,ge=0,le=24)
    notes: str = Field(default='',max_length=4000)
    decision: Literal['Approve','Rework','Reject'] = 'Approve'
    reason: str = Field(default='',max_length=4000)
    passed: bool | None = None
    bin: str | None = None
