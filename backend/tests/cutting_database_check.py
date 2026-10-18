"""Real PostgreSQL integration. All fixtures, postings and pending DDL roll back."""
import copy
import unittest
from pathlib import Path
from psycopg.types.json import Jsonb
from fastapi import HTTPException
from backend.tests.production_development_database_check import DatabaseWorkflowTests
from backend.tests.test_cutting import inputs, MATERIAL
from backend.app.features.production_jobs.repository import WorkflowRepository
from backend.app.features.manufacturing.cutting_service import CuttingService
from backend.app.features.manufacturing.cutting_models import SavePlan, Placement, PlanAction
from backend.app.features.manufacturing.cutting_engine import optimize


class CuttingDatabaseTests(unittest.TestCase):
    tearDown=DatabaseWorkflowTests.tearDown
    actor=DatabaseWorkflowTests.actor
    jobs=DatabaseWorkflowTests.jobs
    proposals=DatabaseWorkflowTests.proposals
    proposal=DatabaseWorkflowTests.proposal

    def setUp(self):
        DatabaseWorkflowTests.setUp(self)
        try:
            if not self.db.execute("select to_regclass('public.cutting_plan_versions') as t").fetchone()['t']:
                self.db.execute((Path(__file__).parents[1]/'migrations/20261021_cutting_optimization.sql').read_text(encoding='utf-8'),prepare=False)
            repo=WorkflowRepository(self.db);state=repo.lock()
            self.roles['operator']='Cutting Operator'
            next(e for e in state['employees'] if e['id']=='WF-TEST-operator')['role']='Cutting Operator'
            state['manufacturing']['sheets'].append(dict(id='CUT-TEST-SHEET',w=1000,h=500,cost=100000,status='Available',location='RAW',**MATERIAL))
            state['manufacturing']['machines'].append(dict(id='CUT-TEST-LASER',type='Laser',status='Idle',name='Rollback laser'))
            repo.save_state(state)
            self.inp=inputs();self.inp.sheets[0].inventory_id='CUT-TEST-SHEET';self.inp.machine_id='CUT-TEST-LASER';self.inp.production_order_id='WF-TEST-JOB'
        except Exception:
            self.db.rollback();self.db.close();raise

    def svc(self,actor='operator'):return CuttingService(WorkflowRepository(self.db),self.actor(actor))
    def save(self):return self.svc().save(SavePlan(inputs=self.inp,placements=[Placement.model_validate(p) for p in optimize(self.inp)['placements']]))
    def action(self,p,a,actor='operator',**kw):return self.svc(actor).action(p['id'],PlanAction(version=p['version'],action=a,**kw))

    def test_full_job_stock_cost_history(self):
        p=self.save();pid=p['id'];self.assertEqual(self.db.execute('select status from public.physical_sheets where id=%s',('CUT-TEST-SHEET',)).fetchone()['status'],'Available')
        p=self.action(p,'submit');self.assertTrue(p['task_id'])
        p=self.action(p,'approve','supervisor');p=self.action(p,'start');p=self.action(p,'complete',accepted_quantity=3,note='Measured 3 plates')
        p=self.action(p,'verify','supervisor',note='Verified geometry',verified_offcuts=[o['id'] for s in p['layout']['sheets'] for o in s['offcuts']])
        self.assertEqual(self.db.execute('select status from public.physical_sheets where id=%s',('CUT-TEST-SHEET',)).fetchone()['status'],'Used')
        self.assertEqual(self.db.execute('select status from public.production_job_tasks where id=%s',(p['task_id'],)).fetchone()['status'],'COMPLETED')
        self.assertEqual(len(self.svc().versions(pid)),6)
        movements=self.db.execute("select payload from public.stock_movements where payload->>'reference'=%s",(pid,)).fetchall();self.assertGreaterEqual(len(movements),2)
        costs=self.db.execute("select payload from public.manufacturing_cost_events where payload->>'reference'=%s",(pid,)).fetchall();self.assertEqual(sum(r['payload']['amount'] for r in costs),100000)
        with self.assertRaises(HTTPException):self.action(p,'verify','supervisor',note='Replay')
        self.assertEqual(len(self.svc().list(job='WF-TEST-JOB')),1)

    def test_proposal_feasibility_cannot_release(self):
        proposal=self.proposal();self.inp.production_order_id=None;self.inp.proposal_id=proposal['id']
        svc=self.svc('planner');p=svc.save(SavePlan(inputs=self.inp,placements=[Placement.model_validate(p) for p in optimize(self.inp)['placements']]))
        self.assertEqual(len(svc.list(proposal=proposal['id'])),1)
        with self.assertRaises(HTTPException):self.action(p,'submit','planner')

    def test_stale_and_snapshot_tampering(self):
        p=self.save();self.action(p,'submit')
        with self.assertRaises(HTTPException):self.svc().action(p['id'],PlanAction(version=1,action='submit'))
        state=copy.deepcopy(WorkflowRepository(self.db).state());next(c for c in state['manufacturing']['cuts'] if c['id']==p['id'])['status']='Confirmed'
        self.db.execute('savepoint tampering')
        self.db.execute("select set_config('orbit.workflow_write','no',true)")
        try:
            with self.assertRaises(Exception) as caught:self.db.execute('select public.save_erp_state(%s)',(Jsonb(state),))
            self.assertEqual(caught.exception.sqlstate,'42501')
        finally:self.db.execute('rollback to savepoint tampering')

if __name__=='__main__':unittest.main()
