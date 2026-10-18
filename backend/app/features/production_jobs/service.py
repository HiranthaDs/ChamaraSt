import base64
import copy
import math
from datetime import date, datetime, timezone, timedelta
from .policy import (STAGES, JOB_COLUMNS, PROPOSAL_COLUMNS, PLANNERS, FINANCE, READERS, WORKERS,
                     REVIEW_ROLES, require, role, validate_dependencies, progress)
from .repository import ident

def now():
    return datetime.now(timezone.utc)

class JobService:
    def __init__(self, repo, actor):
        self.repo, self.actor = repo, actor
        role(actor,READERS)

    def metadata(self):
        state = self.repo.state()
        m = state.get('manufacturing',{})
        return {'columns':JOB_COLUMNS,'proposal_columns':PROPOSAL_COLUMNS,'stages':STAGES,
                'review_roles':{**REVIEW_ROLES,**(self.repo.config().get('review_roles') or {})},'review_role_options':REVIEW_ROLES,
                'config':self.repo.config(),'can_plan':self.actor['role'] in PLANNERS,'can_finance':self.actor['role'] in FINANCE,
                'employees':[{k:e.get(k) for k in ['id','name','role','department','status']} for e in state.get('employees',[]) if e.get('status')=='Active'],
                'materials':[{k:r.get(k) for k in ['id','name','unit','onHand','reserved']} for r in m.get('materials',[])],
                'products':[{k:r.get(k) for k in ['id','name','revision','status']} for r in m.get('products',[])],
                'machines':[{k:r.get(k) for k in ['id','name','status']} for r in m.get('machines',[])],
                'sales_orders':[{k:r.get(k) for k in ['id','productId','quantity','status']} for r in m.get('orders',[])]}

    def create(self, body):
        role(self.actor, PLANNERS)
        self.repo.lock()
        state = self.repo.state()
        m = state['manufacturing']
        previous = next((j for j in m.get('jobs', []) if j.get('creationRequest') == body.request_id), None)
        if previous:
            require(previous.get('createdBy') == self.actor['id'], 'Request belongs to another employee.', 403)
            return self.detail(previous['id'])
        product = next((p for p in m.get('products', []) if p['id'] == body.product_id), None)
        require(product and product.get('status') not in {'Development', 'Archived'}, 'Choose an approved production product.', 422)
        require(product.get('bom') and product.get('quality'), 'Complete the product BOM and quality criteria first.', 422)
        employee = self.repo.employee(body.operator_id)
        require(employee.get('role') in {'Manufacturing Operator', 'Factory Manager'}, 'Assign a manufacturing operator.', 422)
        machine = next((x for x in m.get('machines', []) if x['id'] == body.machine_id), None)
        require(machine and machine.get('status') not in {'Maintenance', 'Unavailable'}, 'Choose an available production machine.', 422)
        if body.purpose == 'order':
            order = next((o for o in m.get('orders', []) if o['id'] == body.sales_order_id), None)
            require(order and order.get('status') == 'Requested' and order['productId'] == body.product_id,
                    'Choose an unallocated shop order for this product.', 422)
            stock = sum(1 for g in m.get('goods', []) if g.get('productId') == body.product_id and g.get('status') == 'Available' and g.get('qc') == 'Pass' and g.get('bin') != 'QA-HOLD')
            linked = sum(j['quantity'] for j in m.get('jobs', []) if j.get('salesOrderId') == order['id'] and j.get('status') not in {'Completed', 'Cancelled'})
            receiving = sum(1 for g in m.get('goods', []) if g.get('productId') == body.product_id and g.get('status') == 'Receiving' and g.get('qc') == 'Pass' and any(j['id'] == g.get('jobId') and j.get('salesOrderId') == order['id'] for j in m.get('jobs', [])))
            shortage = max(0, order['quantity'] - stock - linked - receiving)
            require(body.quantity <= shortage, f'Only {shortage} additional units are needed now. Refresh stock and existing production before creating another order.')
        job = dict(id=ident('MO'), productId=body.product_id, quantity=body.quantity,
                   purpose=body.purpose, salesOrderId=body.sales_order_id, creationRequest=body.request_id,
                   operator=body.operator_id, machine=body.machine_id, start=body.start.isoformat(), due=body.due.isoformat(),
                   priority=body.priority, notes=body.notes, stage=0, status='Planned', materialsPosted=False,
                   materialCost=0, laborCost=0, overhead=0, hours=0, history=[], createdBy=self.actor['id'],
                   productSnapshot=copy.deepcopy(product), route=product.get('route') or STAGES)
        m.setdefault('jobs', []).insert(0, job)
        self.repo.save_state(state)
        self.ensure(job)
        self.repo.activity(self.actor, 'Production order created', job=job['id'], details={'purpose':body.purpose, 'sales_order_id':body.sales_order_id, 'quantity':body.quantity})
        return self.detail(job['id'])

    def access(self, job_id, write=False):
        if write:
            self.repo.lock()
        row = self.repo.one('select payload from public.production_orders where id=%s',(job_id,))
        require(row,'Production order not found.',404)
        if self.actor['role'] in WORKERS:
            assigned = row['payload'].get('operator')==self.actor['id'] or self.repo.one(
                'select id from public.production_job_tasks where production_order_id=%s and assigned_employee_id=%s',(job_id,self.actor['id']))
            require(assigned,'You can only access your assigned production jobs.',403)
        return row['payload']

    def management(self, job):
        row = self.repo.one('select * from public.production_job_management where production_order_id=%s',(job['id'],))
        return row or {'production_order_id':job['id'],'status':'Backlog','version':1,'priority':job.get('priority','Normal'),
                       'planned_start':job.get('start'),'due_date':job.get('due'),'supervisor_id':None,'dispatch_required':job.get('purpose')=='order',
                       'sales_order_id':job.get('salesOrderId'),'approved_by':None,'reconciled_by':None,'specification':{}}

    def ensure(self, job):
        row = self.repo.one('select * from public.production_job_management where production_order_id=%s',(job['id'],))
        if row:
            return row
        m = self.repo.state()['manufacturing']
        product = job.get('productSnapshot') or next((p for p in m.get('products',[]) if p['id']==job['productId']),{})
        return self.repo.insert('production_job_management',dict(production_order_id=job['id'],priority=job.get('priority','Normal'),
            planned_start=job.get('start') or None,due_date=job.get('due') or None,
            dispatch_required=job.get('purpose')=='order',sales_order_id=job.get('salesOrderId'),specification={
                'product_id':job['productId'],'revision':job.get('bomRevision') or product.get('revision'),
                'bom':product.get('bom',[]),'route':job.get('route') or product.get('route') or STAGES,
                'quality':product.get('quality',''),'product_snapshot':product}))

    def check_version(self, row, version):
        require(row['version']==version,'This record changed. Refresh it before saving.',409)

    def summary(self, job, m, tasks, meta, goods):
        product = next((p for p in m.get('products',[]) if p['id']==job.get('productId')), {})
        metrics = progress(job,product,goods,tasks,self.repo.config().get('stage_weights'))
        blockers = self.repo.all('select * from public.production_job_blockers where production_order_id=%s and resolved_at is null',(job['id'],))
        derived = meta['status']
        if derived != 'Closed':
            if blockers: derived='Blocked / On Hold'
            elif metrics['manufactured']: derived='Production Completed' if derived not in {'Ready for Dispatch','Dispatched'} else derived
            elif job.get('status')=='Awaiting QC': derived='Quality Inspection'
            elif job.get('materialsPosted'): derived='In Progress'
            elif job.get('status')=='Ready' and meta.get('approved_by'): derived='Ready for Production'
        route=job.get('route') or product.get('route') or STAGES
        missing=[]
        for line in product.get('bom',[]):
            material=next((x for x in m.get('materials',[]) if x['id']==line['materialId']),{})
            shortage=max(0,line.get('amount',0)*job.get('quantity',0)-material.get('onHand',0)+material.get('reserved',0))
            if shortage and not job.get('bom'): missing.append({'material':material.get('name',line['materialId']),'quantity':shortage})
        due=str(meta.get('due_date') or '')
        safe_meta=copy.deepcopy(meta)
        if self.actor['role'] not in FINANCE:
            spec=safe_meta.get('specification',{})
            spec.pop('product_snapshot',None)
            spec['bom']=[{k:v for k,v in b.items() if k!='cost'} for b in spec.get('bom',[])]
        return {**safe_meta,'id':job['id'],'product_name':product.get('name',job.get('productId')),'product_id':job.get('productId'),
            'image':product.get('image'),'quantity':job.get('quantity',0),'operator':job.get('operator'),
            'current_stage':route[min(job.get('stage',0),len(route)-1)],'production_status':job.get('status'),
            'board_status':derived,'progress':metrics,'shortages':missing,'blockers':len(blockers),
            'overdue':bool(due and due<date.today().isoformat() and derived!='Closed'),
            'team':list({t['assigned_employee_id'] for t in tasks if t.get('assigned_employee_id')} | ({job['operator']} if job.get('operator') else set()))}

    def list(self):
        state=self.repo.state(); m=state.get('manufacturing',{}); result=[]
        tasks=self.repo.all('select * from public.production_job_tasks')
        for job in m.get('jobs',[]):
            mine=[t for t in tasks if t['production_order_id']==job['id']]
            if self.actor['role'] in WORKERS and job.get('operator')!=self.actor['id'] and not any(t['assigned_employee_id']==self.actor['id'] for t in mine): continue
            result.append(self.summary(job,m,mine,self.management(job),[g for g in m.get('goods',[]) if g.get('jobId')==job['id']]))
        return result

    def detail(self, job_id):
        job=self.access(job_id); state=self.repo.state(); m=state['manufacturing']
        tasks=self.repo.all('select * from public.production_job_tasks where production_order_id=%s order by created_at',(job_id,))
        deps=self.repo.all('select d.* from public.production_task_dependencies d join public.production_job_tasks t on t.id=d.task_id where t.production_order_id=%s',(job_id,))
        for t in tasks: t['dependencies']=[d['depends_on_task_id'] for d in deps if d['task_id']==t['id']]
        goods=[g for g in m.get('goods',[]) if g.get('jobId')==job_id]
        meta=self.management(job)
        result=self.summary(job,m,tasks,meta,goods)
        product=next((p for p in m.get('products',[]) if p['id']==job.get('productId')), {})
        result.update(tasks=tasks,stages=job.get('history',[]),materials=job.get('bom') or product.get('bom',[]),
            quality={'result':job.get('qc','Pending'),'criteria':meta.get('specification',{}).get('quality') or product.get('quality',''),
                     'rejected_units':job.get('rejectedQuantity'),'rework_units':job.get('reworkQuantity')},
            goods=goods,blocker_history=self.repo.all('select * from public.production_job_blockers where production_order_id=%s order by reported_at desc',(job_id,)),
            exceptions=self.repo.all('select e.* from public.production_dependency_exceptions e join public.production_job_tasks t on t.id=e.task_id where t.production_order_id=%s',(job_id,)),
            activity=self.repo.all('select * from public.production_workflow_activity where production_order_id=%s order by created_at desc limit 500',(job_id,)),
            documents=self.repo.all('select id,filename,mime_type,uploaded_by,created_at,task_id from public.production_workflow_documents where production_order_id=%s',(job_id,)),
            stock_movements=[v for v in m.get('movements',[]) if v.get('reference')==job_id or v.get('item') in {g['id'] for g in goods}],
            attendance={e:state.get('attendance',{}).get(e,{}).get('status','Not recorded') for e in result['team']})
        gates=self.repo.all('''select id,number,status,direction,sales_order_id,verified_by,inspected_by from public.gate_passes
            where production_order_id=%s or sales_order_id=%s''',(job_id,meta.get('sales_order_id')))
        ids=[g['id'] for g in gates]
        result['dispatch']={'gates':gates,'movements':self.repo.all('select * from public.gate_pass_movements where pass_id=any(%s)',(ids,)),
            'shipments':self.repo.all('select id,gate_pass_id,shipment_status,dispatched_at,assigned_employee_id from public.shipment_tracking where gate_pass_id=any(%s)',(ids,))}
        result['dispatch']['deliveries']=self.repo.all('select d.* from public.shipment_delivery_confirmations d join public.shipment_tracking s on s.id=d.shipment_id where s.gate_pass_id=any(%s)',(ids,))
        if self.actor['role'] in FINANCE:
            result['costs']={'material':job.get('materialCost',0),'labor':job.get('laborCost',0),'overhead':job.get('overhead',0),
                'postings':[c for c in m.get('costs',[]) if c.get('reference','').split(':')[0]==job_id]}
        else:
            result['materials']=[{k:v for k,v in r.items() if k!='cost'} for r in result['materials']]
            result['goods']=[{k:v for k,v in r.items() if k!='cost'} for r in result['goods']]
            result['specification']={**result.get('specification',{}),'bom':[{k:v for k,v in b.items() if k!='cost'} for b in result.get('specification',{}).get('bom',[])]}
        return result

    def plan(self, job_id, body):
        role(self.actor,PLANNERS); job=self.access(job_id,True); meta=self.ensure(job); self.check_version(meta,body.version)
        require(meta['status']!='Closed','Closed jobs cannot be rescheduled.')
        if body.supervisor_id: require(self.repo.employee(body.supervisor_id)['role'] in PLANNERS,'Choose a production supervisor.',422)
        if body.sales_order_id:
            order=self.repo.one('select payload from public.sales_orders where id=%s',(body.sales_order_id,))
            require(order and order['payload'].get('productId')==job['productId'],'Sales order product does not match.',422)
        values=body.model_dump(exclude={'version'}); values.update(version=meta['version']+1,updated_at=now())
        old_start=meta.get('planned_start'); new_start=body.planned_start
        if old_start and new_start:
            delta=(new_start-old_start).days
            self.repo.db.execute("update public.production_job_tasks set planned_start=planned_start+%s,due_date=due_date+%s,version=version+1,updated_at=now() where production_order_id=%s and status not in ('COMPLETED','CANCELLED')",(delta,delta,job_id))
        self.repo.update('production_job_management','production_order_id',job_id,values)
        state = self.repo.state()
        canonical = next(j for j in state['manufacturing']['jobs'] if j['id'] == job_id)
        canonical.update(salesOrderId=body.sales_order_id, purpose='order' if body.sales_order_id else 'stock',
                         priority=body.priority, start=body.planned_start.isoformat() if body.planned_start else '',
                         due=body.due_date.isoformat() if body.due_date else '')
        self.repo.save_state(state)
        self.repo.activity(self.actor,'Job plan updated',job=job_id,details=body.model_dump(mode='json'))
        self.repo.notify(self.actor,body.supervisor_id,'Production plan assigned: '+job_id,'production_order',job_id)
        return self.detail(job_id)

    def change_status(self, job_id, body):
        role(self.actor,PLANNERS | {'Warehouse Manager','Finance Officer'})
        job=self.access(job_id,True); meta=self.ensure(job); self.check_version(meta,body.version)
        target=body.status; require(target in JOB_COLUMNS,'Unknown board column.',422)
        if target==meta['status']: return self.detail(job_id)
        require(meta['status']!='Closed','A closed job is immutable.')
        detail=self.detail(job_id); metrics=detail['progress']; fields={'status':target,'version':meta['version']+1,'updated_at':now()}
        if target=='Backlog': require(meta['status']=='Pending Approval' and body.reason,'Only a pending request can be returned with a reason.')
        elif target=='Pending Approval': require(meta['status']=='Backlog','Only backlog jobs can be submitted.')
        elif target=='Ready for Production':
            role(self.actor,{'Factory Manager','Supervisor'})
            require(meta['status']=='Pending Approval' and self.actor['id']!=job.get('createdBy'),'An independent supervisor must approve a submitted job.')
            require(job.get('bom') and job.get('status')=='Ready','Reserve materials through Manufacturing first.')
            fields['approved_by']=self.actor['id']
        elif target=='In Progress': require(job.get('materialsPosted') and job.get('status') in {'Running','Ready','Awaiting approval','Rework','Paused'},'Start production through its authorized manufacturing workflow.')
        elif target=='Blocked / On Hold': require(detail['blockers']>0,'Report a blocker with an owner first.')
        elif target=='Quality Inspection': require(job.get('status')=='Awaiting QC','Complete the prerequisite production stages first.')
        elif target in {'Production Completed','Ready for Dispatch','Dispatched','Closed'}:
            require(metrics['manufactured'],'Quality approval and all finished-goods receipts are required.')
            require(not detail['blockers'],'Resolve open blockers first.')
            if target in {'Ready for Dispatch','Dispatched'}: require(meta['dispatch_required'],'This is a stock replenishment job.')
            if target=='Ready for Dispatch': role(self.actor,{'Factory Manager','Warehouse Manager'})
            if target=='Dispatched' or (target=='Closed' and meta['dispatch_required']):
                require(any(x['direction']=='outward' for x in detail['dispatch']['movements']),'Security must confirm the linked outward Gate Pass.')
                gate_ids=[g['id'] for g in detail['dispatch']['gates'] if g['direction']=='outward']
                items=self.repo.all('select * from public.gate_pass_items where pass_id=any(%s)',(gate_ids,))
                serials={g['id'] for g in detail['goods']}
                moved_serials={i['good_id'] for i in items if i.get('good_id') in serials and i['moved_quantity']>=1}
                bulk=sum(i['moved_quantity'] for i in items if i.get('product_id')==job['productId'])
                require(len(moved_serials)+bulk>=job['quantity'],'The linked outward Gate Pass must account for the full job quantity before dispatch or closure.')
            if target=='Closed':
                role(self.actor,{'Factory Manager','Warehouse Manager'})
                require(meta.get('reconciled_by'),'Warehouse reconciliation is required before closure.')
                require(all(t['status'] in {'COMPLETED','CANCELLED'} for t in detail['tasks']),'Finish or cancel outstanding tasks first.')
                fields['closed_at']=now()
        self.repo.update('production_job_management','production_order_id',job_id,fields)
        self.repo.activity(self.actor,'Job status changed',job=job_id,details={'from':meta['status'],'to':target,'reason':body.reason})
        self.repo.notify(self.actor,meta.get('supervisor_id'),'Production status: '+target,'production_order',job_id)
        return self.detail(job_id)

    def reconcile(self, job_id, body):
        role(self.actor,{'Factory Manager','Warehouse Manager'}); job=self.access(job_id,True); meta=self.ensure(job)
        require(self.detail(job_id)['progress']['manufactured'],'Finish production, quality inspection, and warehouse receipt first.')
        self.repo.update('production_job_management','production_order_id',job_id,{'reconciled_by':self.actor['id'],'reconciliation_note':body.text,'version':meta['version']+1})
        self.repo.activity(self.actor,'Warehouse reconciled',job=job_id,details={'note':body.text})
        return self.detail(job_id)

    def task_save(self, job_id, body, task_id=None):
        role(self.actor,PLANNERS); job=self.access(job_id,True); meta=self.ensure(job)
        require(meta['status']!='Closed','Closed job cannot be edited.')
        values=body.model_dump(exclude={'dependencies','version'})
        if body.assigned_employee_id: self.repo.employee(body.assigned_employee_id)
        if body.supervisor_id: require(self.repo.employee(body.supervisor_id)['role'] in PLANNERS,'Choose an authorized supervisor.',422)
        require(not body.approval_required or body.supervisor_id,'Select a reviewer for tasks requiring approval.',422)
        require(not body.supervisor_id or body.supervisor_id!=body.assigned_employee_id,'Task owner and reviewer must be different.',422)
        if body.stage: require(body.stage in STAGES or body.stage=='Cutting','Unknown production stage.',422)
        all_tasks=self.repo.all('select * from public.production_job_tasks where production_order_id=%s',(job_id,))
        ids={t['id'] for t in all_tasks}
        require(set(body.dependencies)<=ids,'Dependencies must belong to this job.',422)
        if body.parent_task_id: require(body.parent_task_id in ids,'Parent must belong to this job.',422)
        if task_id:
            task=next((t for t in all_tasks if t['id']==task_id),None); require(task,'Task not found.',404); self.check_version(task,body.version)
            require(task['status'] not in {'COMPLETED','CANCELLED'},'Completed task history is immutable.')
        task_id=task_id or ident('TASK')
        parent=body.parent_task_id
        while parent:
            require(parent!=task_id,'Subtasks cannot contain a cycle.',422)
            parent=next((t['parent_task_id'] for t in all_tasks if t['id']==parent),None)
        edges=self.repo.all('select d.* from public.production_task_dependencies d join public.production_job_tasks t on t.id=d.task_id where t.production_order_id=%s',(job_id,))
        validate_dependencies(task_id,body.dependencies,[(e['task_id'],e['depends_on_task_id']) for e in edges])
        existing=next((t for t in all_tasks if t['id']==task_id),None)
        if existing:
            values.update(version=existing['version']+1,updated_at=now())
            self.repo.update('production_job_tasks','id',task_id,values)
            self.repo.db.execute('delete from public.production_task_dependencies where task_id=%s',(task_id,))
        else: self.repo.insert('production_job_tasks',dict(id=task_id,production_order_id=job_id,**values))
        for dep in set(body.dependencies): self.repo.insert('production_task_dependencies',{'task_id':task_id,'depends_on_task_id':dep})
        self.repo.activity(self.actor,'Task updated' if existing else 'Task created',job=job_id,task=task_id,details={'title':body.title})
        self.repo.notify(self.actor,body.assigned_employee_id,'Task assigned: '+body.title,'production_order',job_id)
        return self.detail(job_id)

    def task_action(self, job_id, task_id, body):
        self.access(job_id,True)
        task=self.repo.one('select * from public.production_job_tasks where id=%s and production_order_id=%s',(task_id,job_id))
        require(task,'Task not found.',404); self.check_version(task,body.version)
        own=task['assigned_employee_id']==self.actor['id']
        reviewer=self.actor['id']==task['supervisor_id'] or self.actor['role']=='Factory Manager'
        target=body.status; old=task['status']
        edges={'TODO':{'READY','CANCELLED'},'READY':{'IN_PROGRESS','BLOCKED','CANCELLED'},'IN_PROGRESS':{'BLOCKED','PENDING_REVIEW','COMPLETED'},'BLOCKED':{'READY','CANCELLED'},'PENDING_REVIEW':{'COMPLETED','IN_PROGRESS'},'COMPLETED':set(),'CANCELLED':set()}
        require(target in edges[old],'This task transition is not allowed.')
        require(own or reviewer or self.actor['role'] in PLANNERS,'Only the assigned employee or supervisor can update this task.',403)
        if target in {'IN_PROGRESS','PENDING_REVIEW'} and old!='PENDING_REVIEW': require(own,'Only the assigned employee can record work.',403)
        if target in {'READY','IN_PROGRESS'}:
            incomplete=self.repo.all("select d.depends_on_task_id from public.production_task_dependencies d join public.production_job_tasks p on p.id=d.depends_on_task_id where d.task_id=%s and p.status<>'COMPLETED'",(task_id,))
            exceptions=self.repo.all('select dependency_ids from public.production_dependency_exceptions where task_id=%s and approved_by is not null',(task_id,))
            waived={dep for exception in exceptions for dep in exception['dependency_ids']}
            require(all(d['depends_on_task_id'] in waived for d in incomplete),'Complete prerequisite tasks or obtain an approved dependency exception.')
        values={'status':target,'version':task['version']+1,'updated_at':now()}
        if target=='IN_PROGRESS' and not task['actual_start']: values['actual_start']=now()
        if target in {'COMPLETED','PENDING_REVIEW'}:
            require(body.reason,'Record completion evidence or review comments.',422)
            children=self.repo.one("select id from public.production_job_tasks where parent_task_id=%s and status not in ('COMPLETED','CANCELLED') limit 1",(task_id,))
            require(not children,'Finish the subtasks first.')
            if old=='PENDING_REVIEW':
                require(reviewer and self.actor['role'] in PLANNERS and self.actor['id'] not in {task['assigned_employee_id'],task['completed_by']},'An independent assigned supervisor must approve this work.',403)
                values['approved_by']=self.actor['id']
            else:
                require(own,'Only the task owner can submit completion.',403)
                require(target=='PENDING_REVIEW' or not task['approval_required'],'Submit this task for independent review.')
                require([x.title for x in body.checklist]==[x['title'] for x in task['checklist']],'Complete the original checklist without removing items.',422)
                require(all(x.done for x in body.checklist),'Complete all checklist items.')
                values.update(checklist=[x.model_dump() for x in body.checklist],actual_hours=body.actual_hours,completed_by=self.actor['id'])
            if target=='COMPLETED': values['completed_at']=now()
        if old=='PENDING_REVIEW' and target=='IN_PROGRESS': require(reviewer and body.reason,'An assigned reviewer must record a rework reason.',403)
        if target=='CANCELLED': role(self.actor,PLANNERS); require(body.reason,'Record a cancellation reason.',422)
        self.repo.update('production_job_tasks','id',task_id,values)
        self.repo.activity(self.actor,'Task '+target,job=job_id,task=task_id,details={'from':old,'reason':body.reason})
        self.repo.notify(self.actor,task['supervisor_id'] if target=='PENDING_REVIEW' else task['assigned_employee_id'],'Task '+target+': '+task['title'],'production_order',job_id)
        return self.detail(job_id)

    def blocker(self, job_id, body):
        self.access(job_id,True); self.repo.employee(body.assigned_to)
        if body.task_id: require(self.repo.one('select id from public.production_job_tasks where id=%s and production_order_id=%s',(body.task_id,job_id)),'Task does not belong to this job.',422)
        self.repo.insert('production_job_blockers',dict(id=ident('BLK'),production_order_id=job_id,reported_by=self.actor['id'],**body.model_dump()))
        self.repo.activity(self.actor,'Blocker reported',job=job_id,details=body.model_dump(mode='json'))
        self.repo.notify(self.actor,body.assigned_to,'Blocker: '+body.description,'production_order',job_id)
        supervisor=self.management(self.access(job_id)).get('supervisor_id')
        self.repo.notify(self.actor,supervisor,'Production blocked: '+job_id,'production_order',job_id)
        return self.detail(job_id)

    def resolve(self, job_id, blocker_id, body):
        self.access(job_id,True)
        row=self.repo.one('select * from public.production_job_blockers where id=%s and production_order_id=%s',(blocker_id,job_id))
        require(row,'Blocker not found.',404)
        require(row['assigned_to']==self.actor['id'] or self.actor['role'] in PLANNERS,'Only the blocker owner or supervisor can resolve it.',403)
        require(not row['resolved_at'],'Blocker is already resolved.')
        self.repo.update('production_job_blockers','id',blocker_id,{'resolved_at':now(),'resolution':body.text})
        meta=self.management(self.access(job_id))
        if meta['status']=='Blocked / On Hold' and not self.repo.one('select id from public.production_job_blockers where production_order_id=%s and resolved_at is null',(job_id,)):
            self.repo.update('production_job_management','production_order_id',job_id,{'status':'Ready for Production' if meta.get('approved_by') else 'Backlog','version':meta['version']+1,'updated_at':now()})
        self.repo.activity(self.actor,'Blocker resolved',job=job_id,details={'id':blocker_id,'resolution':body.text})
        self.repo.notify(self.actor,row['reported_by'],'Blocker resolved: '+job_id,'production_order',job_id)
        return self.detail(job_id)

    def exception(self, job_id, task_id, body, exception_id=None):
        self.access(job_id,True)
        task=self.repo.one('select * from public.production_job_tasks where id=%s and production_order_id=%s',(task_id,job_id)); require(task,'Task not found.',404)
        if exception_id:
            role(self.actor,PLANNERS)
            row=self.repo.one('select * from public.production_dependency_exceptions where id=%s and task_id=%s',(exception_id,task_id))
            require(row and not row['approved_by'] and row['requested_by']!=self.actor['id'] and task['assigned_employee_id']!=self.actor['id'],'An independent supervisor must approve this exception.')
            deps=[r['depends_on_task_id'] for r in self.repo.all('select depends_on_task_id from public.production_task_dependencies where task_id=%s',(task_id,))]
            require(set(deps)==set(row['dependency_ids']),'Dependencies changed after this exception was requested. Submit a new exception.')
            self.repo.update('production_dependency_exceptions','id',exception_id,{'approved_by':self.actor['id'],'approved_at':now()})
        else:
            require(task['assigned_employee_id']==self.actor['id'] or self.actor['role'] in PLANNERS,'Task ownership required.',403)
            deps=[r['depends_on_task_id'] for r in self.repo.all('select depends_on_task_id from public.production_task_dependencies where task_id=%s',(task_id,))]
            self.repo.insert('production_dependency_exceptions',dict(id=ident('EX'),task_id=task_id,requested_by=self.actor['id'],reason=body.text,dependency_ids=deps))
        self.repo.activity(self.actor,'Dependency exception approved' if exception_id else 'Dependency exception requested',job=job_id,task=task_id,details={'note':body.text})
        return self.detail(job_id)

    def configure(self, body):
        role(self.actor,{'Factory Manager'}); self.repo.lock()
        require(not body.column_order or set(body.column_order)==set(JOB_COLUMNS) and len(body.column_order)==len(JOB_COLUMNS),'Column order must include every semantic stage once.',422)
        require(set(body.column_labels)<=set(JOB_COLUMNS) and all(0<len(v)<=60 for v in body.column_labels.values()),'Invalid column labels.',422)
        require(set(body.stage_weights)<=set(STAGES) and all(0<v<=100 for v in body.stage_weights.values()),'Stage weights must be positive.',422)
        for stage, roles in body.review_roles.items():
            require(stage in REVIEW_ROLES and roles and set(roles)<=set(REVIEW_ROLES[stage]),'Review roles may be restricted, but cannot bypass separation of duties.',422)
        config=body.model_dump()
        if self.repo.one("select id from public.production_workflow_config where id='main'"):
            self.repo.update('production_workflow_config','id','main',{'config':config,'updated_at':now()})
        else: self.repo.insert('production_workflow_config',{'id':'main','config':config})
        self.repo._config=config
        return self.metadata()

    def analytics(self):
        jobs=self.list(); tasks=self.repo.all('select * from public.production_job_tasks where production_order_id=any(%s)',([j['id'] for j in jobs],))
        conflicts=[]
        for i,a in enumerate(tasks):
            for b in tasks[i+1:]:
                if a['assigned_employee_id'] and a['assigned_employee_id']==b['assigned_employee_id'] and a['status'] not in {'COMPLETED','CANCELLED'} and b['status'] not in {'COMPLETED','CANCELLED'} and a['planned_start'] and a['due_date'] and b['planned_start'] and b['due_date'] and a['planned_start']<=b['due_date'] and b['planned_start']<=a['due_date']:
                    conflicts.append({'employee':a['assigned_employee_id'],'tasks':[a['id'],b['id']]})
        completed_today=sum(j.get('status')=='Completed' and any(h.get('stage')=='Packaging' and h.get('decision')=='Approve' and h.get('at','').startswith(date.today().isoformat()) for h in j.get('history',[])) for j in self.repo.state()['manufacturing'].get('jobs',[]) if j['id'] in {x['id'] for x in jobs})
        return {'active':sum(j['board_status']!='Closed' for j in jobs),'overdue':sum(j['overdue'] for j in jobs),'blocked':sum(j['blockers']>0 for j in jobs),
            'completed_today':completed_today,'pending_review':sum(t['status']=='PENDING_REVIEW' for t in tasks),
            'manufactured':sum(j['progress']['manufactured'] for j in jobs),'quality_holds':sum(j['progress']['rework'] for j in jobs),
            'tasks':tasks,'conflicts':conflicts,'stages':{s:sum(j['current_stage']==s and j['board_status']!='Closed' for j in jobs) for s in STAGES}}

    def manufacture(self, body):
        """Execute existing manufacturing transitions against the canonical ERP state atomically."""
        state=self.repo.lock(); m=state['manufacturing']; actor=self.actor['id']; action=body.action
        def get(collection, reference):
            record=next((r for r in m.get(collection,[]) if r['id']==reference),None)
            require(record,collection+' record not found.',404); return record
        def authorize(roles): role(self.actor,set(roles)|{'Factory Manager'})
        def journal(reference,kind,debit,credit,amount):
            key=reference+':'+kind
            require(not any(c['id']==key for c in m['costs']),'This financial event is already posted.')
            m['costs'].insert(0,dict(id=key,reference=reference,kind=kind,debit=debit,credit=credit,amount=amount,at=now().isoformat()))
        def movement(reference,item,amount,source,target):
            key=f'{reference}:{item}:{source}:{target}'
            require(not any(r['id']==key for r in m['movements']),'Stock movement already posted.')
            m['movements'].insert(0,dict(id=key,reference=reference,item=item,amount=amount,**{'from':source,'to':target},actor=actor,at=now().isoformat()))
        if action=='goods-move':
            authorize({'Warehouse Manager'}); good=get('goods',body.id); destination=get('bins',body.bin)
            require(good['status'] in {'Available','Receiving'} and good.get('qc')=='Pass','Only unallocated quality-released goods can be received.')
            require(body.bin!='QA-HOLD','Choose a sellable warehouse bin.')
            require(sum(g.get('bin')==body.bin and g['status']!='Dispatched' for g in m['goods'])<destination['capacity'],'Warehouse bin is full.')
            movement(ident('MOVE'),good['id'],1,good['bin'],body.bin)
            good.update(bin=body.bin,status='Available'); good.setdefault('history',[]).append({'at':now().isoformat(),'action':'Put away in '+body.bin})
            job_id=good.get('jobId')
        else:
            job=get('jobs',body.id); job_id=job['id']; self.access(job_id); meta=self.ensure(job)
            require(meta['status']!='Closed','Closed jobs cannot be changed.')
            product=job.get('productSnapshot') or meta.get('specification',{}).get('product_snapshot') or get('products',job['productId'])
            route=job.get('route') or product.get('route') or STAGES
            if action=='job-reserve':
                authorize({'Inventory Officer','Production Planner'})
                require(job['status']=='Planned','Materials can only be reserved once.')
                # Use the proposal/order snapshot, never a subsequently edited product BOM.
                snapshot=meta.get('specification',{})
                lines=snapshot.get('bom') or product.get('bom',[])
                require(lines,'A BOM is required before release.')
                matrix=[]
                for line in lines:
                    material=get('materials',line['materialId']); amount=math.ceil(line['amount']*job['quantity'])
                    require(material['onHand']-material['reserved']>=amount,'Insufficient material: '+material['name'])
                    matrix.append({'materialId':material['id'],'amount':amount,'cost':amount*material['cost']})
                job.update(bom=matrix,bomRevision=snapshot.get('revision') or product.get('revision'),productSnapshot=copy.deepcopy(product),status='Ready')
                job['productSnapshot']['quality']=snapshot.get('quality') or product.get('quality','')
                job['route']=snapshot.get('route') or route
                for line in matrix: get('materials',line['materialId'])['reserved']+=line['amount']
            elif action=='job-start':
                authorize({'Manufacturing Operator'})
                require(job['status'] in {'Ready','Paused','Rework'},'Stage is not ready to start.')
                require(actor==job['operator'] or self.actor['role']=='Factory Manager','Only the assigned operator can start production.',403)
                require(meta.get('approved_by'),'Submit the job and obtain independent release approval in Production Jobs first.')
                require(not self.repo.one('select id from public.production_job_blockers where production_order_id=%s and resolved_at is null',(job_id,)),'Resolve production blockers first.')
                require(state.get('attendance',{}).get(job['operator'],{}).get('status') in {'Present','Late'},'The operator must be present in HR attendance.')
                labor=m.get('labor',{}).get(job['operator'],{})
                require(labor.get('approved') and labor.get('expires','')>=date.today().isoformat(),'An approved labor rate and current certification are required.')
                require(get('machines',job['machine'])['status'] not in {'Unavailable','Maintenance'},'The assigned machine is unavailable.')
                if not job.get('materialsPosted'):
                    require(job.get('bom'),'Reserve materials first.')
                    for line in job['bom']:
                        material=get('materials',line['materialId']); amount=line['amount']
                        require(material['onHand']>=amount and material['reserved']>=amount,'Reserved inventory is inconsistent.')
                        material['onHand']-=amount; material['reserved']-=amount; movement(job_id,material['id'],-amount,material['location'],'Production')
                    job['materialCost']=sum(b['cost'] for b in job['bom']);job['materialsPosted']=True
                    journal(job_id,'Production consumption','Work in progress','Raw materials',job['materialCost'])
                job.update(status='Running',started=now().isoformat())
            elif action in {'job-pause','job-complete'}:
                authorize({'Manufacturing Operator'})
                require(job['status']=='Running' and (actor==job['operator'] or self.actor['role']=='Factory Manager'),'Only the assigned operator can record running work.',403)
                if action=='job-pause': job['status']='Paused'
                else:
                    require(body.hours>0 and body.notes,'Record actual hours and completion evidence.',422)
                    job.update(hours=body.hours,notes=body.notes,status='Awaiting approval',completedBy=actor,completedAt=now().isoformat())
            elif action=='job-review':
                authorize({'Supervisor'})
                require(not meta.get('supervisor_id') or meta['supervisor_id']==actor or self.actor['role']=='Factory Manager','Only the assigned supervisor can approve this stage.',403)
                require(job['status']=='Awaiting approval','Stage is not awaiting approval.')
                require(actor not in {job['operator'],job.get('completedBy')},'Operators cannot approve their own work.',403)
                require(body.decision=='Approve' or body.reason,'Record a rework or rejection reason.',422)
                job['history'].append(dict(stage=route[job['stage']],decision=body.decision,actor=actor,at=now().isoformat(),note=body.reason or job.get('notes','')))
                if body.decision=='Approve':
                    labor=round(job['hours']*m.get('labor',{}).get(job['operator'],{}).get('rate',0));job['laborCost']+=labor
                    journal(f"{job_id}:{len(job['history'])}",'Approved labor','Work in progress','Labor clearing',labor)
                    if job['stage']==len(route)-1:
                        require(job.get('qc')=='Pass','Independent quality approval is mandatory before finished goods release.')
                        job['status']='Completed';job['overhead']=product.get('overhead',0)*job['quantity']
                        total=job['materialCost']+job['laborCost']+job['overhead']
                        journal(job_id,'Allocated overhead','Work in progress','Overhead clearing',job['overhead'])
                        journal(job_id,'Finished goods release','Finished goods','Work in progress',total)
                        allocated=0
                        for i in range(job['quantity']):
                            cost=total-allocated if i==job['quantity']-1 else total//job['quantity'];allocated+=cost
                            m['goods'].append(dict(id=ident('FG'),productId=job['productId'],jobId=job_id,status='Receiving',bin='QA-HOLD',cost=cost,bom=job['bomRevision'],qc='Pass',sources=[b['materialId'] for b in job['bom']],history=[{'at':now().isoformat(),'action':'Quality released from production'}]))
                    else:
                        job['stage']+=1;job['status']='Awaiting QC' if route[job['stage']]=='Quality inspection' else 'Ready'
                else: job['status']='Rework' if body.decision=='Rework' else 'Rejected'
            elif action=='qc':
                authorize({'Quality Inspector'})
                require(job['status']=='Awaiting QC','Job is not awaiting independent quality inspection.')
                require(actor!=job['operator'],'An independent inspector must inspect quality.',403)
                require(body.passed is not None and body.notes,'Record the quality result and findings.',422)
                job['history'].append(dict(stage='Quality inspection',decision='Pass' if body.passed else 'Fail',actor=actor,at=now().isoformat(),note=body.notes))
                if body.passed: job.update(stage=job['stage']+1,status='Ready',qc='Pass')
                else: job.update(stage=route.index('Assembly'),status='Rework',qc='Fail')
        self.repo.save_state(state)
        if job_id:
            self.repo.activity(self.actor,action,job=job_id,details={'reference':body.id,'notes':body.notes or body.reason})
            meta=self.management(get('jobs',job_id))
            self.repo.notify(self.actor,meta.get('supervisor_id'),'Manufacturing handoff: '+action,'production_order',job_id)
        return {'saved':True,'job_id':job_id}

    def document(self, body, job=None, proposal=None, task=None):
        if job: self.access(job,True)
        if task: require(self.repo.one('select id from public.production_job_tasks where id=%s and production_order_id=%s',(task,job)),'Task does not belong to this job.',404)
        try: content=base64.b64decode(body.content_base64,validate=True)
        except ValueError: require(False,'Invalid attachment encoding.',422)
        require(len(content)<=5242880,'Maximum file size is 5 MB.',413)
        signatures={'application/pdf':b'%PDF-','image/png':b'\x89PNG\r\n\x1a\n','image/jpeg':b'\xff\xd8\xff','application/step':b'ISO-10303-21;'}
        if body.mime_type=='application/dxf':
            require(b'SECTION' in content[:4096] and b'<script' not in content.lower() and b'<!doctype' not in content.lower(),'Upload an ASCII DXF drawing.',422)
        else: require(content.lstrip().startswith(signatures[body.mime_type]),'File content does not match its selected type.',422)
        column='production_order_id' if job else 'proposal_id'; reference=job or proposal
        count=self.repo.one(f'select count(*) as n from public.production_workflow_documents where {column}=%s',(reference,))['n']
        require(count<30,'Maximum 30 documents per workspace.')
        record=self.repo.insert('production_workflow_documents',dict(id=ident('DOC'),production_order_id=job,proposal_id=proposal,task_id=task,filename=body.filename,mime_type=body.mime_type,content=content,uploaded_by=self.actor['id']))
        self.repo.activity(self.actor,'Document uploaded',job=job,proposal=proposal,task=task,details={'filename':body.filename})
        return {'id':record['id']}
