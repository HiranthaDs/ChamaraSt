from datetime import date
from typing import Literal
from pydantic import Field
from backend.app.features.production_jobs.models import Input, Priority, VersionInput

class ProposalStatusAction(VersionInput):
    status: str = Field(min_length=1,max_length=50)
    reason: str = Field(default='',max_length=4000)
    fast_track: bool = False

class BOMLine(Input):
    materialId: str
    amount: float = Field(gt=0,le=1000000)

class Specifications(Input):
    category: str = Field(default='',max_length=200)
    description: str = Field(default='',max_length=6000)
    business_justification: str = Field(default='',max_length=6000)
    vehicle_manufacturer: str = Field(default='',max_length=200)
    vehicle_model: str = Field(default='',max_length=200)
    model_years: str = Field(default='',max_length=100)
    part_position: str = Field(default='',max_length=200)
    dimensions: str = Field(default='',max_length=1000)
    material_specifications: str = Field(default='',max_length=4000)
    compatibility: str = Field(default='',max_length=4000)
    comparable_product_id: str | None = None
    customer_order_id: str | None = None
    customer_segment: str = Field(default='',max_length=500)
    expected_demand: int = Field(default=0,ge=0,le=100000000)
    market_references: str = Field(default='',max_length=4000)
    evidence: str = Field(default='',max_length=6000)
    manufacturing_requirements: str = Field(default='',max_length=4000)
    special_tools: str = Field(default='',max_length=2000)
    complexity: Literal['Low','Medium','High'] = 'Medium'
    quality_criteria: str = Field(default='',max_length=4000)
    feasibility: Literal['PENDING_REVIEW','FEASIBLE','FEASIBLE_WITH_CHANGES','NOT_FEASIBLE'] = 'PENDING_REVIEW'
    feasibility_notes: str = Field(default='',max_length=4000)
    bom: list[BOMLine] = Field(default_factory=list,max_length=100)
    route: list[str] = Field(default_factory=lambda:['Bending','Welding','Grinding','Painting','Assembly','Quality inspection','Packaging'],min_length=1,max_length=30)

class ProposalInput(Input):
    title: str = Field(min_length=3,max_length=200)
    proposed_product_name: str = Field(min_length=3,max_length=200)
    priority: Priority = 'Normal'
    reviewer_id: str | None = None
    specifications: Specifications
    change_summary: str = Field(default='Initial proposal',min_length=3,max_length=4000)
    effective_date: date | None = None

class ProposalEdit(ProposalInput,VersionInput):
    pass

class ReviewInput(VersionInput):
    review_stage: Literal['Technical','Materials','Cost','Prototype','Quality','Final']
    decision: Literal['Approved','Changes requested','Rejected']
    comments: str = Field(min_length=3,max_length=4000)

class Costs(Input):
    material: int = Field(default=0,ge=0,le=100000000000)
    cutting: int = Field(default=0,ge=0,le=100000000000)
    waste: int = Field(default=0,ge=0,le=100000000000)
    offcut_credit: int = Field(default=0,ge=0,le=100000000000)
    labor: int = Field(default=0,ge=0,le=100000000000)
    machine: int = Field(default=0,ge=0,le=100000000000)
    consumables: int = Field(default=0,ge=0,le=100000000000)
    overhead: int = Field(default=0,ge=0,le=100000000000)
    prototype: int = Field(default=0,ge=0,le=100000000000)

class EstimateInput(VersionInput):
    name: str = Field(min_length=2,max_length=200)
    costs: Costs
    estimated_selling_price: int = Field(ge=0,le=100000000000)

class PrototypeInput(VersionInput):
    request_id: str = Field(pattern=r'^[a-zA-Z0-9-]{8,80}$')
    quantity: int = Field(ge=1,le=500)
    operator: str
    supervisor_id: str
    machine: str
    start: date
    due: date

class PrototypeTest(Input):
    result: Literal['Pass','Fail','Changes required']
    findings: str = Field(min_length=3,max_length=6000)

class ConversionInput(VersionInput):
    sku: str = Field(pattern=r'^[A-Z0-9][A-Z0-9-]{2,39}$')
    existing_product_id: str | None = None
    estimate_id: str

