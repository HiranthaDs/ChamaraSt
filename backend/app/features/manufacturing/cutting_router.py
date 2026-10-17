import json
from functools import lru_cache
from threading import BoundedSemaphore
from fastapi import APIRouter, Depends, Response
from backend.app.db.postgres import get_connection
from backend.app.features.production_jobs.router import actor_context
from backend.app.features.production_jobs.repository import WorkflowRepository
from backend.app.features.production_jobs.policy import require, role
from .cutting_models import CuttingInput, LayoutInput, SavePlan, PlanAction
from .cutting_service import CuttingService, EDITORS
from .cutting_engine import optimize, validate
from .cutting_exports import svg, pdf

router=APIRouter(prefix='/api/manufacturing/cutting',tags=['Cutting optimization'])
slots=BoundedSemaphore(2)


def service(actor=Depends(actor_context)):
    with get_connection() as db: yield CuttingService(WorkflowRepository(db),actor)


@lru_cache(maxsize=12)
def compute(serialized):
    inp=CuttingInput.model_validate_json(serialized)
    return [optimize(inp,mode) for mode in ['fast','maximum','offcut-first']]


@router.post('/preview')
def preview(body:CuttingInput,svc=Depends(service)):
    role(svc.actor,EDITORS);inp=svc.resolve(body)
    require(slots.acquire(blocking=False),'Optimizer is busy; try again shortly.',429)
    try:return {'inputs':inp.model_dump(),'candidates':compute(inp.model_dump_json())}
    finally:slots.release()


@router.post('/validate')
def check(body:LayoutInput,svc=Depends(service)):
    role(svc.actor,EDITORS)
    return validate(svc.resolve(body.inputs),body.placements,body.mode)


@router.get('/plans')
def plans(production_order_id:str|None=None,proposal_id:str|None=None,svc=Depends(service)):
    return svc.list(production_order_id,proposal_id)


@router.post('/plans')
def save(body:SavePlan,svc=Depends(service)): return svc.save(body)


@router.get('/plans/{pid}/versions')
def versions(pid:str,svc=Depends(service)): return svc.versions(pid)


@router.post('/plans/{pid}/action')
def action(pid:str,body:PlanAction,svc=Depends(service)): return svc.action(pid,body)


@router.get('/plans/{pid}/export/{kind}')
def export(pid:str,kind:str,sheet:int=0,svc=Depends(service)):
    p=svc.get(pid);layout=p['layout'];require(kind in {'svg','pdf','json'},'Unsupported export.',422)
    require(0<=sheet<len(layout['sheets']),'Unknown sheet.',422)
    content=svg(layout,sheet) if kind=='svg' else pdf(layout) if kind=='pdf' else json.dumps(p,ensure_ascii=False)
    return Response(content,media_type={'svg':'image/svg+xml','pdf':'application/pdf','json':'application/json'}[kind],headers={
        'Content-Disposition':f'attachment; filename="{pid}.{kind}"','X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})
