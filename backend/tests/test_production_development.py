"""Pure policy tests; no database or network needed."""
import unittest
from fastapi import HTTPException
from pydantic import ValidationError
from backend.app.features.production_jobs.policy import STAGES, progress, validate_dependencies, cost_total, REVIEW_ROLES
from backend.app.features.production_jobs.models import TaskInput, JobPlan
from backend.app.features.product_development.models import Costs, ConversionInput

class WorkflowPolicyTests(unittest.TestCase):
    def test_existing_roles_reused(self):
        self.assertEqual(REVIEW_ROLES['Final'],['Factory Manager'])
        self.assertEqual(REVIEW_ROLES['Quality'],['Quality Inspector'])
    def test_dependency_cycle_rejected(self):
        with self.assertRaises(HTTPException): validate_dependencies('a',['b'],[('b','c'),('c','a')])
    def test_dependencies_accept_dag(self):
        validate_dependencies('a',['b'],[('b','c')])
    def test_task_dates_validated(self):
        with self.assertRaises(ValidationError): TaskInput(title='Weld',planned_start='2026-10-18',due_date='2026-10-17')
    def test_dispatch_requires_sales_order(self):
        with self.assertRaises(ValidationError): JobPlan(version=1,dispatch_required=True)
    def test_warehouse_required_for_complete(self):
        order={'quantity':1,'status':'Completed','qc':'Pass','history':[{'stage':s,'decision':'Pass' if s=='Quality inspection' else 'Approve'} for s in STAGES]}
        self.assertLess(progress(order,{},[{'qc':'Pass','status':'Receiving','bin':'QA-HOLD'}],[])['manufacturing'],100)
        self.assertEqual(progress(order,{},[{'qc':'Pass','status':'Available','bin':'FG-1'}],[])['manufacturing'],100)
    def test_quality_required_for_complete(self):
        self.assertFalse(progress({'quantity':1,'status':'Completed','history':[]},{},[{'qc':'Pass','status':'Available','bin':'FG'}],[])['manufactured'])
    def test_tasks_do_not_fake_manufacture(self):
        result=progress({'quantity':10,'status':'Planned'},{},[],[{'status':'COMPLETED'}])
        self.assertEqual(result['tasks'],100);self.assertEqual(result['manufacturing'],0)
    def test_weighted_route_progress(self):
        result=progress({'history':[{'stage':'Bending','decision':'Approve'}],'quantity':1},{'route':['Bending','Welding']},[],[],{'Bending':1,'Welding':3})
        self.assertEqual(result['manufacturing'],24)
    def test_costs_and_credit(self):
        self.assertEqual(cost_total(Costs(material=1000,labor=500,offcut_credit=100).model_dump()),1400)
    def test_negative_cost_rejected(self):
        with self.assertRaises(ValidationError): Costs(material=-1)
    def test_sku_validation(self):
        with self.assertRaises(ValidationError): ConversionInput(version=1,sku='../bad',estimate_id='x')

if __name__=='__main__': unittest.main()
