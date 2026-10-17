from datetime import datetime, timezone
from urllib.parse import quote
from fastapi import APIRouter, Depends, Header, Response
from backend.app.core.config import settings
from backend.app.db.postgres import get_connection
from .models import PassInput, ActionInput, ScanInput, TypePolicy, CheckpointInput, AttachmentInput
from .policy import READERS, MANAGEMENT, SECURITY, require, effective_status
from .repository import GateRepository, new_id
from .service import GateService

router = APIRouter(prefix='/api/gate-passes', tags=['Gate passes & security'])


def actor_context(x_demo_role: str = Header(...), x_demo_employee_id: str = Header(...)):
    # The existing ERP has no verified server-side identity yet. Do not accept
    # client-selected identities in a production deployment.
    require(settings.app_env.lower() in {'development', 'test'}, 'Gate access requires the ERP production authentication integration. Demo identities are disabled.', 503)
    require(x_demo_role in READERS, 'This role does not have gate-pass access.', 403)
    with get_connection() as db:
        employee = db.execute('select payload from public.employees where id=%s', (x_demo_employee_id,)).fetchone()
    require(employee and employee['payload'].get('status') == 'Active' and employee['payload'].get('role') == x_demo_role, 'Choose an active HR employee with the selected role.', 403)
    return {'id':x_demo_employee_id, 'role':x_demo_role, 'payload':employee['payload']}


def service(actor=Depends(actor_context)):
    with get_connection() as db:
        yield GateService(GateRepository(db), actor)


@router.get('/metadata')
def metadata(svc=Depends(service)):
    return svc.metadata()


@router.get('')
def passes(svc=Depends(service)):
    rows = svc.repo.list(svc.actor)
    for row in rows:
        row.pop('token_hash', None)
        row['status'] = effective_status(row)
        row['overdue'] = bool(row['return_required'] and row['return_due_at'] and row['return_due_at'] < datetime.now(timezone.utc) and row['outstanding_quantity'] > 0)
    return rows


@router.get('/activity')
def activity(svc=Depends(service)):
    clause, params = svc.repo.scope(svc.actor)
    return svc.repo.all(f'''select a.*,p.number,e.name as actor_name from public.gate_pass_audit_logs a
       join public.gate_passes p on p.id=a.pass_id join public.employees e on e.id=a.actor_id
       where {clause} order by a.created_at desc limit 100''', params)


@router.get('/scan-history')
def scan_history(svc=Depends(service)):
    require(svc.actor['role'] in SECURITY | MANAGEMENT, 'Security or management role required.', 403)
    return svc.repo.all('''select s.*,p.number,e.name as actor_name from public.gate_pass_scan_logs s
        left join public.gate_passes p on p.id=s.pass_id join public.employees e on e.id=s.actor_id
        order by s.created_at desc limit 100''')


@router.post('', status_code=201)
def create_pass(body: PassInput, svc=Depends(service)):
    return svc.create(body)


@router.post('/scan')
def scan(body: ScanInput, svc=Depends(service)):
    return svc.scan(body)


@router.put('/types/{code}')
def update_type(code: str, body: TypePolicy, svc=Depends(service)):
    require(svc.actor['role'] in MANAGEMENT, 'Factory Manager role required.', 403)
    svc.repo.lock_workspace()
    require(svc.repo.one('select code from public.gate_pass_types where code=%s', (code,)), 'Pass type not found.', 404)
    from psycopg import sql
    from psycopg.types.json import Jsonb
    values = body.model_dump()
    svc.repo.db.execute(sql.SQL('update public.gate_pass_types set {} where code=%s').format(
        sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in values)),
        (*[Jsonb(v) if isinstance(v, list) else v for v in values.values()], code))
    svc.repo.audit(svc.actor, 'POLICY_UPDATED', details={'type':code, **body.model_dump(mode='json')})
    return svc.metadata()


@router.post('/checkpoints', status_code=201)
def create_checkpoint(body: CheckpointInput, svc=Depends(service)):
    require(svc.actor['role'] in MANAGEMENT, 'Factory Manager role required.', 403)
    svc.repo.lock_workspace()
    row = svc.repo.insert('gate_checkpoints', dict(id=new_id('GC'), **body.model_dump()))
    svc.repo.audit(svc.actor, 'CHECKPOINT_CREATED', details=row)
    return row


@router.put('/checkpoints/{ident}')
def update_checkpoint(ident: str, body: CheckpointInput, svc=Depends(service)):
    require(svc.actor['role'] in MANAGEMENT, 'Factory Manager role required.', 403)
    svc.repo.lock_workspace()
    require(svc.repo.one('select id from public.gate_checkpoints where id=%s', (ident,)), 'Checkpoint not found.', 404)
    svc.repo.db.execute('update public.gate_checkpoints set name=%s,direction=%s,active=%s where id=%s', (body.name,body.direction,body.active,ident))
    svc.repo.audit(svc.actor, 'CHECKPOINT_UPDATED', details={'id':ident, **body.model_dump()})
    return {'id':ident, **body.model_dump()}


@router.get('/{ident}')
def detail(ident: str, svc=Depends(service)):
    return svc.detail(ident)


@router.put('/{ident}')
def edit_pass(ident: str, body: PassInput, svc=Depends(service)):
    return svc.create(body, ident)


@router.post('/{ident}/actions')
def action(ident: str, body: ActionInput, svc=Depends(service)):
    return svc.action(ident, body)


@router.post('/{ident}/qr')
def qr(ident: str, svc=Depends(service)):
    return svc.issue_token(ident)


@router.post('/{ident}/attachments', status_code=201)
def upload(ident: str, body: AttachmentInput, svc=Depends(service)):
    return svc.attach(ident, body)


@router.get('/{ident}/attachments/{attachment}')
def download(ident: str, attachment: str, svc=Depends(service)):
    svc.get(ident)
    row = svc.repo.one('select * from public.gate_pass_attachments where id=%s and pass_id=%s', (attachment,ident))
    require(row, 'Attachment not found.', 404)
    return Response(bytes(row['content']), media_type=row['mime_type'], headers={
        'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row['filename'], safe=''),
        'X-Content-Type-Options':'nosniff', 'Cache-Control':'no-store'})
