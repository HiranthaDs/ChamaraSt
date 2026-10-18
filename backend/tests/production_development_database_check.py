"""Transactional integration checks against configured PostgreSQL. ALL fixtures roll back.
Run: python -m backend.tests.production_development_database_check
Also validates a pending migration inside the same rollback-only transaction.
"""
import copy
from pathlib import Path
import unittest
from datetime import date, timedelta
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from fastapi import HTTPException
from backend.app.core.config import settings
from backend.app.features.production_jobs.repository import WorkflowRepository
from backend.app.features.production_jobs.service import JobService
from backend.app.features.production_jobs.policy import STAGES
from backend.app.features.production_jobs.models import JobPlan, Action, TaskInput, TaskEdit, TaskAction, BlockerInput, Note, ManufacturingAction, DocumentInput
from backend.app.features.product_development.repository import ProposalRepository
from backend.app.features.product_development.service import ProposalService
from backend.app.features.product_development.models import ProposalInput, ProposalEdit, ReviewInput, EstimateInput, Costs, PrototypeInput, PrototypeTest, ConversionInput, Specifications

class DatabaseWorkflowTests(unittest.TestCase):
    def setUp(self):
        cls = self
        cls.db=psycopg.connect(settings.database_url,row_factory=dict_row,prepare_threshold=None,connect_timeout=15)
        cls.db.execute('begin')
        try:
            if not cls.db.execute("select to_regclass('public.production_job_tasks') as table_name").fetchone()['table_name']:
                cls.db.execute((Path(__file__).parents[1]/'migrations/20261019_production_development.sql').read_text(),prepare=False)
            if not cls.db.execute("select 1 from information_schema.columns where table_schema='public' and table_name='production_workflow_documents' and column_name='task_id'").fetchone():
                cls.db.execute((Path(__file__).parents[1]/'migrations/20261020_workflow_task_evidence.sql').read_text(),prepare=False)
            repo=WorkflowRepository(cls.db); cls.state=repo.lock(); state=copy.deepcopy(cls.state); m=state['manufacturing']
            cls.roles={'planner':'Production Planner','manager':'Factory Manager','supervisor':'Supervisor','operator':'Manufacturing Operator','quality':'Quality Inspector','warehouse':'Warehouse Manager','finance':'Finance Officer','inventory':'Inventory Officer','sales':'Sales Officer','other':'Manufacturing Operator'}
            for key,role in cls.roles.items():
                state['employees'].append({'id':'WF-TEST-'+key,'name':'Rollback test '+key,'role':role,'status':'Active','department':'Manufacturing','salary':0,'email':key+'@workflow-test.invalid'})
                state['attendance']['WF-TEST-'+key]={'status':'Present'}
            m['materials'].append({'id':'WF-TEST-MAT','name':'Rollback material','unit':'pcs','onHand':100,'reserved':0,'cost':1000,'location':'RAW','reorder':0})
            m['products'].append({'id':'WF-TEST-PROD','name':'Rollback product','bom':[{'materialId':'WF-TEST-MAT','amount':2}],'revision':'A','overhead':100,'price':5000,'quality':'Dimensional check'})
            m['machines'].append({'id':'WF-TEST-MACHINE','name':'Rollback machine','status':'Idle','capacity':8})
            m['bins'].append({'id':'WF-TEST-BIN','name':'Rollback warehouse','capacity':100})
            m['labor']['WF-TEST-operator']={'approved':True,'rate':100,'expires':(date.today()+timedelta(days=30)).isoformat()}
            m['jobs'].append(dict(id='WF-TEST-JOB',productId='WF-TEST-PROD',quantity=2,operator='WF-TEST-operator',machine='WF-TEST-MACHINE',start=date.today().isoformat(),due=(date.today()+timedelta(days=3)).isoformat(),priority='Normal',stage=0,status='Planned',materialsPosted=False,materialCost=0,laborCost=0,overhead=0,hours=0,history=[],createdBy='WF-TEST-planner'))
            repo.save_state(state)
            cls.db.execute('savepoint fixture')
        except Exception:
            cls.db.rollback();cls.db.close();raise
    def tearDown(self):
        if not self.db.closed: self.db.rollback()
        self.db.close()
    def actor(self,key): return {'id':'WF-TEST-'+key,'role':self.roles[key]}
    def jobs(self,key='planner'): return JobService(WorkflowRepository(self.db),self.actor(key))
    def proposals(self,key='planner'): return ProposalService(ProposalRepository(self.db),self.actor(key))
    def proposal(self):
        return self.proposals().save(ProposalInput(title='Test bracket',proposed_product_name='Rollback new bracket',reviewer_id='WF-TEST-supervisor',specifications=Specifications(description='New test design',business_justification='Customer demand',feasibility='FEASIBLE',bom=[{'materialId':'WF-TEST-MAT','amount':1}],quality_criteria='Fitment and dimension tests')))
    def advance_proposal(self,p,target,key='planner'):
        return self.proposals(key).status(p['id'],Action(version=p['version'],status=target))
    def review(self,p,stage,key):
        return self.proposals(key).review(p['id'],ReviewInput(version=p['version'],review_stage=stage,decision='Approved',comments='Independent test approval'))
    def ready_proposal(self):
        p=self.proposal()
        for target in ['Submitted','Under Review','Feasibility Study','Design & Costing']: p=self.advance_proposal(p,target)
        p=self.review(p,'Technical','supervisor');p=self.review(p,'Materials','inventory')
        p=self.proposals('finance').estimate(p['id'],EstimateInput(version=p['version'],name='Option A',costs=Costs(material=1000,labor=500),estimated_selling_price=3000))
        p=self.review(p,'Cost','finance');return self.advance_proposal(p,'Prototype Development')
    def release(self,job_id='WF-TEST-JOB'):
        svc=self.jobs();svc.manufacture(ManufacturingAction(action='job-reserve',id=job_id))
        d=svc.detail(job_id);d=svc.change_status(job_id,Action(version=d['version'],status='Pending Approval'))
        return self.jobs('supervisor').change_status(job_id,Action(version=d['version'],status='Ready for Production'))
    def manufacture(self,job_id='WF-TEST-JOB'):
        self.release(job_id)
        for stage in STAGES:
            if stage=='Quality inspection': self.jobs('quality').manufacture(ManufacturingAction(action='qc',id=job_id,passed=True,notes='Measured within tolerance'));continue
            self.jobs('operator').manufacture(ManufacturingAction(action='job-start',id=job_id))
            self.jobs('operator').manufacture(ManufacturingAction(action='job-complete',id=job_id,hours=1,notes='Completed stage inspection'))
            self.jobs('supervisor').manufacture(ManufacturingAction(action='job-review',id=job_id))
        d=self.jobs().detail(job_id)
        self.assertLess(d['progress']['manufacturing'],100)
        for good in d['goods']: self.jobs('warehouse').manufacture(ManufacturingAction(action='goods-move',id=good['id'],bin='WF-TEST-BIN'))
        return self.jobs().detail(job_id)

    def test_retrieval_and_employee_scope(self):
        self.assertIn('WF-TEST-JOB',[j['id'] for j in self.jobs().list()])
        self.assertNotIn('WF-TEST-JOB',[j['id'] for j in self.jobs('other').list()])
        with self.assertRaises(HTTPException): self.jobs('other').detail('WF-TEST-JOB')
    def test_no_unauthorized_drag_or_quality_bypass(self):
        with self.assertRaises(HTTPException): self.jobs('operator').change_status('WF-TEST-JOB',Action(version=1,status='Closed'))
        with self.assertRaises(HTTPException): self.jobs('manager').change_status('WF-TEST-JOB',Action(version=1,status='Production Completed'))
    def test_task_dependencies_assignment_and_independent_approval(self):
        svc=self.jobs();job='WF-TEST-JOB'
        d=svc.task_save(job,TaskInput(title='Cut',assigned_employee_id='WF-TEST-operator',supervisor_id='WF-TEST-supervisor'))
        first=d['tasks'][0]
        d=svc.task_save(job,TaskInput(title='Weld',assigned_employee_id='WF-TEST-operator',supervisor_id='WF-TEST-supervisor',dependencies=[first['id']]))
        second=d['tasks'][1]
        with self.assertRaises(HTTPException): self.jobs('operator').task_action(job,second['id'],TaskAction(version=1,status='READY'))
        for target in ['READY','IN_PROGRESS','PENDING_REVIEW']:
            d=self.jobs('operator').task_action(job,first['id'],TaskAction(version=first['version'],status=target,reason='Recorded evidence',actual_hours=1)); first=d['tasks'][0]
        with self.assertRaises(HTTPException): self.jobs('operator').task_action(job,first['id'],TaskAction(version=first['version'],status='COMPLETED',reason='Self approve'))
        d=self.jobs('supervisor').task_action(job,first['id'],TaskAction(version=first['version'],status='COMPLETED',reason='Verified evidence'))
        d=self.jobs('operator').task_action(job,second['id'],TaskAction(version=1,status='READY'))
        self.assertEqual(d['tasks'][1]['status'],'READY')
    def test_blocker_notify_resolve(self):
        svc=self.jobs();d=svc.blocker('WF-TEST-JOB',BlockerInput(blocker_type='Material shortage',description='Need material',assigned_to='WF-TEST-inventory'))
        self.assertEqual(d['board_status'],'Blocked / On Hold')
        b=d['blocker_history'][0]
        d=self.jobs('inventory').resolve('WF-TEST-JOB',b['id'],Note(text='Stock received'))
        self.assertEqual(d['blockers'],0)
        self.assertTrue(self.db.execute("select id from public.erp_notifications where recipient_employee_id='WF-TEST-inventory'").fetchone())
    def test_full_manufacture_stock_closure_and_balanced_postings(self):
        d=self.manufacture();self.assertEqual(d['progress']['manufacturing'],100)
        self.jobs('warehouse').reconcile('WF-TEST-JOB',Note(text='All serials and costs reconciled'))
        d=self.jobs('warehouse').detail('WF-TEST-JOB')
        d=self.jobs('warehouse').change_status('WF-TEST-JOB',Action(version=d['version'],status='Closed'))
        self.assertEqual(d['status'],'Closed');self.assertFalse(d['dispatch_required'])
        state=self.jobs().repo.state();m=state['manufacturing']
        mat=next(r for r in m['materials'] if r['id']=='WF-TEST-MAT');self.assertEqual(mat['onHand'],96)
        costs=self.jobs('finance').detail('WF-TEST-JOB')['costs'];self.assertEqual(sum(g['cost'] for g in m['goods'] if g.get('jobId')=='WF-TEST-JOB'),costs['material']+costs['labor']+costs['overhead'])
        with self.assertRaises(HTTPException): self.jobs('operator').manufacture(ManufacturingAction(action='job-start',id='WF-TEST-JOB'))
    def test_financial_data_hidden(self):
        self.assertNotIn('costs',self.jobs('operator').detail('WF-TEST-JOB'))
        self.assertIn('costs',self.jobs('finance').detail('WF-TEST-JOB'))
    def test_snapshot_cannot_mutate_managed_orders(self):
        self.jobs().ensure(self.jobs().access('WF-TEST-JOB'))
        self.db.execute("select set_config('orbit.workflow_write','',true)")
        state=copy.deepcopy(self.jobs().repo.state());next(j for j in state['manufacturing']['jobs'] if j['id']=='WF-TEST-JOB')['status']='Completed'
        self.db.execute('savepoint rejected')
        with self.assertRaises(psycopg.Error): self.db.execute('select public.save_erp_state(%s)',(Jsonb(state),))
        self.db.execute('rollback to savepoint rejected')
    def test_proposal_revision_invalidates_approval(self):
        p=self.proposal();p=self.advance_proposal(p,'Submitted');p=self.review(p,'Technical','supervisor')
        p=self.proposals().save(ProposalEdit(version=p['version'],title=p['title'],proposed_product_name=p['proposed_product_name'],specifications=Specifications(**p['specifications']),change_summary='New dimensions'),p['id'])
        self.assertEqual(p['current_version'],2);self.assertEqual(p['approvals'],{});self.assertEqual(len(p['reviews']),1)
    def test_self_approval_and_rejection(self):
        p=self.proposal();p=self.advance_proposal(p,'Submitted')
        with self.assertRaises(HTTPException): self.review(p,'Technical','planner')
        p=self.proposals('supervisor').review(p['id'],ReviewInput(version=p['version'],review_stage='Technical',decision='Rejected',comments='Insufficient technical evidence'))
        self.assertEqual(p['status'],'Rejected / Archived')
    def test_cost_estimates_do_not_post_finance(self):
        p=self.proposal();before=len(self.jobs().repo.state()['manufacturing']['costs'])
        p=self.proposals('finance').estimate(p['id'],EstimateInput(version=p['version'],name='Option A',costs=Costs(material=1000,labor=500,offcut_credit=100),estimated_selling_price=2000))
        self.assertEqual(p['estimates'][0]['total_cost'],1400);self.assertEqual(p['estimates'][0]['estimated_margin'],30)
        self.assertEqual(before,len(self.jobs().repo.state()['manufacturing']['costs']))
        self.assertEqual(self.proposals('supervisor').detail(p['id'])['estimates'],[])
    def test_prototype_launch_and_duplicate_retry(self):
        p=self.ready_proposal();body=PrototypeInput(version=p['version'],request_id='rollback-prototype-1',quantity=1,operator='WF-TEST-operator',supervisor_id='WF-TEST-supervisor',machine='WF-TEST-MACHINE',start=date.today(),due=date.today()+timedelta(days=3))
        p=self.proposals().prototype(p['id'],body);p=self.proposals().prototype(p['id'],body)
        self.assertEqual(len(p['prototypes']),1);proto=p['prototypes'][0]
        self.manufacture(proto['production_order_id']);p=self.advance_proposal(p,'Prototype Testing')
        p=self.proposals('quality').test(p['id'],proto['id'],PrototypeTest(result='Pass',findings='All dimensional and fitment tests passed'))
        p=self.review(p,'Prototype','supervisor');p=self.review(p,'Quality','quality');p=self.advance_proposal(p,'Awaiting Final Approval');p=self.review(p,'Final','manager')
        p=self.proposals('manager').detail(p['id']);estimate=p['estimates'][0]
        with self.assertRaises(HTTPException):
            self.proposals('manager').convert(p['id'],ConversionInput(version=p['version'],sku='WF-TEST-PROD',estimate_id=estimate['id']))
        body=ConversionInput(version=p['version'],sku='WF-TEST-LAUNCH',estimate_id=estimate['id'])
        p=self.proposals('manager').convert(p['id'],body);p=self.proposals('manager').convert(p['id'],body)
        self.assertEqual(p['status'],'Launched');self.assertEqual(p['product_id'],'WF-TEST-LAUNCH')
        self.assertEqual(sum(x['id']=='WF-TEST-LAUNCH' for x in self.jobs().repo.state()['manufacturing']['products']),1)
    def test_document_content_validation(self):
        import base64
        with self.assertRaises(HTTPException): self.jobs().document(DocumentInput(filename='drawing.pdf',mime_type='application/pdf',content_base64=base64.b64encode(b'<script>bad</script>').decode()),job='WF-TEST-JOB')
    def test_stale_version_conflict(self):
        d=self.jobs().plan('WF-TEST-JOB',JobPlan(version=1,priority='High'))
        self.assertEqual(d['priority'],'High')
        with self.assertRaises(HTTPException): self.jobs().plan('WF-TEST-JOB',JobPlan(version=1,priority='Low'))

    def test_task_evidence_and_exception_scope(self):
        import base64
        svc=self.jobs();job='WF-TEST-JOB'
        d=svc.task_save(job,TaskInput(title='Prerequisite',assigned_employee_id='WF-TEST-operator',supervisor_id='WF-TEST-supervisor'))
        prerequisite=d['tasks'][0]
        d=svc.task_save(job,TaskInput(title='Dependent',assigned_employee_id='WF-TEST-operator',supervisor_id='WF-TEST-supervisor',dependencies=[prerequisite['id']]))
        task=d['tasks'][1]
        d=self.jobs('operator').exception(job,task['id'],Note(text='Approved alternative work sequence needed'))
        exception=d['exceptions'][0]
        with self.assertRaises(HTTPException): self.jobs('operator').exception(job,task['id'],Note(text='Self approval blocked'),exception['id'])
        d=self.jobs('supervisor').exception(job,task['id'],Note(text='Alternative sequence reviewed'),exception['id'])
        d=self.jobs('operator').task_action(job,task['id'],TaskAction(version=1,status='READY'))
        self.assertEqual(d['tasks'][1]['status'],'READY')
        doc=svc.document(DocumentInput(filename='evidence.pdf',mime_type='application/pdf',content_base64=base64.b64encode(b'%PDF-1.4\nTest fixture').decode()),job=job,task=task['id'])
        self.assertEqual(svc.detail(job)['documents'][0]['task_id'],task['id'])
        self.assertTrue(doc['id'])

    def test_schedule_shift_and_overlap(self):
        svc=self.jobs();job='WF-TEST-JOB';start=date.today();due=start+timedelta(days=2)
        for title in ['Task A','Task B']:
            svc.task_save(job,TaskInput(title=title,assigned_employee_id='WF-TEST-operator',supervisor_id='WF-TEST-supervisor',planned_start=start,due_date=due))
        self.assertTrue(svc.analytics()['conflicts'])
        d=svc.plan(job,JobPlan(version=1,planned_start=start+timedelta(days=3),due_date=due+timedelta(days=3)))
        self.assertTrue(all(t['planned_start']==start+timedelta(days=3) for t in d['tasks']))

    def test_engineering_product_snapshot_guard(self):
        state=self.jobs().repo.lock();product=next(p for p in state['manufacturing']['products'] if p['id']=='WF-TEST-PROD')
        product['proposalId']='rollback-source';self.jobs().repo.save_state(state)
        self.db.execute("select set_config('orbit.workflow_write','',true)")
        product['bom'][0]['amount']=99
        self.db.execute('savepoint engineering_guard')
        with self.assertRaises(psycopg.Error): self.db.execute('select public.save_erp_state(%s)',(Jsonb(state),))
        self.db.execute('rollback to savepoint engineering_guard')

if __name__=='__main__': unittest.main(verbosity=2)
