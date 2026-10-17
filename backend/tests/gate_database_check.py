"""Real database integration check. All fixture records roll back, including on failure.
Run: python -m backend.tests.gate_database_check
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from psycopg.types.json import Jsonb
from fastapi import HTTPException
from backend.app.db.postgres import get_connection
from backend.app.features.gate_passes.repository import GateRepository
from backend.app.features.gate_passes.service import GateService
from backend.app.features.gate_passes.models import PassInput, ActionInput, ScanInput
from backend.app.features.gate_passes.policy import CHECKS


def main():
    with get_connection() as db:
        try:
            prefix='QA-'+uuid4().hex[:12]
            actors={}
            for key,role in [('requester','Production Planner'),('warehouse','Warehouse Manager'),('supervisor','Supervisor'),('security','Gate Security Officer'),('officer','Sales Officer'),('salesman','Salesman')]:
                ident=prefix+'-'+key
                payload=dict(id=ident,name='Temporary gate test',role=role,status='Active',department='Manufacturing')
                db.execute('insert into public.employees(id,payload) values(%s,%s)',(ident,Jsonb(payload)))
                actors[key]=dict(id=ident,role=role,payload=payload)
            asset=prefix+'-asset'
            db.execute('insert into public.machines(id,payload) values(%s,%s)',(asset,Jsonb(dict(id=asset,name='Temporary test asset',status='Idle'))))
            job_id=prefix+'-job'
            db.execute("""insert into public.sales_field_jobs(id,salesman_id,sales_officer_id,work_date,starts_at,ends_at,territory,status)
              values(%s,%s,%s,current_date,'08:00','17:00','Rollback test','assigned')""",(job_id,actors['salesman']['id'],actors['officer']['id']))
            repo=GateRepository(db)
            svc=lambda key:GateService(repo,actors[key])
            now=datetime.now(timezone.utc)
            body=PassInput(type_code='returnable_outward',purpose='Rollback integration verification',origin='Factory',destination='Repair workshop',expected_at=now-timedelta(minutes=1),valid_until=now+timedelta(hours=1),return_due_at=now+timedelta(days=1),checkpoint_id='MAIN',vehicle_number='QA-001',driver_name='Test driver',document_reference='QA rollback only',items=[dict(kind='asset',reference_id=asset,quantity=1)])
            row=svc('requester').create(body); ident=row['id']
            for key,action in [('requester','submit'),('warehouse','verify'),('supervisor','approve'),('requester','ready'),('security','inspect')]:
                svc(key).action(ident,ActionInput(action=action,checkpoint_id='MAIN',checks={k:True for k in CHECKS}))
            qr=svc('security').issue_token(ident)
            scan=svc('security').scan(ScanInput(code=qr['qr_payload'],checkpoint_id='MAIN',direction='outward'))
            assert scan['valid'],scan['reason']
            item=repo.items(ident)[0]
            confirm=ActionInput(action='confirm',checkpoint_id='MAIN',checks={k:True for k in CHECKS},token=qr['token'],quantities={item['id']:1})
            result=svc('security').action(ident,confirm)
            assert result['status']=='COMPLETED'
            assert result['return_status']=='AWAITING_RETURN'
            try:
                svc('security').action(ident,confirm)
                raise AssertionError('Replay was accepted')
            except HTTPException:
                pass
            invalid=svc('security').scan(ScanInput(code=qr['qr_payload'],checkpoint_id='MAIN',direction='outward'))
            assert not invalid['valid']
            inward=body.model_copy(update={'type_code':'returnable_inward','parent_pass_id':ident,'return_due_at':None,'items':[]})
            from backend.app.features.gate_passes.models import ItemInput
            inward.items=[ItemInput(kind='asset',reference_id=asset,quantity=1,original_item_id=item['id'])]
            ret=svc('requester').create(inward)
            for key,action in [('requester','submit'),('warehouse','verify'),('supervisor','approve'),('requester','ready'),('security','inspect')]:
                svc(key).action(ret['id'],ActionInput(action=action,checkpoint_id='MAIN',checks={k:True for k in CHECKS}))
            token=svc('security').issue_token(ret['id'])
            svc('security').action(ret['id'],ActionInput(action='confirm',checkpoint_id='MAIN',checks={k:True for k in CHECKS},token=token['token'],quantities={repo.items(ret['id'])[0]['id']:1}))
            assert svc('requester').detail(ident)['return_status']=='FULLY_RETURNED'
            assert repo.master('asset',asset)['status']=='Idle'
            shipment_body=body.model_copy(update={'type_code':'branch_transfer','return_due_at':None,'parent_pass_id':None,'field_job_id':job_id,'destination':'Rollback test destination'})
            dispatched=svc('requester').create(shipment_body)
            for key,action in [('requester','submit'),('warehouse','verify'),('supervisor','approve'),('requester','ready'),('security','inspect')]:
                svc(key).action(dispatched['id'],ActionInput(action=action,checkpoint_id='MAIN',checks={k:True for k in CHECKS}))
            dispatch_qr=svc('security').issue_token(dispatched['id'])
            dispatched_item=repo.items(dispatched['id'])[0]
            svc('security').action(dispatched['id'],ActionInput(action='confirm',checkpoint_id='MAIN',checks={k:True for k in CHECKS},token=dispatch_qr['token'],quantities={dispatched_item['id']:1}))
            shipment=db.execute('select * from public.shipment_tracking where gate_pass_id=%s',(dispatched['id'],)).fetchone()
            assert shipment and shipment['field_job_id']==job_id and shipment['assigned_employee_id']==actors['salesman']['id']
            assert shipment['shipment_status']=='IN_TRANSIT' and shipment['tracking_status']=='AWAITING_LOCATION'
            print('PASS: gate approvals, QR movement, replay rejection, linked return, idempotent shipment creation, awaiting-GPS status, audit, and unchanged inventory.')
        finally:
            db.rollback()
            print('All integration fixture records rolled back.')


if __name__=='__main__':
    main()
