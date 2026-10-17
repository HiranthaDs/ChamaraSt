import assert from 'node:assert/strict';
import { optimize } from '../src/manufacturing/nesting.js';
import { migrate, transition, reconcilePayments, STAGES, seedManufacturing } from '../src/manufacturing/store.js';
import { initialState } from '../src/data.js';

function validateGeometry(sheet,plan){
  const rectangles=[...plan.placed,...plan.reusable,...plan.scrap,...plan.cuts];
  for(let i=0;i<rectangles.length;i++){
    const a=rectangles[i];assert.ok(a.w>0&&a.h>0&&a.x>=0&&a.y>=0&&a.x+a.w<=sheet.w+.0001&&a.y+a.h<=sheet.h+.0001);
    for(let j=i+1;j<rectangles.length;j++){const b=rectangles[j];assert.ok(a.x+a.w<=b.x+.0001||b.x+b.w<=a.x+.0001||a.y+a.h<=b.y+.0001||b.y+b.h<=a.y+.0001,'Rectangles cannot overlap');}
  }
  assert.ok(Math.abs(plan.totalArea-(rectangles.reduce((n,r)=>n+r.w*r.h,0)+plan.trimArea))<.001,'Area must reconcile');
  assert.equal(plan.partCost+plan.offcutCost+plan.lossCost,sheet.cost,'Purchase cost must reconcile exactly');
}
const sheet={w:3000,h:1500,thickness:3,cost:1800000};
for(let i=0;i<60;i++)for(const plan of optimize(sheet,[{w:100+(i*83)%800,h:100+(i*113)%600,qty:1+i%12},{w:210,h:130,qty:i%5+1}],{kerf:i%7,margin:i%20,rotate:i%2===0,grain:i%3===0}))validateGeometry(sheet,plan);
assert.ok(optimize(sheet,[{w:800,h:400,qty:6}])[0].feasible);
assert.ok(!optimize(sheet,[{w:3100,h:400,qty:1}])[0].feasible);
assert.throws(()=>optimize(sheet,[{w:-1,h:4,qty:2}]));
assert.throws(()=>optimize({...sheet,w:4000},[{w:100,h:100,qty:1}]));
const rotatedSheet={w:1000,h:500,thickness:3,cost:50000};
assert.ok(optimize(rotatedSheet,[{w:400,h:800,qty:1}],{rotate:true,margin:0})[0].feasible);
assert.ok(!optimize(rotatedSheet,[{w:400,h:800,qty:1}],{rotate:true,grain:true,margin:0})[0].feasible);

let data=migrate({...structuredClone(initialState),manufacturing:seedManufacturing()});const originalEmployees=JSON.stringify(data.employees);const originalPayroll=JSON.stringify(data.payroll);
const call=(type,p)=>data=transition(data,type,p);
const actor=(role,employeeId)=>call('actor',{role,employeeId});
call('receive-sheets',{count:20,w:3000,h:1500,thickness:3,cost:1800000,material:'Mild steel',grade:'S235',supplier:'Lanka Steel',location:'A-01'});
assert.equal(data.manufacturing.sheets.length,24);assert.equal(new Set(data.manufacturing.sheets.map(s=>s.id)).size,24);
actor('Cutting Operator','EMP-005');
call('cut-save',{sheetId:'SH-26001',requests:[{w:800,h:400,qty:6}],options:{kerf:3,margin:10},layoutId:'layout-0'});
const cut=data.manufacturing.cuts[0];assert.equal(data.manufacturing.sheets.find(s=>s.id==='SH-26001').status,'Available');
call('cut-submit',{id:cut.id});assert.throws(()=>transition(data,'cut-confirm',{id:cut.id,quantity:6}));
actor('Supervisor','EMP-005');assert.throws(()=>transition(data,'cut-approve',{id:cut.id}),/own/);
actor('Supervisor','EMP-002');call('cut-approve',{id:cut.id});actor('Cutting Operator','EMP-005');call('cut-execute',{id:cut.id});call('cut-confirm',{id:cut.id,quantity:6});
assert.equal(data.manufacturing.parts.length,6);assert.equal(data.manufacturing.sheets.find(s=>s.id==='SH-26001').status,'Used');
assert.throws(()=>transition(data,'cut-confirm',{id:cut.id,quantity:6}));
actor('Factory Manager','EMP-008');call('purchase-create',{materialId:'paint',quantity:20000});const pr=data.manufacturing.purchases[0];
assert.throws(()=>transition(data,'purchase-approve',{id:pr.id}),/own/);actor('Supervisor','EMP-002');call('purchase-approve',{id:pr.id});actor('Inventory Officer','EMP-009');call('purchase-receive',{id:pr.id});assert.throws(()=>transition(data,'purchase-receive',{id:pr.id}));
actor('Factory Manager','EMP-008');call('job-create',{productId:'RB-001',quantity:3,operator:'EMP-005',machine:'BEND-01',priority:'Normal',start:'2026-10-16',due:'2026-10-20'});
const jobId=data.manufacturing.jobs[0].id;call('job-reserve',{id:jobId});assert.throws(()=>transition(data,'job-reserve',{id:jobId}));
actor('Manufacturing Operator','EMP-005');call('job-start',{id:jobId});const afterConsumption=data.manufacturing.materials.find(m=>m.id==='paint').onHand;
call('job-pause',{id:jobId});call('job-start',{id:jobId});assert.equal(data.manufacturing.materials.find(m=>m.id==='paint').onHand,afterConsumption);
for(let i=0;i<STAGES.length;i++){
  const job=data.manufacturing.jobs.find(j=>j.id===jobId);
  if(job.status==='Awaiting QC'){actor('Quality Inspector','EMP-011');call('qc',{id:jobId,pass:false,notes:'Coating defect'});assert.equal(data.manufacturing.goods.filter(g=>g.jobId===jobId).length,0);actor('Manufacturing Operator','EMP-005');call('job-start',{id:jobId});call('job-complete',{id:jobId,hours:.5,notes:'Coating corrected and reassembled'});actor('Supervisor','EMP-002');call('job-review',{id:jobId,decision:'Approve'});actor('Quality Inspector','EMP-011');call('qc',{id:jobId,pass:true,notes:'All dimensions verified'});continue;}
  actor('Manufacturing Operator','EMP-005');if(job.status!=='Running')call('job-start',{id:jobId});call('job-complete',{id:jobId,hours:1,notes:'Checked against drawing'});
  actor('Supervisor','EMP-005');assert.throws(()=>transition(data,'job-review',{id:jobId,decision:'Approve'}),/own/);actor('Supervisor','EMP-002');call('job-review',{id:jobId,decision:'Approve'});
}
assert.equal(data.manufacturing.jobs.find(j=>j.id===jobId).status,'Completed');const goods=data.manufacturing.goods.filter(g=>g.jobId===jobId);assert.equal(goods.length,3);
actor('Warehouse Manager','EMP-007');for(const g of goods)call('goods-move',{id:g.id,bin:'WH1-A1'});
call('order-create',{shopId:'SHOP-01',productId:'RB-001',quantity:3,due:'2026-10-22'});const orderId=data.manufacturing.orders[0].id;
for(let i=0;i<4;i++)call('order-advance',{id:orderId});
const dispatched=data.manufacturing.goods.filter(g=>g.status==='Dispatched').length;
actor('Finance Officer','EMP-006');call('invoice-order',{id:orderId});assert.equal(data.manufacturing.goods.filter(g=>g.status==='Dispatched').length,dispatched);assert.throws(()=>transition(data,'invoice-order',{id:orderId}));
const invoice=data.invoices.find(i=>i.manufacturingOrder===orderId);assert.equal(invoice.currency,'LKR');invoice.status='Paid';data=reconcilePayments(data);const postingCount=data.manufacturing.costs.length;data=reconcilePayments(data);assert.equal(data.manufacturing.costs.length,postingCount);
assert.equal(JSON.stringify(data.employees),originalEmployees);assert.equal(JSON.stringify(data.payroll),originalPayroll);assert.equal(new Set(data.manufacturing.costs.map(c=>c.id)).size,data.manufacturing.costs.length);
assert.ok(data.manufacturing.materials.every(m=>m.onHand>=0&&m.reserved>=0&&m.reserved<=m.onHand));
console.log('PASS: 180 geometric layouts, area/cost conservation, grain restriction, cutting gates, self-approval protection, idempotent stock/finance posting, procurement, full production with failed QC and rework, warehouse, dispatch, existing Finance invoice/payment integration, and HR preservation.');
