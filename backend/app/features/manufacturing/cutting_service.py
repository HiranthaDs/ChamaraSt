import copy
import math
from datetime import datetime, timezone
from shapely.geometry import shape, mapping
from shapely.affinity import translate
from backend.app.features.production_jobs.policy import PLANNERS, READERS, WORKERS, require, role
from backend.app.features.production_jobs.repository import ident
from backend.app.features.production_jobs.service import JobService
from backend.app.features.product_development.repository import ProposalRepository
from backend.app.features.product_development.service import ProposalService
from .cutting_models import CuttingInput, Placement
from .cutting_engine import validate

EDITORS=PLANNERS | {'Cutting Operator'}
REVIEWERS={'Supervisor','Factory Manager'}
ENGINE='mixed-v1'


def now(): return datetime.now(timezone.utc).isoformat()


class CuttingService:
    def __init__(self,repo,actor):
        self.repo,self.actor=repo,actor
        role(actor,READERS)

    def access(self,plan):
        inp=plan['inputs']
        if inp.get('production_order_id'): JobService(self.repo,self.actor).access(inp['production_order_id'])
        elif inp.get('proposal_id'): ProposalService(ProposalRepository(self.repo.db),self.actor).get(inp['proposal_id'])
        elif self.actor['role'] in WORKERS: require(plan['createdBy']==self.actor['id'],'This plan belongs to another operator.',403)
        return plan

    def get(self,pid):
        plan=next((c for c in self.repo.state()['manufacturing']['cuts'] if c['id']==pid and c.get('engine')==ENGINE),None)
        require(plan,'Cutting plan not found.',404)
        return self.access(plan)

    def list(self,job=None,proposal=None):
        result=[]
        for p in self.repo.state()['manufacturing']['cuts']:
            if p.get('engine')!=ENGINE: continue
            if job and p['inputs'].get('production_order_id')!=job: continue
            if proposal and p['inputs'].get('proposal_id')!=proposal: continue
            try: self.access(p)
            except Exception as e:
                if getattr(e,'status_code',None)==403: continue
                raise
            result.append(p)
        return result

    def resolve(self,inp,reserved_for=None):
        """Never trust browser dimensions, valuation or offcut flags for inventory."""
        inp=inp.model_copy(deep=True); m=self.repo.state()['manufacturing']; used=set()
        if inp.production_order_id: JobService(self.repo,self.actor).access(inp.production_order_id)
        if inp.proposal_id: ProposalService(ProposalRepository(self.repo.db),self.actor).get(inp.proposal_id)
        if inp.machine_id:
            machine=next((x for x in m['machines'] if x['id']==inp.machine_id),None)
            require(machine and machine.get('status') not in {'Unavailable','Maintenance'},'Selected machine is unavailable.',422)
            require(any(w in machine.get('type','').lower() for w in ['laser','cutter','cutting']),'Select a cutting machine.',422)
            for field in ['machine_w','machine_h','machine_thickness']:
                if machine.get(field): setattr(inp.constraints,field,min(getattr(inp.constraints,field),float(machine[field])))
        for p in inp.parts:
            if p.product_id: require(any(x['id']==p.product_id for x in m['products']),'Linked product does not exist.',422)
        for s in inp.sheets:
            if not s.inventory_id: continue
            require(s.inventory_id not in used,'A physical sheet cannot appear twice.',422);used.add(s.inventory_id)
            row=next((x for x in m['sheets'] if x['id']==s.inventory_id),None)
            require(row and (row['status']=='Available' or (reserved_for and row.get('reservedFor')==reserved_for and row['status']=='Reserved')),'Inventory sheet is no longer available.',409)
            for key in ['w','h','material','grade','thickness','cost']: setattr(s,key,row[key])
            s.quantity=1;s.offcut=bool(row.get('parent'));s.geometry=row.get('geometry')
        return inp

    def save(self,body):
        role(self.actor,EDITORS); state=self.repo.lock(); m=state['manufacturing']
        old=self.get(body.plan_id) if body.plan_id else None
        if old:
            require(old['version']==body.version,'Plan changed; reload before saving.')
            require(old['status'] in {'Draft','Returned'},'Only drafts or returned plans can be edited.')
        inp=self.resolve(body.inputs); result=validate(inp,body.placements,body.mode)
        require(result['valid'],'Invalid manual placement: '+str(result['errors']),422)
        require(result['placed']>0,'Place at least one part before saving.',422)
        original=validate(inp,body.optimized_placements,body.mode) if body.optimized_placements else result
        require(original['valid'],'Original comparison layout is invalid.',422)
        pid=old['id'] if old else ident('CUT')
        plan={'id':pid,'engine':ENGINE,'inputs':inp.model_dump(),'layout':result,'sheetId':result['sheets'][0]['sheet']['inventory_id'],
              'status':'Draft','version':old['version']+1 if old else 1,'createdBy':old['createdBy'] if old else self.actor['id'],
              'created':old['created'] if old else now(),'updated':now(),'original_layout':original}
        if inp.proposal_id:
            proposal=self.repo.one('select current_version from public.product_proposals where id=%s',(inp.proposal_id,))
            plan['proposal_version']=proposal['current_version']
        if old and old.get('task_id'): plan['task_id']=old['task_id']
        if old: m['cuts'][m['cuts'].index(old)]=plan
        else: m['cuts'].insert(0,plan)
        self.persist(plan,'Layout saved')
        return plan

    def persist(self,plan,event):
        self.sync_task(plan)
        self.repo.save_state(self.repo.state())
        self.repo.insert('cutting_plan_versions',{'cutting_plan_id':plan['id'],'version_number':plan['version'],
            'production_order_id':plan['inputs'].get('production_order_id'),'proposal_id':plan['inputs'].get('proposal_id'),
            'changed_by':self.actor['id'],'event':event,'snapshot':copy.deepcopy(plan)})
        job=plan['inputs'].get('production_order_id')
        proposal=plan['inputs'].get('proposal_id')
        # Workflow activity requires either a production order or proposal link.
        # Standalone plans are already audited in cutting_plan_versions.
        if job or proposal:
            self.repo.activity(self.actor,event,job=job,proposal=proposal,details={'cutting_plan_id':plan['id'],'version':plan['version'],'status':plan['status']})

    def sync_task(self,plan):
        job=plan['inputs'].get('production_order_id')
        if not job: return
        states={'Draft':'TODO','Returned':'TODO','Review':'PENDING_REVIEW','Approved':'READY','Cutting':'IN_PROGRESS','Executed':'PENDING_REVIEW','Confirmed':'COMPLETED'}
        if not plan.get('task_id'):
            if plan['status']!='Review': return
            task=self.repo.insert('production_job_tasks',{'id':ident('TASK'),'production_order_id':job,
                'title':'Sheet cutting · '+plan['id'],'description':'Validated cutting plan '+plan['id']+'. Completion is verified through Cutting Studio.',
                'assigned_employee_id':plan['createdBy'],'approval_required':True,'status':'PENDING_REVIEW'})
            plan['task_id']=task['id']
        task=self.repo.one('select * from public.production_job_tasks where id=%s',(plan['task_id'],))
        fields={'status':states[plan['status']],'version':task['version']+1,'updated_at':now()}
        if plan.get('approvedBy'):fields['supervisor_id']=plan['approvedBy']
        if plan.get('executedBy'):fields['assigned_employee_id']=plan['executedBy']
        if plan['status']=='Cutting':fields['actual_start']=plan['started_at']
        if plan['status']=='Confirmed':fields.update(completed_at=plan['verified_at'],completed_by=plan['executedBy'],approved_by=plan['verifiedBy'])
        self.repo.update('production_job_tasks','id',plan['task_id'],fields)

    def action(self,pid,body):
        state=self.repo.lock(); plan=self.get(pid);m=state['manufacturing']
        require(plan['version']==body.version,'Plan changed; refresh before acting.')
        action=body.action
        rules={'submit':(EDITORS,{'Draft'}),'approve':(REVIEWERS,{'Review'}),'return':(REVIEWERS,{'Review','Approved'}),
               'start':({'Cutting Operator','Factory Manager'},{'Approved'}),'complete':({'Cutting Operator','Factory Manager'},{'Cutting'}),
               'verify':(REVIEWERS,{'Executed'})}
        roles,states=rules[action];role(self.actor,roles);require(plan['status'] in states,'Invalid cutting workflow transition.')
        inp=CuttingInput.model_validate(plan['inputs'])
        if action=='start' and not inp.machine_id:
            cutters=[machine for machine in m['machines']
                     if any(word in machine.get('type','').lower() for word in ['laser','cutter','cutting'])]
            require(cutters,'No cutting machine is registered. Register a cutter in Manufacturing → Production → Factory floor before starting this plan.')
            available_status=[]
            for machine in cutters:
                status=str(machine.get('status') or '').strip().lower()
                if status in {'running','busy','maintenance','unavailable','offline'}: continue
                available_status.append(machine)
            require(available_status,'No cutting machine is marked available. In the machine register, mark a physically idle cutter as Idle.')
            available=[]
            for machine in available_status:
                c=inp.constraints
                if any(sheet.w>min(c.machine_w,float(machine.get('machine_w') or c.machine_w))
                       or sheet.h>min(c.machine_h,float(machine.get('machine_h') or c.machine_h))
                       or sheet.thickness>min(c.machine_thickness,float(machine.get('machine_thickness') or c.machine_thickness))
                       for sheet in inp.sheets): continue
                available.append(machine)
            if not available:
                required_w=max(sheet.w for sheet in inp.sheets);required_h=max(sheet.h for sheet in inp.sheets)
                required_t=max(sheet.thickness for sheet in inp.sheets)
                capacities=', '.join(f"{machine.get('name') or machine['id']}: {machine.get('machine_w') or inp.constraints.machine_w:g} × {machine.get('machine_h') or inp.constraints.machine_h:g} mm, {machine.get('machine_thickness') or inp.constraints.machine_thickness:g} mm thick" for machine in available_status)
                require(False,f'Plan needs a cutter for {required_w:g} × {required_h:g} mm sheets, {required_t:g} mm thick. Available cutter capacities: {capacities}.')
            inp.machine_id=available[0]['id']
        if action in {'submit','approve','start'}:
            inp=self.resolve(inp,pid)
            result=validate(inp,[Placement.model_validate(p) for p in plan['layout']['placements']],plan['layout']['mode'])
            require(result['valid'] and result['feasible'],'Every required part must have a valid placement before release.')
            require(not inp.proposal_id,'Feasibility layouts cannot be released for production.')
            require(all(s['sheet']['inventory_id'] for s in result['sheets']),'Planning sheets must be replaced with actual inventory before release.')
            if action=='submit':
                # Refresh the saved snapshot from current inventory/machine data and
                # keep the existing placements only when they remain feasible.
                plan['inputs']=inp.model_dump(mode='json')
                plan['layout']=result
                original=plan.get('original_layout',{}).get('placements',[])
                comparison=validate(inp,[Placement.model_validate(p) for p in original],plan['layout']['mode']) if original else result
                plan['original_layout']=comparison if comparison['valid'] else result
            elif action=='approve':
                require(inp.model_dump(mode='json')==plan['inputs'],'Inventory or machine specifications changed after submission. Return the plan for revision before continuing.')
            elif action=='start':
                machine=next(x for x in m['machines'] if x['id']==inp.machine_id)
                require(str(machine.get('status') or '').strip().lower() not in {'running','busy','maintenance','unavailable','offline'},'The selected cutting machine is not available. Free it or choose another machine.')
                plan['inputs']=inp.model_dump(mode='json')
                plan['layout']=result
        stock_ids={s['sheet']['inventory_id'] for s in plan['layout']['sheets']}
        sheets=[s for s in m['sheets'] if s['id'] in stock_ids]
        if action=='submit':
            for s in sheets:
                require(s['status']=='Available','Another plan reserved this sheet.');s.update(status='Reserved',reservedFor=pid)
            plan.update(status='Review',submittedBy=self.actor['id'])
        elif action=='approve':
            require(self.actor['id']!=plan.get('submittedBy') and self.actor['id']!=plan['createdBy'],'An independent supervisor must approve.')
            plan.update(status='Approved',approvedBy=self.actor['id'],approved_at=now())
        elif action=='return':
            require(body.note.strip(),'Record the reason for returning the plan.',422)
            for s in sheets:
                require(s.get('reservedFor')==pid,'Sheet reservation changed.');s.update(status='Available',reservedFor=None)
            plan.update(status='Returned',return_note=body.note)
        elif action=='start':
            require(inp.machine_id,'Select an available cutting machine before execution.')
            plan.update(status='Cutting',executedBy=self.actor['id'],started_at=now())
        elif action=='complete':
            require(body.accepted_quantity==plan['layout']['placed'],'Record the full accepted count. Quantity discrepancies require supervisor reconciliation before posting.')
            require(body.note.strip(),'Record actual cutting completion and inspection evidence.',422)
            plan.update(status='Executed',completed_at=now(),actual_quantity=body.accepted_quantity,completion_note=body.note)
        elif action=='verify':
            require(self.actor['id']!=plan.get('executedBy'),'Cutting completion needs independent verification.')
            require(body.note.strip(),'Record verification evidence and measured offcut confirmation.',422)
            self.post(plan,body.verified_offcuts)
            plan.update(status='Confirmed',verifiedBy=self.actor['id'],verified_at=now(),verification_note=body.note)
        plan['version']+=1;plan['updated']=now();self.persist(plan,'Cutting '+action)
        return plan

    def post(self,plan,verified):
        """Single locked transaction; uses existing stock, components and cost events."""
        m=self.repo.state()['manufacturing'];pid=plan['id']
        require(not any(x.get('reference')==pid for x in m['movements']),'This cutting plan was already posted.')
        all_offcuts={o['id'] for s in plan['layout']['sheets'] for o in s['offcuts']}
        require(len(set(verified))==len(verified) and set(verified)<=all_offcuts,'Unknown or duplicate verified offcut.',422)
        total_parts_cost=0
        for layout in plan['layout']['sheets']:
            sheet=next(s for s in m['sheets'] if s['id']==layout['sheet']['inventory_id'])
            require(sheet['status']=='Reserved' and sheet.get('reservedFor')==pid,'Sheet is no longer reserved for this plan.')
            sheet.update(status='Used',reservedFor=None,cuttingPlanId=pid)
            def movement(material,quantity,source,destination):
                m['movements'].append({'id':ident('MOV'),'reference':pid,'item':material,'amount':quantity,'from':source,'to':destination,'at':now(),'actor':self.actor['id']})
            movement(sheet['id'],-1,sheet.get('location',''),'Cutting')
            allocated=0
            for i,p in enumerate(layout['placements']):
                cost=layout['part_cost']-allocated if i==len(layout['placements'])-1 else math.floor(layout['part_cost']*p['area']/layout['part_area']);allocated+=cost
                m['parts'].append({**p,'id':ident('PART'),'parent':sheet['id'],'cutId':pid,'cost':cost,'status':'Available'})
            off_value=0
            for o in layout['offcuts']:
                if o['id'] not in verified: continue
                g=shape(o['geometry']);x,y,right,bottom=g.bounds;cost=math.floor(sheet['cost']*g.area/layout['total_area']);off_value+=cost
                off={**sheet,'id':ident('OFF'),'w':right-x,'h':bottom-y,'geometry':mapping(translate(g,-x,-y)),
                     'parent':sheet['id'],'batch':pid,'cost':cost,'status':'Available','location':'OFF-01','received':now()[:10],'reservedFor':None,'verifiedBy':self.actor['id']}
                m['sheets'].append(off);movement(off['id'],1,'Cutting','OFF-01')
            for kind,debit,amount in [('Parts allocation','Cut components',layout['part_cost']),('Reusable offcuts','Offcut inventory',off_value),('Unrecoverable loss','Scrap loss',sheet['cost']-layout['part_cost']-off_value)]:
                m['costs'].append({'id':ident('COST'),'reference':pid,'kind':kind,'debit':debit,'credit':'Raw materials','amount':amount,'at':now()})
            total_parts_cost+=layout['part_cost']
        mat=next((x for x in m['materials'] if x['id']=='steel-parts'),None)
        if not mat:
            mat={'id':'steel-parts','name':'Steel cut components','grade':'Mixed / serialized','unit':'pcs','onHand':0,'reserved':0,'cost':0,'safety':0,'reorder':0,'daily':0,'lead':0,'moq':1,'location':'CUT','supplier':'Internal cutting','history':[]};m['materials'].append(mat)
        count=plan['layout']['placed']; value=mat['onHand']*mat['cost']+total_parts_cost;mat['onHand']+=count;mat['cost']=round(value/mat['onHand'])
        m['movements'].append({'id':ident('MOV'),'reference':pid,'item':mat['id'],'amount':count,'from':'Cutting','to':'A-01','at':now(),'actor':self.actor['id']})
        plan['verified_offcuts']=verified

    def versions(self,pid):
        self.get(pid)
        return self.repo.all('select version_number,event,changed_by,created_at,snapshot from public.cutting_plan_versions where cutting_plan_id=%s order by version_number desc',(pid,))
