import copy
import math
import unittest
from pydantic import ValidationError
from fastapi import HTTPException
from shapely.geometry import Point,box
from backend.app.features.manufacturing.cutting_models import CuttingInput, Placement, SavePlan, PlanAction
from backend.app.features.manufacturing.cutting_engine import optimize,validate,local,finished_area,collides,stock
from backend.app.features.manufacturing.cutting_service import CuttingService
from backend.app.features.manufacturing.cutting_exports import svg,pdf

MATERIAL=dict(material='Steel',grade='MS',thickness=3)
def inputs(parts=None,**kw):
    return CuttingInput(sheets=[dict(id='sheet',w=1000,h=500,cost=100000,**MATERIAL)],parts=parts or [dict(id='p',name='Plate',shape='rectangle',w=100,h=100,quantity=3,**MATERIAL)],**kw)
def place(**kw):
    return Placement(**(dict(part_id='p',instance=1,sheet_id='sheet',sheet_instance=1,x=12,y=12,rotation=0)|kw))

class GeometryTests(unittest.TestCase):
    def test_dimension_validation(self):
        with self.assertRaises(ValidationError): CuttingInput(sheets=[dict(id='s',w=-1,h=20,**MATERIAL)],parts=[])
    def test_nonfinite(self):
        with self.assertRaises(ValidationError): inputs().parts[0].model_validate(dict(inputs().parts[0].model_dump(),w=float('nan')))
    def test_quantity_limits(self):
        with self.assertRaises(ValidationError): inputs(parts=[dict(id='p',name='p',shape='circle',quantity=151,**MATERIAL)])
    def test_rectangle_and_square(self):
        p=inputs().parts[0];p.w=30;p.h=70
        self.assertEqual(local(p,90)[0].area,2100)
        p.shape='square';self.assertEqual(local(p,0)[0].area,900)
    def test_circle_exact_area(self):
        p=inputs().parts[0];p.shape='circle';p.diameter=200
        self.assertAlmostEqual(finished_area(*local(p,0)[:2]),math.pi*100**2)
    def test_triangle(self):
        p=inputs().parts[0];p.shape='triangle';p.vertices=[(0,0),(100,0),(0,100)]
        self.assertEqual(local(p,0)[0].area,5000)
    def test_concave_polygon(self):
        p=inputs().parts[0];p.shape='polygon';p.vertices=[(0,0),(100,0),(100,30),(30,30),(30,100),(0,100)]
        self.assertEqual(local(p,0)[0].area,5100)
    def test_self_intersection_rejected(self):
        p=inputs().parts[0];p.shape='polygon';p.vertices=[(0,0),(100,100),(0,100),(100,0)]
        with self.assertRaises(ValueError):local(p,0)
    def test_exact_circle_collision(self):
        self.assertTrue(collides(Point(0,0),100,Point(199.999,0),100,0))
        self.assertFalse(collides(Point(0,0),100,Point(200,0),100,0))
    def test_circle_rectangle_corner(self):
        self.assertFalse(collides(Point(120,120),20,box(0,0,100,100),0,0))
        self.assertTrue(collides(Point(110,110),20,box(0,0,100,100),0,0))
    def test_polygon_overlap(self):
        self.assertTrue(collides(box(0,0,100,100),0,box(99,99,200,200),0,0))
    def test_edge_and_kerf(self):
        i=inputs();self.assertFalse(validate(i,[place(x=11.9)])['valid']);self.assertTrue(validate(i,[place()])['valid'])
    def test_gap(self):
        i=inputs();self.assertFalse(validate(i,[place(),place(instance=2,x=117.9)])['valid'])
        self.assertTrue(validate(i,[place(),place(instance=2,x=118)])['valid'])
    def test_material_compatibility(self):
        i=inputs();i.parts[0].grade='SS';r=optimize(i);self.assertEqual(r['placed'],0);self.assertEqual(r['missing'][0]['quantity'],3)
    def test_rotation(self):
        i=inputs();self.assertFalse(validate(i,[place(rotation=45)])['valid']);i.parts[0].grain=True;self.assertFalse(validate(i,[place(rotation=90)])['valid'])
    def test_restricted_zone(self):
        i=inputs();i.constraints.zones=[[(0,0),(200,0),(200,200),(0,200)]];self.assertFalse(validate(i,[place()])['valid'])
    def test_duplicate_placement(self):
        self.assertFalse(validate(inputs(),[place(),place(x=200)])['valid'])
    def test_multi_sheet(self):
        i=inputs();i.parts[0].w=900;i.parts[0].h=400;i.sheets[0].quantity=3
        r=optimize(i);self.assertEqual(len(r['sheets']),3);self.assertTrue(r['feasible'])
    def test_insufficient_stock(self):
        i=inputs();i.parts[0].w=900;i.parts[0].h=400
        self.assertEqual(optimize(i)['missing'][0]['quantity'],2)
    def test_machine_capacity(self):
        i=inputs();i.constraints.machine_w=500
        with self.assertRaises(ValueError):optimize(i)
    def test_irregular_stock_hole(self):
        i=inputs();i.sheets[0].geometry={'type':'Polygon','coordinates':[[[0,0],[1000,0],[1000,500],[0,500],[0,0]],[[200,100],[200,300],[400,300],[400,100],[200,100]]]}
        self.assertFalse(validate(i,[place(x=220,y=120)])['valid'])
        self.assertTrue(validate(i,[place()])['valid'])
    def test_offcut_first(self):
        i=inputs();s=i.sheets[0].model_copy();s.id='off';s.w=450;s.h=450;s.offcut=True;s.cost=999999;i.sheets.append(s)
        self.assertEqual(optimize(i,'offcut-first')['sheets'][0]['sheet_id'],'off')
    def test_accounting(self):
        r=optimize(inputs());t=r['totals'];self.assertAlmostEqual(t['total_area'],sum(t[k] for k in ['part_area','kerf_area','offcut_area','scrap_area']))
        self.assertEqual(t['material_cost'],t['part_cost']+t['offcut_cost']+t['scrap_cost'])
    def test_manual_overlap(self):
        self.assertFalse(validate(inputs(),[place(),place(instance=2,x=50)])['valid'])
    def test_svg_escaping_and_dimensions(self):
        i=inputs();i.parts[0].name='<script>alert(1)</script>';out=svg(optimize(i));self.assertIn('&lt;script&gt;',out);self.assertNotIn('<script>',out);self.assertIn('width="1120.0mm"',out)
    def test_pdf(self):self.assertTrue(pdf(optimize(inputs())).startswith(b'%PDF-'))
    def test_required_scenario_all_modes(self):
        i=inputs(parts=[dict(id='c',name='Circles',shape='circle',diameter=200,quantity=12,**MATERIAL),dict(id='r',name='Rectangles',shape='rectangle',w=300,h=150,quantity=8,**MATERIAL),dict(id='s',name='Squares',shape='square',w=100,quantity=6,**MATERIAL)])
        i.sheets[0].w=2400;i.sheets[0].h=1200
        for mode in ['fast','maximum','offcut-first']:
            r=optimize(i,mode);self.assertTrue(r['valid']);self.assertEqual(r['placed'],26);self.assertEqual(r['missing'],[])
            self.assertAlmostEqual(r['utilization'],100*(12*math.pi*100**2+8*300*150+6*100**2)/(2400*1200))
    def test_determinism(self):self.assertEqual(optimize(inputs())['placements'],optimize(inputs())['placements'])


class MemoryRepo:
    def __init__(self):
        self.data={'manufacturing':{'cuts':[],'sheets':[dict(id='STOCK',w=1000,h=500,cost=100000,status='Available',location='RAW',**MATERIAL)],'machines':[dict(id='LASER',type='Laser',status='Idle')],'products':[],'parts':[],'movements':[],'costs':[],'materials':[]}}
        self.events=[];self.versions=[]
    def state(self):return self.data
    def lock(self):return self.data
    def save_state(self,state):self.data=state
    def insert(self,table,value):self.versions.append(copy.deepcopy(value));return value
    def activity(self,*args,**kwargs):self.events.append(kwargs)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.repo=MemoryRepo();self.operator={'id':'OP','role':'Cutting Operator'};self.supervisor={'id':'SUP','role':'Supervisor'}
        self.svc=CuttingService(self.repo,self.operator);self.review=CuttingService(self.repo,self.supervisor)
        self.inp=inputs();self.inp.sheets[0].inventory_id='STOCK';self.inp.machine_id='LASER'
        self.body=SavePlan(inputs=self.inp,placements=[Placement.model_validate(p) for p in optimize(self.inp)['placements']])
    def save(self):return self.svc.save(self.body)
    def action(self,p,action,svc=None,**kw):return (svc or self.svc).action(p['id'],PlanAction(version=p['version'],action=action,**kw))
    def test_save_no_stock_effect(self):
        p=self.save();self.assertEqual(p['status'],'Draft');self.assertEqual(self.repo.data['manufacturing']['sheets'][0]['status'],'Available');self.assertFalse(self.repo.data['manufacturing']['movements'])
    def test_canonical_inventory(self):
        self.body.inputs.sheets[0].cost=1;p=self.save();self.assertEqual(p['inputs']['sheets'][0]['cost'],100000)
    def test_reject_duplicate_inventory(self):
        s=self.inp.sheets[0].model_copy();s.id='another';self.inp.sheets.append(s)
        with self.assertRaises(HTTPException):self.svc.resolve(self.inp)
    def test_invalid_save(self):
        self.body.placements[1].x=self.body.placements[0].x;self.body.placements[1].y=self.body.placements[0].y
        with self.assertRaises(HTTPException):self.save()
    def test_permissions(self):
        with self.assertRaises(HTTPException):CuttingService(self.repo,{'id':'F','role':'Finance Officer'}).save(self.body)
    def test_stale_save(self):
        p=self.save();self.body.plan_id=p['id'];self.body.version=0
        with self.assertRaises(HTTPException):self.save()
    def test_independent_approval(self):
        p=self.action(self.save(),'submit')
        with self.assertRaises(HTTPException):self.action(p,'approve',CuttingService(self.repo,{'id':'OP','role':'Factory Manager'}))
    def test_manual_sheet_not_released(self):
        self.body.inputs.sheets[0].inventory_id=None;p=self.save()
        with self.assertRaises(HTTPException):self.action(p,'submit')
    def test_full_workflow_once(self):
        p=self.action(self.save(),'submit');self.assertEqual(self.repo.data['manufacturing']['sheets'][0]['status'],'Reserved')
        p=self.action(p,'approve',self.review);self.assertFalse(self.repo.data['manufacturing']['costs'])
        p=self.action(p,'start');p=self.action(p,'complete',accepted_quantity=3,note='All dimensions measured')
        self.assertFalse(self.repo.data['manufacturing']['parts'])
        off=[o['id'] for s in p['layout']['sheets'] for o in s['offcuts']]
        p=self.action(p,'verify',self.review,note='Measurements verified',verified_offcuts=off)
        m=self.repo.data['manufacturing'];self.assertEqual(p['status'],'Confirmed');self.assertEqual(len(m['parts']),3);self.assertEqual(sum(x['amount'] for x in m['costs']),100000)
        with self.assertRaises(HTTPException):self.action(p,'verify',self.review,note='Repeat')
        self.assertEqual(len(self.repo.versions),6)
    def test_no_theoretical_stock(self):
        p=self.action(self.save(),'submit');p=self.action(p,'approve',self.review);p=self.action(p,'start');p=self.action(p,'complete',accepted_quantity=3,note='Done')
        self.action(p,'verify',self.review,note='No reusable offcuts verified');self.assertEqual(len(self.repo.data['manufacturing']['sheets']),1)
    def test_return_releases_reservation(self):
        p=self.action(self.save(),'submit');self.action(p,'return',self.review,note='Revise')
        self.assertEqual(self.repo.data['manufacturing']['sheets'][0]['status'],'Available')

if __name__=='__main__':unittest.main()
