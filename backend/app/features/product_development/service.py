from datetime import date
from backend.app.features.production_jobs.policy import (STAGES, PROPOSAL_COLUMNS, PLANNERS, FINANCE, READERS,
    WORKERS, REVIEW_ROLES, require, role, cost_total)
from backend.app.features.production_jobs.repository import ident
from backend.app.features.production_jobs.service import JobService, now

class ProposalService:
    def __init__(self,repo,actor):
        self.repo,self.actor=repo,actor
        role(actor,READERS)

    def get(self, proposal_id, write=False):
        if write: self.repo.lock()
        row=self.repo.proposal(proposal_id); require(row,'Proposal not found.',404)
        if self.actor['role'] in WORKERS:
            require(row['proposed_by']==self.actor['id'],'You can only view your own proposals.',403)
        return row

    def version(self,row,expected):
        require(row['version']==expected,'Proposal changed. Refresh before saving.')

    def approvals(self,row):
        version=self.repo.current_version(row)
        reviews=self.repo.all('select * from public.product_proposal_reviews where version_id=%s order by created_at,id',(version['id'],))
        return {r['review_stage']:r['decision'] for r in reviews}

    def list(self):
        rows=self.repo.all('select * from public.product_proposals order by updated_at desc')
        result=[]
        for row in rows:
            if self.actor['role'] in WORKERS and row['proposed_by']!=self.actor['id']: continue
            specs=self.repo.current_version(row)['specifications']
            row.update(category=specs.get('category',''),vehicle_compatibility=' '.join(specs.get(k,'') for k in ['vehicle_manufacturer','vehicle_model','model_years']),approvals=self.approvals(row))
            result.append(row)
        return result

    def detail(self,proposal_id):
        row=self.get(proposal_id)
        row['versions']=self.repo.all('select * from public.product_proposal_versions where proposal_id=%s order by version_number desc',(proposal_id,))
        row['specifications']=row['versions'][0]['specifications']
        row['approvals']=self.approvals(row)
        row['reviews']=self.repo.all('select * from public.product_proposal_reviews where proposal_id=%s order by created_at desc',(proposal_id,))
        row['prototypes']=self.repo.all('select p.*,o.payload as production_order from public.product_proposal_prototypes p join public.production_orders o on o.id=p.production_order_id where p.proposal_id=%s order by p.created_at desc',(proposal_id,))
        for proto in row['prototypes']:
            proto['tests']=self.repo.all('select * from public.product_prototype_tests where prototype_id=%s order by created_at desc',(proto['id'],))
            if self.actor['role'] not in FINANCE:
                proto['production_order']={k:v for k,v in proto['production_order'].items() if k not in {'materialCost','laborCost','overhead','bom','productSnapshot'}}
        row['estimates']=self.repo.all('select * from public.product_proposal_cost_estimates where proposal_id=%s order by created_at desc',(proposal_id,)) if self.actor['role'] in FINANCE else []
        for estimate in row['estimates']:
            price=estimate['estimated_selling_price']; estimate['estimated_margin']=round((price-estimate['total_cost'])/price*100,2) if price else None
        row['documents']=self.repo.all('select id,filename,mime_type,uploaded_by,created_at from public.production_workflow_documents where proposal_id=%s',(proposal_id,))
        row['activity']=self.repo.all('select * from public.production_workflow_activity where proposal_id=%s order by created_at desc limit 500',(proposal_id,))
        if self.actor['role'] not in FINANCE: row['activity']=[a for a in row['activity'] if a['action']!='Cost estimate saved']
        return row

    def validate_specs(self,body):
        if body.reviewer_id: require(self.repo.employee(body.reviewer_id)['role'] in PLANNERS,'Select a development coordinator from existing production roles.',422)
        specs=body.specifications
        require(specs.route==STAGES,'Use the existing authorized manufacturing route. Additional machine routes require manufacturing configuration.',422)
        ids=[b.materialId for b in specs.bom]
        require(len(ids)==len(set(ids)),'A material may appear only once in the BOM.',422)
        for mid in ids: require(self.repo.one('select id from public.manufacturing_materials where id=%s',(mid,)),'BOM material not found.',422)
        if specs.comparable_product_id: require(self.repo.one('select id from public.products where id=%s',(specs.comparable_product_id,)),'Comparable product not found.',422)
        if specs.customer_order_id: require(self.repo.one('select id from public.sales_orders where id=%s',(specs.customer_order_id,)),'Customer order not found.',422)

    def save(self,body,proposal_id=None):
        self.repo.lock(); self.validate_specs(body)
        if proposal_id:
            row=self.get(proposal_id); self.version(row,body.version)
            require(row['proposed_by']==self.actor['id'] or self.actor['role'] in PLANNERS,'Only the proposer or development coordinator can revise this proposal.',403)
            number=row['current_version']+1
            # Every edit is a new immutable engineering revision; old approvals stay historical.
            self.repo.update('product_proposals','id',proposal_id,{'title':body.title,'proposed_product_name':body.proposed_product_name,
                'priority':body.priority,'reviewer_id':body.reviewer_id,'current_version':number,'version':row['version']+1,'status':'Ideas','updated_at':now()})
        else:
            proposal_id=ident('NPP'); number=1
            self.repo.insert('product_proposals',dict(id=proposal_id,title=body.title,proposed_product_name=body.proposed_product_name,priority=body.priority,
                reviewer_id=body.reviewer_id,proposed_by=self.actor['id']))
        self.repo.insert('product_proposal_versions',dict(id=ident('REV'),proposal_id=proposal_id,version_number=number,
            specifications=body.specifications.model_dump(mode='json'),change_summary=body.change_summary,effective_date=body.effective_date,created_by=self.actor['id']))
        self.repo.activity(self.actor,'Proposal revision created',proposal=proposal_id,details={'revision':number,'summary':body.change_summary})
        self.repo.notify(self.actor,body.reviewer_id,'New product proposal: '+body.title,'product_proposal',proposal_id)
        return self.detail(proposal_id)

    def status(self,proposal_id,body):
        row=self.get(proposal_id,True); self.version(row,body.version); target=body.status
        require(target in PROPOSAL_COLUMNS,'Unknown proposal stage.',422)
        if target==row['status']: return self.detail(proposal_id)
        require(row['status'] not in {'Launched','Rejected / Archived'},'Create a new revision to reopen this proposal.')
        if body.fast_track:
            role(self.actor,{'Factory Manager'})
            require(target=='Awaiting Final Approval','Fast-track can only move a proposal to final approval.')
            require(row['status'] not in {'Approved for Production','Launched','Rejected / Archived'},'This proposal cannot be fast-tracked from its current stage.')
            require(len(body.reason.strip())>=10,'Explain why this proposal is being fast-tracked (at least 10 characters).',422)
            specs=self.repo.current_version(row)['specifications']
            require(specs['description'].strip() and specs['business_justification'].strip(),
                'Add the product description and business justification before fast-tracking.')
            require(specs['feasibility']=='FEASIBLE','Mark feasibility as FEASIBLE before fast-tracking.')
            require(specs['bom'] and specs['quality_criteria'].strip(),'Add the BOM and quality criteria before fast-tracking.')
            version=self.repo.current_version(row)
            require(self.repo.one('select id from public.product_proposal_cost_estimates where version_id=%s limit 1',(version['id'],)),
                'Add a cost estimate for this revision before fast-tracking.')
            previous=row['status']
            self.repo.update('product_proposals','id',proposal_id,{'status':target,'version':row['version']+1,'updated_at':now()})
            self.repo.activity(self.actor,'Proposal fast-tracked to final approval',proposal=proposal_id,
                details={'from':previous,'to':target,'reason':body.reason.strip(),'revision':version['version_number'],'fast_track':True})
            self.repo.notify(self.actor,row['reviewer_id'],'Proposal fast-tracked to final approval: '+row['title'],'product_proposal',proposal_id)
            return self.detail(proposal_id)
        if target=='Submitted': require(row['status']=='Ideas' and (row['proposed_by']==self.actor['id'] or self.actor['role'] in PLANNERS),'Only a draft can be submitted by its owner.')
        else: role(self.actor,PLANNERS)
        if target=='Rejected / Archived': require(body.reason,'Record an archive reason.',422)
        else:
            require(PROPOSAL_COLUMNS.index(target)==PROPOSAL_COLUMNS.index(row['status'])+1,'Complete the previous proposal stage first.')
            require(target not in {'Approved for Production','Launched'},'Use final review and product conversion for this stage.')
        specs=self.repo.current_version(row)['specifications']; approvals=self.approvals(row)
        if target=='Submitted': require(specs['business_justification'] and specs['description'],'Add a description and business justification before submitting.')
        if target in {'Design & Costing','Prototype Development','Prototype Testing','Awaiting Final Approval'}:
            require(specs['feasibility']=='FEASIBLE','Complete feasibility review and resolve required changes first.')
        if target=='Prototype Development': require(all(approvals.get(k)=='Approved' for k in ['Technical','Materials','Cost']),'Technical, material, and financial approvals are required.')
        if target=='Prototype Testing': require(self.repo.one('select id from public.product_proposal_prototypes where version_id=%s',(self.repo.current_version(row)['id'],)),'Create a prototype manufacturing order first.')
        if target=='Awaiting Final Approval': self.validate_launch_reviews(row,final=False)
        self.repo.update('product_proposals','id',proposal_id,{'status':target,'version':row['version']+1,'updated_at':now()})
        self.repo.activity(self.actor,'Proposal stage changed',proposal=proposal_id,details={'from':row['status'],'to':target,'reason':body.reason})
        self.repo.notify(self.actor,row['reviewer_id'],'Proposal stage: '+target,'product_proposal',proposal_id)
        return self.detail(proposal_id)

    def is_fast_tracked(self,row):
        version=self.repo.current_version(row)
        return self.repo.one("""select id from public.production_workflow_activity
            where proposal_id=%s and action='Proposal fast-tracked to final approval'
              and details->>'revision'=%s order by created_at desc limit 1""",(row['id'],str(version['version_number']))) is not None

    def validate_launch_reviews(self,row,final=True):
        approvals=self.approvals(row)
        version=self.repo.current_version(row)
        specs=version['specifications']
        if self.is_fast_tracked(row):
            require(specs['feasibility']=='FEASIBLE','Feasibility changes must be resolved.')
            require(specs['bom'] and specs['quality_criteria'].strip(),'The fast-tracked revision must have a BOM and quality criteria.')
            require(self.repo.one('select id from public.product_proposal_cost_estimates where version_id=%s limit 1',(version['id'],)),
                'A cost estimate is required for this fast-tracked revision.')
            if final:
                require(approvals.get('Final')=='Approved','Independent final approval is required.')
            return
        required=['Technical','Materials','Cost','Prototype','Quality']+(['Final'] if final else [])
        require(all(approvals.get(s)=='Approved' for s in required),'Current revision requires approved '+', '.join(required)+' reviews.')
        prototypes=self.repo.all('select * from public.product_proposal_prototypes where version_id=%s',(version['id'],))
        passed=False
        for proto in prototypes:
            test=self.repo.one('select result from public.product_prototype_tests where prototype_id=%s order by created_at desc limit 1',(proto['id'],))
            if test and test['result']=='Pass' and JobService(self.repo,self.actor).detail(proto['production_order_id'])['progress']['manufactured']: passed=True
        require(passed,'A manufactured, quality-approved, warehouse-received prototype with a passing test is required.')
        require(version['specifications']['feasibility']=='FEASIBLE','Feasibility changes must be resolved.')

    def review(self,proposal_id,body):
        row=self.get(proposal_id,True); self.version(row,body.version)
        config={**REVIEW_ROLES,**(self.repo.config().get('review_roles') or {})}
        role(self.actor,set(config.get(body.review_stage,REVIEW_ROLES[body.review_stage])))
        require(self.actor['id']!=row['proposed_by'],'The proposer cannot approve their own proposal.',403)
        version=self.repo.current_version(row)
        require(self.actor['id']!=version['created_by'],'The revision author cannot approve their own revision.',403)
        require(row['status'] not in {'Ideas','Launched','Rejected / Archived'},'Submit the current revision for review first.')
        if body.review_stage=='Cost' and body.decision=='Approved':
            require(self.repo.one('select id from public.product_proposal_cost_estimates where version_id=%s',(version['id'],)),'Save a cost estimate for this revision first.')
        if body.review_stage in {'Prototype','Quality'} and body.decision=='Approved':
            passed=self.repo.one("select p.id from public.product_proposal_prototypes p where p.version_id=%s and (select t.result from public.product_prototype_tests t where t.prototype_id=p.id order by t.created_at desc limit 1)='Pass'",(version['id'],))
            require(passed,'Record a passing prototype test for this revision first.')
        if body.review_stage=='Final' and body.decision=='Approved':
            require(row['status']=='Awaiting Final Approval','Submit for final approval first.')
            self.validate_launch_reviews(row,False)
        self.repo.insert('product_proposal_reviews',dict(id=ident('REVIEW'),proposal_id=proposal_id,version_id=version['id'],review_stage=body.review_stage,
            reviewer_id=self.actor['id'],decision=body.decision,comments=body.comments))
        status=row['status']
        if body.decision=='Rejected': status='Rejected / Archived'
        elif body.decision=='Changes requested': status='Ideas'
        elif body.review_stage=='Final': status='Approved for Production'
        self.repo.update('product_proposals','id',proposal_id,{'status':status,'version':row['version']+1,'updated_at':now()})
        self.repo.activity(self.actor,'Proposal review',proposal=proposal_id,details=body.model_dump())
        self.repo.notify(self.actor,row['proposed_by'],body.review_stage+' review: '+body.decision,'product_proposal',proposal_id)
        return self.detail(proposal_id)

    def estimate(self,proposal_id,body):
        role(self.actor,FINANCE); row=self.get(proposal_id,True); self.version(row,body.version)
        require(row['status'] not in {'Launched','Approved for Production','Rejected / Archived'},'Create a revision before changing approved costing.')
        costs=body.costs.model_dump(); total=cost_total(costs)
        require(costs['offcut_credit']<=costs['material']+costs['waste'] and total>=0,'Offcut credit cannot exceed the raw material and waste estimate.',422)
        version=self.repo.current_version(row)
        self.repo.insert('product_proposal_cost_estimates',dict(id=ident('EST'),proposal_id=proposal_id,version_id=version['id'],name=body.name,costs=costs,
            total_cost=total,estimated_selling_price=body.estimated_selling_price,estimated_by=self.actor['id']))
        # A new estimate requires a new cost decision, without erasing previous approval history.
        self.repo.insert('product_proposal_reviews',dict(id=ident('REVIEW'),proposal_id=proposal_id,version_id=version['id'],review_stage='Cost',reviewer_id=self.actor['id'],decision='Changes requested',comments='Cost estimate changed; independent cost review required.'))
        self.repo.update('product_proposals','id',proposal_id,{'version':row['version']+1,'updated_at':now()})
        self.repo.activity(self.actor,'Cost estimate saved',proposal=proposal_id,details={'name':body.name,'total_minor_units':total})
        return self.detail(proposal_id)

    def product_spec(self,row,version,product_id,status,estimate=None):
        specs=version['specifications']; costs=(estimate or {}).get('costs',{})
        return dict(id=product_id,name=row['proposed_product_name'],category=specs['category'],revision=str(version['version_number']),
            price=(estimate or {}).get('estimated_selling_price',0),laborMinutes=0,overhead=costs.get('overhead',0),bom=specs['bom'],route=specs['route'],
            quality=specs['quality_criteria'],status=status,proposalId=row['id'],proposalVersionId=version['id'],effectiveDate=str(version['effective_date'] or date.today()))

    def prototype(self,proposal_id,body):
        role(self.actor,PLANNERS); row=self.get(proposal_id,True)
        prototype_id='PROTO-'+body.request_id
        existing=self.repo.one('select * from public.product_proposal_prototypes where id=%s',(prototype_id,))
        if existing:
            require(existing['proposal_id']==proposal_id,'Request id belongs to a different proposal.'); return self.detail(proposal_id)
        self.version(row,body.version)
        require(row['status'] in {'Prototype Development','Prototype Testing'},'Approve development before creating prototypes.')
        approvals=self.approvals(row); require(all(approvals.get(k)=='Approved' for k in ['Technical','Materials','Cost']),'Current technical, material, and cost approvals required.')
        version=self.repo.current_version(row); specs=version['specifications']
        require(specs['bom'] and specs['quality_criteria'],'Define BOM and quality requirements first.')
        state=self.repo.state(); m=state['manufacturing']
        operator=self.repo.employee(body.operator)
        require(operator['role']=='Manufacturing Operator','Choose a manufacturing operator.',422)
        require(self.repo.employee(body.supervisor_id)['role'] in PLANNERS and body.supervisor_id!=body.operator,'Choose an independent supervisor.',422)
        require(body.due>=body.start,'Due date precedes start.',422)
        machine=next((x for x in m.get('machines',[]) if x['id']==body.machine),None)
        require(machine and machine.get('status') not in {'Unavailable','Maintenance'},'Choose an available machine.',422)
        product_id='DEV-'+version['id']
        if not any(p['id']==product_id for p in m['products']): m['products'].append(self.product_spec(row,version,product_id,'Development'))
        job_id=ident('MO')
        job=dict(id=job_id,productId=product_id,quantity=body.quantity,operator=body.operator,machine=body.machine,start=body.start.isoformat(),due=body.due.isoformat(),
            priority=row['priority'],stage=0,status='Planned',materialsPosted=False,materialCost=0,laborCost=0,overhead=0,hours=0,history=[],createdBy=self.actor['id'],
            proposalId=proposal_id,proposalVersionId=version['id'],prototypeId=prototype_id,route=specs['route'],notes='Prototype '+str(version['version_number']))
        m['jobs'].append(job); self.repo.save_state(state)
        self.repo.insert('product_proposal_prototypes',dict(id=prototype_id,proposal_id=proposal_id,version_id=version['id'],production_order_id=job_id))
        service=JobService(self.repo,self.actor); service.ensure(job)
        self.repo.update('production_job_management','production_order_id',job_id,{'supervisor_id':body.supervisor_id})
        self.repo.update('product_proposals','id',proposal_id,{'version':row['version']+1,'updated_at':now()})
        self.repo.activity(self.actor,'Prototype manufacturing order created',proposal=proposal_id,details={'production_order_id':job_id,'revision':version['version_number']})
        self.repo.notify(self.actor,body.operator,'Prototype assigned: '+job_id,'production_order',job_id)
        return self.detail(proposal_id)

    def test(self,proposal_id,prototype_id,body):
        role(self.actor,{'Quality Inspector'}); row=self.get(proposal_id,True)
        proto=self.repo.one('select * from public.product_proposal_prototypes where id=%s and proposal_id=%s',(prototype_id,proposal_id)); require(proto,'Prototype not found.',404)
        order=JobService(self.repo,self.actor).access(proto['production_order_id'])
        require(self.actor['id']!=order.get('operator'),'An independent inspector must test the prototype.',403)
        if body.result=='Pass': require(JobService(self.repo,self.actor).detail(proto['production_order_id'])['progress']['manufactured'],'Complete manufacture, quality inspection and warehouse receipt before recording a passing test.')
        self.repo.insert('product_prototype_tests',dict(id=ident('TEST'),prototype_id=prototype_id,inspector_id=self.actor['id'],**body.model_dump()))
        self.repo.update('product_proposal_prototypes','id',prototype_id,{'status':body.result})
        if body.result!='Pass':
            for stage in ['Prototype','Quality','Final']:
                self.repo.insert('product_proposal_reviews',dict(id=ident('REVIEW'),proposal_id=proposal_id,version_id=proto['version_id'],review_stage=stage,reviewer_id=self.actor['id'],decision='Changes requested',comments='Prototype test: '+body.findings))
        self.repo.activity(self.actor,'Prototype test recorded',proposal=proposal_id,details={'prototype_id':prototype_id,**body.model_dump()})
        self.repo.notify(self.actor,row['reviewer_id'],'Prototype test: '+body.result,'product_proposal',proposal_id)
        return self.detail(proposal_id)

    def convert(self,proposal_id,body):
        role(self.actor,{'Factory Manager'}); row=self.get(proposal_id,True)
        if row['status']=='Launched': return self.detail(proposal_id)
        self.version(row,body.version); require(row['status']=='Approved for Production','Final approval is required.')
        self.validate_launch_reviews(row)
        version=self.repo.current_version(row)
        require(not version['effective_date'] or version['effective_date']<=date.today(),'The approved revision is not effective yet.')
        estimate=self.repo.one('select * from public.product_proposal_cost_estimates where id=%s and version_id=%s',(body.estimate_id,version['id']))
        require(estimate,'Select an estimate from the approved revision.',422)
        state=self.repo.state(); products=state['manufacturing']['products']
        linked=body.existing_product_id or row.get('product_id')
        duplicate=next((p for p in products if p['id'].casefold()==body.sku.casefold() or (p.get('name','').casefold()==row['proposed_product_name'].casefold() and p.get('status')!='Development')),None)
        if linked:
            product=next((p for p in products if p['id']==linked),None); require(product,'Existing product not found.',404)
            require(not duplicate or duplicate['id']==linked,'This SKU or equivalent name already belongs to a different product.')
            require(product.get('proposalId') in {None,proposal_id},'Product belongs to another development proposal.')
            # Existing released orders retain their own BOM, route and quality snapshot.
            for job in state['manufacturing']['jobs']:
                if job.get('productId')==linked: JobService(self.repo,self.actor).ensure(job)
            product.update(self.product_spec(row,version,linked,'Active',estimate)); product_id=linked
        else:
            require(not duplicate,'Equivalent product already exists. Select it explicitly instead of creating a duplicate.')
            product_id=body.sku; products.append(self.product_spec(row,version,product_id,'Active',estimate))
        released=next(p for p in products if p['id']==product_id)
        geometry_plans=[c for c in state['manufacturing'].get('cuts',[]) if c.get('engine')=='mixed-v1'
            and c.get('inputs',{}).get('proposal_id')==proposal_id and c.get('proposal_version')==row['current_version']
            and c.get('layout',{}).get('valid') and c['layout'].get('feasible')]
        if geometry_plans:
            latest=max(geometry_plans,key=lambda c:c['updated'])
            released['cuttingGeometry']={'plan_id':latest['id'],'parts':latest['inputs']['parts'],'proposal_version':row['current_version']}
        self.repo.save_state(state)
        self.repo.update('product_proposals','id',proposal_id,{'product_id':product_id,'status':'Launched','version':row['version']+1,'updated_at':now()})
        self.repo.activity(self.actor,'Approved product launched',proposal=proposal_id,details={'product_id':product_id,'revision':version['version_number'],'estimate_id':estimate['id']})
        for employee in state.get('employees',[]):
            if employee.get('status')=='Active' and employee.get('role') in {'Production Planner','Inventory Officer','Sales Officer','Finance Officer'}:
                self.repo.notify(self.actor,employee['id'],'Product released: '+row['proposed_product_name'],'product_proposal',proposal_id)
        return self.detail(proposal_id)
