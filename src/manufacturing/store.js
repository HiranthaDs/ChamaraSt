import { optimize } from './nesting.js';

export const STAGES = ['Bending', 'Welding', 'Grinding', 'Painting', 'Assembly', 'Quality inspection', 'Packaging'];
export const ROLES = ['Factory Manager', 'Production Planner', 'Cutting Operator', 'Manufacturing Operator', 'Supervisor', 'Quality Inspector', 'Inventory Officer', 'Warehouse Manager', 'Procurement Officer', 'Sales Officer', 'Finance Officer', 'HR Manager'];
export const ROLE_HOME = {
  'Factory Manager':'factory', 'Production Planner':'production', 'Cutting Operator':'cutting',
  'Manufacturing Operator':'production', 'Supervisor':'quality', 'Quality Inspector':'quality',
  'Inventory Officer':'materials', 'Warehouse Manager':'warehouse', 'Procurement Officer':'materials',
  'Sales Officer':'distribution', 'Finance Officer':'manufacturing-reports', 'HR Manager':'production',
};
export const ROLE_PAGES = {
  'Factory Manager':['factory','materials','cutting','production','quality','warehouse','distribution','manufacturing-reports'],
  'Production Planner':['factory','production','materials','cutting'],
  'Cutting Operator':['factory','cutting'],
  'Manufacturing Operator':['factory','production'],
  'Supervisor':['factory','quality','cutting','production','materials'],
  'Quality Inspector':['factory','quality'],
  'Inventory Officer':['factory','materials','cutting','production'],
  'Warehouse Manager':['factory','warehouse','distribution'],
  'Procurement Officer':['factory','materials'],
  'Sales Officer':['factory','distribution'],
  'Finance Officer':['factory','manufacturing-reports','distribution'],
  'HR Manager':['factory','production'],
};
// New workflow workspaces validate the selected HR identity on the server.
Object.values(ROLE_PAGES).forEach(pages => pages.push('production-jobs', 'product-proposals'));
export const roleEmployee = { 'Factory Manager':'EMP-008', 'Production Planner':'EMP-008', 'Cutting Operator':'EMP-005', 'Manufacturing Operator':'EMP-005', Supervisor:'EMP-002', 'Quality Inspector':'EMP-011', 'Inventory Officer':'EMP-009', 'Warehouse Manager':'EMP-007', 'Procurement Officer':'EMP-006', 'Sales Officer':'EMP-010', 'Finance Officer':'EMP-006', 'HR Manager':'EMP-003' };
export const lkr = (cents, compact = false) => new Intl.NumberFormat('en-LK', { style:'currency', currency:'LKR', maximumFractionDigits:compact?1:2, minimumFractionDigits:compact?0:2, ...(compact?{notation:'compact'}:{}) }).format(cents/100);
export const qty = (material, amount) => `${material.unit === 'ml' ? (amount/1000).toLocaleString() : amount.toLocaleString()} ${material.unit === 'ml' ? 'L' : material.unit}`;
export const uid = prefix => `${prefix}-${crypto.randomUUID().slice(0,8).toUpperCase()}`;
const now = () => new Date().toISOString();
const check = (condition, message) => { if (!condition) throw Error(message); };
const positive = (n, max = 10000000) => Number.isFinite(n) && n>0 && n<=max;
const whole = n => Number.isSafeInteger(n) && n>=0;

export function seedManufacturing() {
  const materials = [
    {id:'steel-parts',name:'Steel cut components',grade:'MS / S235',unit:'pcs',onHand:24,reserved:0,safety:20,reorder:30,daily:6,lead:3,moq:10,cost:145000,location:'A-01',supplier:'Lanka Steel',history:[4,8,6,4,8,6,6]},
    {id:'paint',name:'Red automotive paint',grade:'RAL 3000',unit:'ml',onHand:8000,reserved:0,safety:10000,reorder:20000,daily:2000,lead:5,moq:20000,cost:180,location:'C-02',supplier:'ColourTech',history:[1700,2100,1800,2400,1900,2100,2000]},
    {id:'primer',name:'Anti-corrosion primer',grade:'Epoxy 2K',unit:'ml',onHand:20000,reserved:0,safety:5000,reorder:10000,daily:1000,lead:3,moq:10000,cost:120,location:'C-01',supplier:'ColourTech',history:[800,1100,900,1200,1000,1100,900]},
    {id:'fasteners',name:'M10 fastener kit',grade:'Grade 8.8',unit:'pcs',onHand:800,reserved:0,safety:100,reorder:200,daily:50,lead:2,moq:100,cost:4500,location:'B-01',supplier:'AutoFix Lanka',history:[36,60,48,72,48,36,50]},
    {id:'abrasive',name:'Polishing paper',grade:'P180',unit:'pcs',onHand:200,reserved:0,safety:30,reorder:60,daily:12,lead:2,moq:50,cost:18000,location:'B-02',supplier:'AutoFix Lanka',history:[8,16,10,14,12,12,12]},
  ];
  return {
    version:1, actor:{role:'Factory Manager',employeeId:'EMP-008'},
    sheets:[{id:'SH-26001',w:3000,h:1500,thickness:3,material:'Mild steel',grade:'S235',cost:1800000,status:'Available',supplier:'Lanka Steel',batch:'LOT-2609',location:'A-01',received:'2026-10-01',parent:null},{id:'SH-26002',w:2500,h:1250,thickness:3,material:'Mild steel',grade:'S235',cost:1320000,status:'Available',supplier:'Lanka Steel',batch:'LOT-2609',location:'A-02',received:'2026-10-01',parent:null},{id:'SH-26003',w:3000,h:1500,thickness:5,material:'Stainless steel',grade:'304',cost:4200000,status:'Available',supplier:'Ceylon Metals',batch:'LOT-2610',location:'A-03',received:'2026-10-05',parent:null},{id:'OFF-25001',w:1200,h:600,thickness:3,material:'Mild steel',grade:'S235',cost:288000,status:'Available',supplier:'Recovered material',batch:'CUT-25001',location:'OFF-01',received:'2026-09-10',parent:'SH-25001'}],
    materials, cuts:[], parts:[],
    products:[{id:'RB-001',name:'Rear Buffer',revision:'B',category:'Buffers',price:1250000,laborMinutes:100,overhead:120000,bom:[{materialId:'steel-parts',amount:2},{materialId:'fasteners',amount:12},{materialId:'primer',amount:350},{materialId:'paint',amount:500},{materialId:'abrasive',amount:2}],quality:'Overall width 800 ± 2 mm; coating uniform; all welds inspected.'},{id:'FB-002',name:'Front Buffer',revision:'A',category:'Buffers',price:1490000,laborMinutes:120,overhead:145000,bom:[{materialId:'steel-parts',amount:3},{materialId:'fasteners',amount:12},{materialId:'primer',amount:400},{materialId:'paint',amount:600},{materialId:'abrasive',amount:2}],quality:'Overall width 900 ± 2 mm; coating and weld inspection.'},{id:'BR-003',name:'Mounting Bracket',revision:'C',category:'Brackets',price:320000,laborMinutes:35,overhead:35000,bom:[{materialId:'steel-parts',amount:1},{materialId:'fasteners',amount:4},{materialId:'primer',amount:100},{materialId:'paint',amount:150}],quality:'Hole alignment and overall dimensions verified.'}],
    jobs:[{id:'PR-101',productId:'RB-001',quantity:3,stage:1,status:'Awaiting approval',operator:'EMP-005',machine:'WELD-01',priority:'High',due:'2026-10-17',start:'2026-10-15',materialsPosted:true,materialCost:1350000,laborCost:0,overhead:0,hours:1.5,history:[],notes:'Weld seams completed; ready for visual inspection.',createdBy:'EMP-008'},{id:'PR-102',productId:'RB-001',quantity:44,stage:0,status:'Planned',operator:'EMP-009',machine:'BEND-01',priority:'Normal',due:'2026-10-22',start:'2026-10-18',materialsPosted:false,materialCost:0,laborCost:0,overhead:0,hours:0,history:[],notes:'Shop replenishment batch. Review paint and steel availability.',createdBy:'EMP-008'}],
    machines:[{id:'LASER-01',name:'Sheet cutting',type:'Laser cutter',status:'Idle',capacity:8,service:'2026-10-25',operator:'EMP-005',downtime:0},{id:'BEND-01',name:'CNC bending',type:'Press brake',status:'Running',capacity:8,service:'2026-11-01',operator:'EMP-009',downtime:20},{id:'WELD-01',name:'Welding cell',type:'MIG welder',status:'Running',capacity:8,service:'2026-10-23',operator:'EMP-005',downtime:10},{id:'PAINT-01',name:'Paint booth',type:'Spray booth',status:'Maintenance',capacity:6,service:'2026-10-16',operator:'EMP-010',downtime:120}],
    labor:Object.fromEntries(Object.values(roleEmployee).map(id=>[id,{rate:50000,shift:'Day · 08:00–17:00',certification:'General fabrication',expires:'2027-06-30',approved:true}])),
    purchases:[], maintenance:[], goods:Array.from({length:8},(_,i)=>({id:`FG-RB-${String(i+1).padStart(4,'0')}`,productId:'RB-001',jobId:'PR-OPENING',status:'Available',bin:i<5?'WH1-A1':'WH2-B1',cost:620000,bom:'B',sources:['SH-25001'],qc:'Pass',history:[{at:'2026-10-14',action:'Opening inspected stock'}]})),
    bins:[{id:'WH1-A1',name:'Warehouse 01 · Aisle A / Rack 1',capacity:30},{id:'WH1-A2',name:'Warehouse 01 · Aisle A / Rack 2',capacity:20},{id:'WH2-B1',name:'Warehouse 02 · Aisle B / Rack 1',capacity:15},{id:'QA-HOLD',name:'Quality hold / receiving',capacity:20}],
    shops:[{id:'SHOP-01',name:'Colombo Auto Parts',location:'Colombo',minimum:8,driver:'Nuwan Fernando'},{id:'SHOP-04',name:'Kandy Motor Works',location:'Kandy',minimum:6,driver:'Kasun Perera'}],
    orders:[{id:'SO-201',shopId:'SHOP-01',productId:'RB-001',quantity:4,status:'Requested',serials:[],due:'2026-10-18'},{id:'SO-204',shopId:'SHOP-04',productId:'RB-001',quantity:5,status:'Requested',serials:[],due:'2026-10-20'}],
    movements:[], costs:[{id:'OPENING-WIP',reference:'PR-101',kind:'Opening work in progress',debit:'Work in progress',credit:'Opening balances',amount:1350000,at:'2026-10-15T08:00:00.000Z'}], alerts:{}, audit:[{id:'AUD-OPEN',at:'2026-10-15T08:00:00.000Z',actor:'Demo setup',action:'Manufacturing workspace initialized',reference:'Opening stock'}],savedViews:{},preferences:{email:false,sms:false,whatsapp:false},demoStep:0
  };
}
export function emptyManufacturing() {
  return {
    version: 1, actor: { role: 'Factory Manager', employeeId: '' }, preferences: {}, demoStep: null,
    sheets: [], materials: [], cuts: [], parts: [], products: [], jobs: [], machines: [], labor: {},
    purchases: [], maintenance: [], goods: [], bins: [], shops: [], orders: [], movements: [],
    costs: [], alerts: {}, audit: [], savedViews: {},
  };
}
export function migrate(data) {
  const base=emptyManufacturing(), saved=data.manufacturing||{};
  const manufacturing={...base,...saved,actor:{...base.actor,...(saved.actor||{})}};
  for(const key of ['sheets','materials','cuts','parts','products','jobs','machines','purchases','maintenance','goods','bins','shops','orders','movements','costs','audit']) if(!Array.isArray(manufacturing[key]))manufacturing[key]=[];
  for(const key of ['labor','alerts','savedViews','preferences']) if(!manufacturing[key]||typeof manufacturing[key]!=='object')manufacturing[key]={};
  return {...data,manufacturing};
}
export function demand(m, productId, count) { const product=m.products.find(p=>p.id===productId); if(!product?.bom)return []; return product.bom.map(line=>{const material=m.materials.find(x=>x.id===line.materialId);if(!material)return {material:{id:line.materialId,name:line.materialId,unit:'pcs',reserved:0},required:Math.ceil(line.amount*count),available:0,shortage:Math.ceil(line.amount*count)};const required=Math.ceil(line.amount*count);return {material,required,available:material.onHand-material.reserved,shortage:Math.max(0,required-(material.onHand-material.reserved))};}); }
export function alerts(m) {
  const result=[];
  for(const mat of m.materials){
    const available=mat.onHand-mat.reserved;
    const required=m.jobs.filter(j=>!j.materialsPosted&&!['Completed','Cancelled'].includes(j.status)).reduce((n,j)=>n+(m.products.find(p=>p.id===j.productId)?.bom.find(b=>b.materialId===mat.id)?.amount||0)*j.quantity,0);
    const days=mat.daily>0?Math.floor(available/mat.daily):null;
    if(available<required||available<=mat.reorder)result.push({id:`STOCK-${mat.id}`,priority:available<required?'Critical':'Warning',title:mat.name,detail:`${qty(mat,available)} available · ${qty(mat,required)} scheduled demand${required>available?` · ${qty(mat,required-available)} short`:''}`,materialId:mat.id,days,confidence:'Illustrative forecast',suggested:Math.ceil(Math.max(required-available+mat.safety,mat.daily*mat.lead+mat.safety-available,mat.moq)/mat.moq)*mat.moq,page:'materials'});
  }
  m.jobs.filter(j=>j.status==='Awaiting approval').forEach(j=>result.push({id:`APP-${j.id}`,priority:'Warning',title:`${j.id} awaits approval`,detail:`${STAGES[j.stage]} · ${j.quantity} units · supervisor review required`,page:'quality'}));
  m.machines.filter(x=>['Maintenance','Unavailable'].includes(x.status)).forEach(x=>result.push({id:`MACHINE-${x.id}`,priority:'Warning',title:`${x.name} needs attention`,detail:`${x.status} · next service ${x.service}`,page:'production'}));
  return result.filter(a=>!m.alerts[a.id]?.resolved&&(!m.alerts[a.id]?.snoozedUntil||Date.parse(m.alerts[a.id].snoozedUntil)<Date.now()));
}
function allow(m, roles) { check(m.actor.role==='Factory Manager'||roles.includes(m.actor.role),'Switch to an authorized demo role to perform this action.'); }
function journal(m, reference, kind, debit, credit, amount) { check(whole(amount),'Invalid monetary posting.');const id=`${reference}:${kind}`;check(!m.costs.some(x=>x.id===id),'This financial event is already posted.');m.costs.unshift({id,reference,kind,debit,credit,amount,at:now()}); }
function movement(m, reference, item, amount, from, to) { const id=`${reference}:${item}:${from}:${to}`;check(!m.movements.some(x=>x.id===id),'Stock movement already posted.');m.movements.unshift({id,reference,item,amount,from,to,actor:m.actor.employeeId,at:now()}); }

export function transition(original, action, p={}) {
  const data=structuredClone(migrate(original)),m=data.manufacturing;
  const actor=m.actor.employeeId; let reference=p.id||action;
  if(action==='actor'){check(ROLES.includes(p.role)&&data.employees.some(e=>e.id===p.employeeId&&e.status!=='Inactive'),'Choose a valid demo role and employee.');m.actor=p;return data;}
  const employee=data.employees.find(e=>e.id===actor);
  check(employee&&employee.status!=='Inactive','Select an active employee from the existing HR directory.');
  const present=id=>data.employees.some(e=>e.id===id&&e.status==='Active')&&['Present','Late'].includes(data.attendance[id]?.status);
  const get=(collection,id)=>{const r=m[collection].find(x=>x.id===id);check(r,`${collection} record was not found.`);return r;};
  if(action==='machine-create'){
    allow(m,['Supervisor']);check(p.id?.trim()&&p.name?.trim()&&p.type?.trim(),'Enter a machine code, name, and type.');const machineId=p.id.trim().toUpperCase();check(!m.machines.some(x=>x.id===machineId),'That machine code already exists.');check(positive(p.capacity,24),'Enter available hours per shift.');m.machines.push({id:machineId,name:p.name.trim(),type:p.type.trim(),status:'Idle',capacity:p.capacity,service:p.service||'',operator:'',downtime:0});reference=p.id.trim().toUpperCase();
  } else if(action==='receive-sheets'){
    allow(m,['Inventory Officer']);check(positive(p.count,100)&&Number.isInteger(p.count),'Receive 1 to 100 physical sheets at a time.');check([p.w,p.h,p.thickness].every(n=>positive(n,20000))&&whole(p.cost),'Dimensions and purchase price must be valid.');
    const batch=uid('LOT');reference=batch;
    for(let i=0;i<p.count;i++){const sheet={...p,id:uid('SH'),batch,status:'Available',received:now().slice(0,10),parent:null};delete sheet.count;m.sheets.push(sheet);movement(m,batch,sheet.id,1,'Supplier',p.location);}
    journal(m,batch,'Raw material receipt','Raw materials','Accounts payable',p.count*p.cost);
  } else if(action==='sheet-status'){
    allow(m,['Inventory Officer','Supervisor']);const s=get('sheets',p.id);check(['Available','Quarantined','Scrap'].includes(s.status),'Reserved or used sheets cannot be adjusted.');check(['Available','Quarantined','Scrap'].includes(p.status)&&p.reason?.trim(),'A valid disposition and reason are required.');s.status=p.status;s.note=p.reason;
  } else if(action==='sheet-delete'){
    allow(m,['Inventory Officer','Factory Manager']);const s=get('sheets',p.id);check(s.status==='Available','Only available sheets can be deleted. Reserved, used, quarantined, and scrapped sheets must remain traceable.');check(!m.cuts.some(c=>c.sheetId===s.id),'This sheet is linked to a cutting record and cannot be deleted.');m.sheets=m.sheets.filter(x=>x.id!==s.id);
  } else if(action==='sheets-delete'){
    allow(m,['Inventory Officer','Factory Manager']);check(Array.isArray(p.ids)&&p.ids.length>0&&new Set(p.ids).size===p.ids.length,'Select at least one sheet to delete.');const selected=p.ids.map(id=>get('sheets',id));check(selected.every(s=>s.status==='Available'&&!m.cuts.some(c=>c.sheetId===s.id)),'Only available sheets with no cutting history can be deleted.');m.sheets=m.sheets.filter(s=>!p.ids.includes(s.id));
  } else if(action==='material-delete'){
    allow(m,['Inventory Officer','Factory Manager']);const mat=get('materials',p.id);check(mat.onHand===0&&mat.reserved===0,'Material must have zero on-hand and reserved stock before it can be deleted.');check(!m.products.some(product=>product.bom?.some(line=>line.materialId===mat.id))&&!m.jobs.some(job=>job.bom?.some(line=>line.materialId===mat.id)),'This material is referenced by a product or production order and cannot be deleted.');check(!m.purchases.some(purchase=>purchase.materialId===mat.id),'This material has purchase history and cannot be deleted.');m.materials=m.materials.filter(x=>x.id!==mat.id);
  } else if(action==='purchase-create'){
    allow(m,['Procurement Officer','Inventory Officer']);const mat=get('materials',p.materialId);check(positive(p.quantity)&&Number.isInteger(p.quantity),'Enter a positive quantity in the inventory base unit.');const pr={...p,id:uid('PRQ'),status:'Pending',requester:actor,cost:mat.cost*p.quantity,supplier:mat.supplier,created:now()};m.purchases.unshift(pr);reference=pr.id;
  } else if(action==='purchase-approve'){
    allow(m,['Supervisor','Finance Officer']);const pr=get('purchases',p.id);check(pr.status==='Pending','Only pending requests can be approved.');check(pr.requester!==actor,'The requester cannot approve their own purchase.');pr.status='Approved';pr.approvedBy=actor;
  } else if(action==='purchase-receive'){
    allow(m,['Inventory Officer']);const pr=get('purchases',p.id);check(pr.status==='Approved','Purchase approval is required before receiving.');const mat=get('materials',pr.materialId);mat.onHand+=pr.quantity;pr.status='Received';movement(m,pr.id,mat.id,pr.quantity,'Supplier',mat.location);journal(m,pr.id,'Consumable receipt','Raw materials','Accounts payable',pr.cost);
  } else if(action==='cut-save'){
    allow(m,['Cutting Operator','Production Planner']);const sheet=get('sheets',p.sheetId);check(sheet.status==='Available','The selected sheet is no longer available.');const options=optimize(sheet,p.requests,p.options);const layout=options.find(x=>x.id===p.layoutId)||options[0];check(layout.feasible,'All requested parts must fit before saving a plan.');const cut={id:uid('CUT'),sheetId:sheet.id,requests:p.requests,options:p.options,layout,status:'Draft',createdBy:actor,created:now()};m.cuts.unshift(cut);reference=cut.id;
  } else if(action==='cut-submit'){
    allow(m,['Cutting Operator']);const cut=get('cuts',p.id),sheet=get('sheets',cut.sheetId);check(cut.status==='Draft'&&sheet.status==='Available','Only a draft with an available source can be submitted.');cut.status='Review';cut.submittedBy=actor;sheet.status='Reserved';sheet.reservedFor=cut.id;
  } else if(action==='cut-approve'){
    allow(m,['Supervisor']);const cut=get('cuts',p.id);check(cut.status==='Review','Only submitted plans can be approved.');check(cut.submittedBy!==actor,'You cannot approve your own cutting plan.');cut.status='Approved';cut.approvedBy=actor;
  } else if(action==='cut-return'){
    allow(m,['Supervisor']);const cut=get('cuts',p.id);check(cut.status==='Review'&&cut.submittedBy!==actor,'An independent supervisor can return a submitted plan.');check(p.reason?.trim(),'A revision reason is required.');const sheet=get('sheets',cut.sheetId);cut.status='Returned';cut.reason=p.reason;sheet.status='Available';sheet.reservedFor=null;
  } else if(action==='cut-execute'){
    allow(m,['Cutting Operator']);const cut=get('cuts',p.id);check(cut.status==='Approved','A supervisor must approve this plan first.');check(present(actor),'The executing employee must be present in HR attendance.');const cutters=m.machines.filter(x=>/laser|cutter|cutting/i.test(x.type));check(cutters.length,'Register a cutting machine on the factory floor before executing this cut.');const cutter=cutters.find(x=>!['Unavailable','Maintenance'].includes(x.status));check(cutter,'All registered cutting machines are unavailable.');cut.machineId=cutter.id;cut.status='Executed';cut.executedBy=actor;
  } else if(action==='cut-confirm'){
    allow(m,['Cutting Operator','Inventory Officer']);const cut=get('cuts',p.id),sheet=get('sheets',cut.sheetId);check(cut.status==='Executed'&&sheet.status==='Reserved'&&sheet.reservedFor===cut.id,'Execute this reserved plan before confirming actual results.');check(p.quantity===cut.layout.placed.length,'Actual accepted quantity must match the plan; discrepancies need a revised plan.');cut.status='Confirmed';sheet.status='Used';
    const layout=cut.layout;let allocated=0;
    layout.placed.forEach((part,i)=>{const cost=i===layout.placed.length-1?layout.partCost-allocated:Math.floor(layout.partCost*(part.w*part.h)/layout.partArea);allocated+=cost;m.parts.push({...part,id:uid('PART'),parent:sheet.id,cutId:cut.id,cost,status:'Available'});});
    let remnantAllocated=0;layout.reusable.forEach((r,i)=>{const cost=i===layout.reusable.length-1?layout.offcutCost-remnantAllocated:Math.floor(layout.offcutCost*r.w*r.h/layout.offcutArea);remnantAllocated+=cost;m.sheets.push({...sheet,...r,id:uid('OFF'),cost,parent:sheet.id,batch:cut.id,status:'Available',location:'OFF-01',received:now().slice(0,10),reservedFor:null});});
    let mat=m.materials.find(x=>x.id==='steel-parts');if(!mat){mat={id:'steel-parts',name:'Steel cut components',grade:`${sheet.material} / ${sheet.grade}`,unit:'pcs',onHand:0,reserved:0,safety:0,reorder:0,daily:0,lead:0,moq:1,cost:0,location:'CUT',supplier:'Internal cutting',history:[]};m.materials.push(mat);}const totalValue=mat.onHand*mat.cost+layout.partCost;mat.onHand+=layout.placed.length;mat.cost=Math.round(totalValue/mat.onHand);
    movement(m,cut.id,sheet.id,-1,sheet.location,'Cutting');movement(m,cut.id,'steel-parts',layout.placed.length,'Cutting','A-01');
    journal(m,cut.id,'Parts allocation','Cut components','Raw materials',layout.partCost);journal(m,cut.id,'Reusable offcuts','Offcut inventory','Raw materials',layout.offcutCost);journal(m,cut.id,'Unrecoverable loss','Scrap loss','Raw materials',layout.lossCost);journal(m,cut.id,'Cutting overhead','Manufacturing expense','Overhead clearing',layout.cuttingCost);
  } else if(action==='product-update'){
    allow(m,['Supervisor']);const prod=get('products',p.id);check(p.bom.every(x=>positive(x.amount)&&m.materials.some(mat=>mat.id===x.materialId)),'BOM quantities must be positive.');prod.bom=p.bom;prod.revision=`${prod.revision.split('.')[0]}.${(Number(prod.revision.split('.')[1])||0)+1}`;
  } else if(action==='job-create'){
    allow(m,['Production Planner']);const selectedProduct=get('products',p.productId);check(selectedProduct.status!=='Development','Development products require an approved proposal prototype order.');check(Number.isInteger(p.quantity)&&positive(p.quantity,500),'Choose between 1 and 500 products.');check(present(p.operator),'The assigned operator must be active and present in HR.');const machine=get('machines',p.machine);check(!['Maintenance','Unavailable'].includes(machine.status),'Unavailable machines cannot be assigned.');check(p.due>=p.start,'Due date cannot precede the start date.');const job={...p,id:uid('MO'),stage:0,status:'Planned',materialsPosted:false,materialCost:0,laborCost:0,overhead:0,hours:0,history:[],createdBy:actor};m.jobs.unshift(job);reference=job.id;
  } else if(action==='job-reserve'){
    allow(m,['Inventory Officer','Production Planner']);const j=get('jobs',p.id);check(j.status==='Planned','Materials can only be reserved once for planned work.');const matrix=demand(m,j.productId,j.quantity);check(matrix.every(x=>x.shortage===0),'Insufficient materials. Receive the shortage before reserving.');j.bom=matrix.map(x=>({materialId:x.material.id,amount:x.required,cost:x.required*x.material.cost}));j.bomRevision=get('products',j.productId).revision;j.productSnapshot=structuredClone(get('products',j.productId));j.bom.forEach(x=>get('materials',x.materialId).reserved+=x.amount);j.status='Ready';
  } else if(action==='job-start'){
    allow(m,['Manufacturing Operator']);const j=get('jobs',p.id);check(['Ready','Paused','Rework'].includes(j.status),'This stage is not ready to start.');check(actor===j.operator||m.actor.role==='Factory Manager','Only the assigned operator can start this stage.');check(present(j.operator),'Operator is absent or on leave in HR.');check(m.labor[j.operator]?.approved&&m.labor[j.operator].expires>='2026-10-15','An approved labor rate and valid certification are required.');check(!['Maintenance','Unavailable'].includes(get('machines',j.machine).status),'Assigned machine is unavailable.');
    if(!j.materialsPosted){check(j.bom,'Reserve materials first.');j.bom.forEach(x=>{const mat=get('materials',x.materialId);check(mat.onHand>=x.amount&&mat.reserved>=x.amount,'Reserved inventory is inconsistent.');mat.onHand-=x.amount;mat.reserved-=x.amount;movement(m,j.id,mat.id,-x.amount,mat.location,'Production');});j.materialCost=j.bom.reduce((n,x)=>n+x.cost,0);j.materialsPosted=true;journal(m,j.id,'Production consumption','Work in progress','Raw materials',j.materialCost);}
    j.status='Running';j.started=now();
  } else if(action==='job-pause'){
    allow(m,['Manufacturing Operator']);const j=get('jobs',p.id);check(j.status==='Running'&&(actor===j.operator||m.actor.role==='Factory Manager'),'Only the current operator can pause a running task.');j.status='Paused';
  } else if(action==='job-complete'){
    allow(m,['Manufacturing Operator']);const j=get('jobs',p.id);check(j.status==='Running'&&(actor===j.operator||m.actor.role==='Factory Manager'),'Only the current operator can complete a running task.');check(positive(p.hours,24)&&p.notes?.trim(),'Record actual hours and completion evidence.');j.hours=p.hours;j.notes=p.notes;j.status='Awaiting approval';j.completedBy=actor;j.completedAt=now();
  } else if(action==='job-review'){
    allow(m,['Supervisor']);const j=get('jobs',p.id);check(j.status==='Awaiting approval','This stage is not awaiting review.');check(actor!==j.operator&&actor!==j.completedBy,'Operators cannot approve their own work.');check(['Approve','Rework','Reject'].includes(p.decision),'Choose a review decision.');check(p.decision==='Approve'||p.reason?.trim(),'A reason is mandatory for rejection or rework.');j.history.push({stage:STAGES[j.stage],decision:p.decision,actor,at:now(),note:p.reason||j.notes});
    if(p.decision==='Approve'){const labor=Math.round(j.hours*(m.labor[j.operator]?.rate||0));j.laborCost+=labor;journal(m,`${j.id}:${j.history.length}`,'Approved labor','Work in progress','Labor clearing',labor);if(j.stage===STAGES.length-1){j.status='Completed';j.overhead=(j.productSnapshot?.overhead??get('products',j.productId).overhead)*j.quantity;const total=j.materialCost+j.laborCost+j.overhead;journal(m,j.id,'Allocated overhead','Work in progress','Overhead clearing',j.overhead);journal(m,j.id,'Finished goods release','Finished goods','Work in progress',total);let assigned=0;for(let i=0;i<j.quantity;i++){const cost=i===j.quantity-1?total-assigned:Math.floor(total/j.quantity);assigned+=cost;m.goods.push({id:uid('FG'),productId:j.productId,jobId:j.id,status:'Receiving',bin:'QA-HOLD',cost,bom:j.bomRevision||'B',qc:'Pass',sources:j.bom?.map(x=>x.materialId)||['Opening WIP'],history:[{at:now(),action:'Quality released from production'}]});}}else {j.stage++;j.status=STAGES[j.stage]==='Quality inspection'?'Awaiting QC':'Ready';}}
    else j.status=p.decision==='Rework'?'Rework':'Rejected';
  } else if(action==='qc'){
    allow(m,['Quality Inspector']);const j=get('jobs',p.id);check(j.status==='Awaiting QC','This job is not awaiting final quality inspection.');check(actor!==j.operator,'An independent inspector must release quality.');check(p.notes?.trim(),'Record dimensional findings or defects.');check(typeof p.pass==='boolean','Choose a quality result.');j.history.push({stage:'Quality inspection',decision:p.pass?'Pass':'Fail',actor,at:now(),note:p.notes});if(p.pass){j.stage++;j.status='Ready';j.qc='Pass';}else{j.status='Rework';j.stage=4;j.qc='Fail';}
  } else if(action==='goods-move'){
    allow(m,['Warehouse Manager']);const good=get('goods',p.id),bin=get('bins',p.bin);check(['Available','Receiving'].includes(good.status)&&good.qc==='Pass','Only unallocated, quality-released goods can be moved.');check(bin.id!=='QA-HOLD','Choose a sellable warehouse bin.');check(m.goods.filter(g=>g.bin===bin.id&&g.status!=='Dispatched').length<bin.capacity,'The destination bin is full.');movement(m,uid('MOVE'),good.id,1,good.bin,bin.id);good.bin=bin.id;good.status='Available';good.history.push({at:now(),action:`Put away in ${bin.id}`});
  } else if(action==='order-create'){
    allow(m,['Sales Officer','Warehouse Manager']);get('shops',p.shopId);get('products',p.productId);check(Number.isInteger(p.quantity)&&positive(p.quantity,500),'Order quantity must be 1 to 500.');const order={...p,id:uid('SO'),status:'Requested',serials:[]};m.orders.unshift(order);reference=order.id;
  } else if(action==='order-advance'){
    allow(m,['Warehouse Manager']);const o=get('orders',p.id);const states=['Requested','Allocated','Picked','Packed','Dispatched','Delivered'];const index=states.indexOf(o.status);check(index>=0&&index<states.length-1,'This order is already complete.');
    if(o.status==='Requested'){const available=m.goods.filter(g=>g.productId===o.productId&&g.status==='Available'&&g.qc==='Pass');check(available.length>=o.quantity,`Only ${available.length} quality-released units are available. Produce or transfer additional stock.`);o.serials=available.slice(0,o.quantity).map(g=>g.id);o.serials.forEach(id=>{const g=get('goods',id);g.status='Allocated';g.orderId=o.id;});}
    if(o.status==='Packed'){o.serials.forEach(id=>{const g=get('goods',id);check(g.status==='Allocated'&&g.orderId===o.id,'Allocated stock has changed.');g.status='Dispatched';movement(m,o.id,g.id,-1,g.bin,'Customer');g.history.push({at:now(),action:`Dispatched to ${get('shops',o.shopId).name}`});});journal(m,o.id,'Cost of goods sold','Cost of goods sold','Finished goods',o.serials.reduce((n,id)=>n+get('goods',id).cost,0));}
    if(o.status==='Dispatched'){check(p.proof?.trim(),'Enter proof of delivery to complete this shipment.');o.proof=p.proof;}o.status=states[index+1];
  } else if(action==='invoice-order'){
    allow(m,['Finance Officer']);const o=get('orders',p.id);check(['Dispatched','Delivered'].includes(o.status),'Dispatch goods before invoicing.');check(!o.invoiceId,'This order already has an invoice.');const product=get('products',o.productId),shop=get('shops',o.shopId);const amount=product.price*o.quantity;const id=uid('INV-MFG');data.invoices.unshift({id,client:shop.name,email:'accounts@example.com',description:`${o.quantity} × ${product.name} · ${o.id}`,amount:amount/100,currency:'LKR',issued:'2026-10-15',due:o.due,status:'Pending',manufacturingOrder:o.id});o.invoiceId=id;journal(m,id,'Sales invoice','Accounts receivable','Sales revenue',amount);
  } else if(action==='maintenance-create'){
    allow(m,['Manufacturing Operator','Cutting Operator','Supervisor']);const machine=get('machines',p.machineId);check(p.notes?.trim(),'Describe the machine issue.');const ticket={...p,id:uid('MT'),status:'Open',reporter:actor,at:now()};m.maintenance.unshift(ticket);machine.status='Unavailable';reference=ticket.id;
  } else if(action==='maintenance-resolve'){
    allow(m,['Supervisor']);const ticket=get('maintenance',p.id);check(ticket.status==='Open','Ticket already closed.');ticket.status='Closed';if(!m.maintenance.some(t=>t.machineId===ticket.machineId&&t.status==='Open'))get('machines',ticket.machineId).status='Idle';
  } else if(action==='machine-release'){
    allow(m,['Supervisor']);const machine=get('machines',p.id);check(!m.maintenance.some(t=>t.machineId===p.id&&t.status==='Open'),'Close all maintenance tickets first.');check(!m.jobs.some(j=>j.machine===p.id&&['Running','Awaiting approval'].includes(j.status)),'This machine still has an active production job.');check(!m.cuts.some(c=>c.inputs?.machine_id===p.id&&c.status==='Cutting'),'This machine still has an active cutting plan.');machine.status='Idle';
  } else if(action==='schedule'){
    allow(m,['Production Planner']);const j=get('jobs',p.id);check(p.start&&p.due>=p.start,'Select a valid date range.');check(!['Completed','Running'].includes(j.status),'Pause active work before rescheduling.');j.start=p.start;j.due=p.due;j.priority=p.priority;
  } else if(action==='alert-update'){
    m.alerts[p.id]={...m.alerts[p.id],...p.changes};
  } else if(action==='labor-update'){
    allow(m,['HR Manager']);check(data.employees.some(e=>e.id===p.employeeId),'Unknown HR employee.');check(whole(p.rate)&&p.rate>0&&p.certification?.trim(),'Enter a valid hourly rate and skill.');m.labor[p.employeeId]={rate:p.rate,certification:p.certification,expires:p.expires,shift:p.shift,approved:true};
  } else if(action==='demo-step') {m.demoStep=Math.max(0,Math.min(12,p.step));return data;
  } else throw Error('Unknown manufacturing action.');
  m.audit.unshift({id:uid('AUD'),at:now(),actor,role:m.actor.role,action,reference});
  return data;
}

export function reconcilePayments(data) {
  if(!data.manufacturing)return data;
  const missing=data.invoices.filter(i=>i.currency==='LKR'&&i.manufacturingOrder&&i.status==='Paid'&&!data.manufacturing.costs.some(c=>c.reference===i.id&&c.kind==='Customer payment'));
  if(!missing.length)return data;
  const next=structuredClone(data);missing.forEach(i=>journal(next.manufacturing,i.id,'Customer payment','Cash','Accounts receivable',Math.round(i.amount*100)));return next;
}
