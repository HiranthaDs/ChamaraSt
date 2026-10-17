"""Millimetres and existing ERP minor currency units throughout."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


class Part(Strict):
    id: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    shape: Literal['rectangle', 'square', 'circle', 'triangle', 'polygon']
    w: float = Field(default=100, gt=0, le=20000)
    h: float = Field(default=100, gt=0, le=20000)
    diameter: float = Field(default=100, gt=0, le=20000)
    vertices: list[tuple[float, float]] = Field(default_factory=list, max_length=100)
    quantity: int = Field(default=1, ge=1, le=150)
    material: str = Field(min_length=1, max_length=100)
    grade: str = Field(min_length=1, max_length=100)
    thickness: float = Field(gt=0, le=500)
    rotations: list[float] = Field(default_factory=lambda: [0, 90], min_length=1, max_length=16)
    grain: bool = False
    priority: int = Field(default=0, ge=0, le=10)
    product_id: str | None = None


class Sheet(Strict):
    id: str = Field(min_length=1, max_length=80)
    inventory_id: str | None = None
    w: float = Field(gt=0, le=20000)
    h: float = Field(gt=0, le=20000)
    material: str = Field(min_length=1, max_length=100)
    grade: str = Field(min_length=1, max_length=100)
    thickness: float = Field(gt=0, le=500)
    quantity: int = Field(default=1, ge=1, le=30)
    cost: int = Field(default=0, ge=0)
    offcut: bool = False
    # GeoJSON Polygon, including holes, for verified irregular stock.
    geometry: dict | None = None


class Constraints(Strict):
    kerf: float = Field(default=2, ge=0, le=30)
    spacing: float = Field(default=2, ge=0, le=100)
    heat_spacing: float = Field(default=0, ge=0, le=100)
    edge: float = Field(default=10, ge=0, le=1000)
    min_offcut: float = Field(default=100, gt=0, le=5000)
    machine_w: float = Field(default=3200, gt=0, le=20000)
    machine_h: float = Field(default=1600, gt=0, le=20000)
    machine_thickness: float = Field(default=12, gt=0, le=500)
    zones: list[list[tuple[float, float]]] = Field(default_factory=list, max_length=20)
    seconds: float = Field(default=2, ge=.1, le=8)


class CuttingInput(Strict):
    sheets: list[Sheet] = Field(min_length=1, max_length=30)
    parts: list[Part] = Field(min_length=1, max_length=40)
    constraints: Constraints = Field(default_factory=Constraints)
    production_order_id: str | None = None
    proposal_id: str | None = None
    machine_id: str | None = None

    @model_validator(mode='after')
    def limits(self):
        if sum(p.quantity for p in self.parts) > 150 or sum(s.quantity for s in self.sheets) > 30:
            raise ValueError('Maximum 150 pieces and 30 sheets per request.')
        for rows in [self.parts, self.sheets]:
            if len({r.id for r in rows}) != len(rows):
                raise ValueError('Part and sheet IDs must be unique.')
        if self.production_order_id and self.proposal_id:
            raise ValueError('A feasibility plan cannot also be a production release.')
        return self


class Placement(Strict):
    part_id: str
    instance: int = Field(ge=1, le=150)
    sheet_id: str
    sheet_instance: int = Field(ge=1, le=30)
    x: float = Field(ge=0, le=20000)
    y: float = Field(ge=0, le=20000)
    rotation: float = 0


class LayoutInput(Strict):
    inputs: CuttingInput
    placements: list[Placement] = Field(max_length=150)
    mode: Literal['fast', 'maximum', 'offcut-first'] = 'fast'


class SavePlan(LayoutInput):
    optimized_placements: list[Placement] = Field(default_factory=list, max_length=150)
    plan_id: str | None = None
    version: int = Field(default=0, ge=0)


class PlanAction(Strict):
    version: int = Field(ge=1)
    action: Literal['submit', 'approve', 'return', 'start', 'complete', 'verify']
    note: str = Field(default='', max_length=2000)
    accepted_quantity: int | None = Field(default=None, ge=0, le=150)
    verified_offcuts: list[str] = Field(default_factory=list, max_length=300)
