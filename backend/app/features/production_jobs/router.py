from urllib.parse import quote
from fastapi import APIRouter, Depends, Header, Response
from backend.app.core.config import settings
from backend.app.db.postgres import get_connection
from .models import JobPlan, Action, TaskInput, TaskEdit, TaskAction, BlockerInput, Note, DocumentInput, WorkflowConfig, ManufacturingAction
from .repository import WorkflowRepository
from .service import JobService
from .policy import READERS, require

router=APIRouter(prefix='/api/production-jobs',tags=['Production jobs'])

def actor_context(x_demo_role: str=Header(...),x_demo_employee_id: str=Header(...)):
    require(settings.app_env.lower() in {'development','test'},'Production identity integration is required. Demo identities are disabled outside development/test.',503)
    require(x_demo_role in READERS,'This role has no production workspace access.',403)
    with get_connection() as db:
        row=db.execute('select payload from public.employees where id=%s',(x_demo_employee_id,)).fetchone()
    require(row and row['payload'].get('status')=='Active' and row['payload'].get('role')==x_demo_role,'Select an active HR employee matching the signed-in demo role.',403)
    return {'id':x_demo_employee_id,'role':x_demo_role}

def service(actor=Depends(actor_context)):
    with get_connection() as db:
        yield JobService(WorkflowRepository(db),actor)

@router.get('/metadata')
def metadata(svc=Depends(service)): return svc.metadata()
@router.put('/configuration')
def configuration(body:WorkflowConfig,svc=Depends(service)): return svc.configure(body)
@router.get('/analytics')
def analytics(svc=Depends(service)): return svc.analytics()
@router.post('/manufacturing-action')
def manufacturing_action(body:ManufacturingAction,svc=Depends(service)): return svc.manufacture(body)
@router.get('')
def jobs(svc=Depends(service)): return svc.list()
@router.get('/{job_id}')
def detail(job_id:str,svc=Depends(service)): return svc.detail(job_id)
@router.put('/{job_id}/plan')
def plan(job_id:str,body:JobPlan,svc=Depends(service)): return svc.plan(job_id,body)
@router.post('/{job_id}/status')
def status(job_id:str,body:Action,svc=Depends(service)): return svc.change_status(job_id,body)
@router.post('/{job_id}/reconciliation')
def reconcile(job_id:str,body:Note,svc=Depends(service)): return svc.reconcile(job_id,body)
@router.post('/{job_id}/tasks',status_code=201)
def create_task(job_id:str,body:TaskInput,svc=Depends(service)): return svc.task_save(job_id,body)
@router.put('/{job_id}/tasks/{task_id}')
def edit_task(job_id:str,task_id:str,body:TaskEdit,svc=Depends(service)): return svc.task_save(job_id,body,task_id)
@router.post('/{job_id}/tasks/{task_id}/status')
def task_action(job_id:str,task_id:str,body:TaskAction,svc=Depends(service)): return svc.task_action(job_id,task_id,body)
@router.post('/{job_id}/tasks/{task_id}/exceptions')
def exception(job_id:str,task_id:str,body:Note,svc=Depends(service)): return svc.exception(job_id,task_id,body)
@router.post('/{job_id}/tasks/{task_id}/comments')
def task_comment(job_id:str,task_id:str,body:Note,svc=Depends(service)):
    svc.access(job_id,True)
    require(svc.repo.one('select id from public.production_job_tasks where id=%s and production_order_id=%s',(task_id,job_id)),'Task not found.',404)
    svc.repo.activity(svc.actor,'Task comment',job=job_id,task=task_id,details={'text':body.text})
    return svc.detail(job_id)
@router.post('/{job_id}/tasks/{task_id}/documents')
def task_document(job_id:str,task_id:str,body:DocumentInput,svc=Depends(service)): return svc.document(body,job=job_id,task=task_id)
@router.get('/{job_id}/tasks/{task_id}/documents/{document_id}')
def task_download(job_id:str,task_id:str,document_id:str,svc=Depends(service)):
    svc.access(job_id)
    return attachment_response(svc.repo.one('select * from public.production_workflow_documents where production_order_id=%s and task_id=%s and id=%s',(job_id,task_id,document_id)))
@router.post('/{job_id}/tasks/{task_id}/exceptions/{exception_id}/approve')
def approve_exception(job_id:str,task_id:str,exception_id:str,body:Note,svc=Depends(service)): return svc.exception(job_id,task_id,body,exception_id)
@router.post('/{job_id}/blockers')
def blocker(job_id:str,body:BlockerInput,svc=Depends(service)): return svc.blocker(job_id,body)
@router.post('/{job_id}/blockers/{blocker_id}/resolve')
def resolve(job_id:str,blocker_id:str,body:Note,svc=Depends(service)): return svc.resolve(job_id,blocker_id,body)
@router.post('/{job_id}/comments')
def comment(job_id:str,body:Note,svc=Depends(service)):
    svc.access(job_id,True)
    svc.repo.activity(svc.actor,'Comment',job=job_id,details={'text':body.text})
    return svc.detail(job_id)
@router.post('/{job_id}/documents')
def upload(job_id:str,body:DocumentInput,svc=Depends(service)): return svc.document(body,job=job_id)
@router.get('/{job_id}/documents/{document_id}')
def download(job_id:str,document_id:str,svc=Depends(service)):
    svc.access(job_id)
    row=svc.repo.one('select * from public.production_workflow_documents where production_order_id=%s and id=%s',(job_id,document_id))
    return attachment_response(row)

def attachment_response(row):
    require(row,'Attachment not found.',404)
    return Response(bytes(row['content']),media_type='application/octet-stream',headers={
        'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row['filename'],safe=''),
        'X-Content-Type-Options':'nosniff','Cache-Control':'no-store','Content-Security-Policy':"sandbox; default-src 'none'"})
