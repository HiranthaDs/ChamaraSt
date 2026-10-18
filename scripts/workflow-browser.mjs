// Browser UI contract test. All API traffic is intercepted; no business data is written.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright-core';
import { createServer } from 'vite';
import { emptyState } from '../src/data.js';
import { emptyManufacturing, STAGES } from '../src/manufacturing/store.js';
const server=await createServer({server:{host:'127.0.0.1',port:4195,strictPort:true}});await server.listen();
const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const employees=[{id:'UI-MGR',name:'UI Manager',role:'Factory Manager',status:'Active',department:'Manufacturing'},{id:'UI-OP',name:'UI Operator',role:'Manufacturing Operator',status:'Active',department:'Manufacturing'},{id:'UI-SUP',name:'UI Supervisor',role:'Supervisor',status:'Active',department:'Manufacturing'}];
const columns=['Backlog','Pending Approval','Ready for Production','In Progress','Blocked / On Hold','Quality Inspection','Production Completed','Ready for Dispatch','Dispatched','Closed'];
const proposalColumns=['Ideas','Submitted','Under Review','Feasibility Study','Design & Costing','Prototype Development','Prototype Testing','Awaiting Final Approval','Approved for Production','Launched','Rejected / Archived'];
const meta={columns,proposal_columns:proposalColumns,stages:STAGES,config:{},can_plan:true,can_finance:true,employees,materials:[{id:'MAT-1',name:'Steel components',unit:'pcs',onHand:20,reserved:2}],products:[{id:'RB-001',name:'Rear buffer'}],machines:[{id:'M-1',name:'Press',status:'Idle'}],sales_orders:[],review_roles:{Technical:['Supervisor','Production Planner'],Materials:['Inventory Officer'],Cost:['Finance Officer'],Prototype:['Supervisor'],Quality:['Quality Inspector'],Final:['Factory Manager']}};
const job={id:'MO-UI-001',production_order_id:'MO-UI-001',product_name:'Rear buffer',product_id:'RB-001',quantity:10,status:'Backlog',board_status:'Backlog',production_status:'Planned',current_stage:'Bending',operator:'UI-OP',supervisor_id:'UI-SUP',priority:'High',version:1,planned_start:'2026-10-17',due_date:'2026-10-20',progress:{tasks:0,manufacturing:0,quality:0,warehouse:0,accepted_units:0,received_units:0,remaining_units:10,manufactured:false},shortages:[],blockers:0,team:['UI-OP'],tasks:[],stages:[],materials:[{materialId:'MAT-1',amount:2}],quality:{result:'Pending'},goods:[],blocker_history:[],exceptions:[],activity:[],documents:[],stock_movements:[],attendance:{'UI-OP':'Present'},costs:{material:0,labor:0,overhead:0,postings:[]},dispatch:{gates:[],movements:[],shipments:[],deliveries:[]},specification:{route:STAGES,revision:'A'}};
const stats={active:1,overdue:0,blocked:0,manufactured:0,quality_holds:0,tasks:[],conflicts:[],stages:{Bending:1}};
let proposals=[];const errors=[];const requests=[];
const context=await browser.newContext({viewport:{width:1440,height:1050}});
await context.addInitScript(()=>sessionStorage.setItem('orbit-demo-department','manufacturing'));
await context.route('**/api/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname;let body;
  if(req.method()!=='GET') {try{body=req.postDataJSON();}catch{} requests.push({path,body});}
  let result={};
  if(path==='/api/state')result=req.method()==='GET'?{state:{...structuredClone(emptyState),employees,manufacturing:{...emptyManufacturing(),actor:{role:'Factory Manager',employeeId:'UI-MGR'}}}}:{};
  else if(path.endsWith('/metadata'))result=meta;
  else if(path.endsWith('/analytics'))result=stats;
  else if(path==='/api/production-jobs')result=[job];
  else if(path==='/api/production-jobs/MO-UI-001/tasks'&&body){job.tasks.push({id:'TASK-UI-1',...body,status:'TODO',version:1,actual_hours:0});result=job;}
  else if(path.startsWith('/api/production-jobs/MO-UI-001'))result=job;
  else if(path==='/api/product-proposals'&&body){const p={id:'NPP-UI-1',...body,status:'Ideas',proposed_by:'UI-MGR',current_version:1,version:1,versions:[{id:'REV-UI-1',version_number:1,specifications:body.specifications,change_summary:body.change_summary,created_by:'UI-MGR'}],approvals:{},reviews:[],prototypes:[],estimates:[],documents:[],activity:[]};proposals.push(p);result=p;}
  else if(path==='/api/product-proposals')result=proposals;
  else if(path.startsWith('/api/product-proposals/NPP-UI-1'))result=proposals[0];
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(result)});
});
const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(15000);
try {
  await mkdir('qa',{recursive:true});
  await page.goto('http://127.0.0.1:4195/#production-jobs');
  await page.getByRole('heading',{name:'Every job. A clear next step.'}).waitFor();
  await page.getByRole('button',{name:/MO-UI-001.*Rear buffer/}).click();
  await page.locator('.wf-tabs').getByRole('button',{name:'Tasks',exact:true}).click();
  await page.getByRole('button',{name:'Add task',exact:true}).click();
  const dialog=page.getByRole('dialog');
  await dialog.getByLabel('Task title').fill('Prepare bending jig');
  await dialog.getByLabel('Assigned employee').selectOption('UI-OP');
  await dialog.getByLabel('Independent reviewer').selectOption('UI-SUP');
  await dialog.getByRole('button',{name:'Save',exact:true}).click();
  await page.getByRole('heading',{name:'Prepare bending jig'}).waitFor();
  assert.equal(requests.find(r=>r.path.endsWith('/tasks')).body.assigned_employee_id,'UI-OP');
  for(const tab of ['Overview','Manufacturing stages','Materials','Quality','Employees','Costs','Documents','Activity','Dispatch'])await page.locator('.wf-tabs').getByRole('button',{name:tab,exact:true}).click();
  await page.getByRole('button',{name:'All jobs',exact:true}).click();
  for(const v of ['List','Timeline','Analytics','Board']) await page.locator('.wf-view-switch').getByRole('button',{name:v,exact:true}).click();
  await page.screenshot({path:'qa/production-jobs-desktop.png',fullPage:true});
  await page.goto('http://127.0.0.1:4195/#product-proposals');
  await page.getByRole('button',{name:'New proposal',exact:true}).click();
  await dialog.getByLabel('Proposal title').fill('New vehicle bracket');await dialog.getByLabel('Proposed product name').fill('Adjustable mounting bracket');
  await dialog.getByLabel('Business Justification').fill('Customer requested improved fitment');await dialog.getByLabel('Description',{exact:true}).fill('A revised bracket with better fitment');
  await dialog.getByRole('button',{name:'Create proposal',exact:true}).click();
  await page.getByRole('button',{name:/NPP-UI-1.*Adjustable mounting bracket/}).click();
  for(const tab of ['Technical','Costing','Prototypes','Reviews','Documents','Versions','Activity','Overview'])await page.locator('.wf-tabs').getByRole('button',{name:tab,exact:true}).click();
  await page.screenshot({path:'qa/product-proposal-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.getByRole('button',{name:'All proposals',exact:true}).click();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile proposal board overflow');
  await page.screenshot({path:'qa/product-proposals-mobile.png',fullPage:true});
  await page.goto('http://127.0.0.1:4195/#production-jobs');await page.getByRole('heading',{name:'Every job. A clear next step.'}).waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile production board overflow');
  await page.screenshot({path:'qa/production-jobs-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: production views, all detail tabs, task assignment request, proposal creation, responsive desktop/mobile, no browser errors. API intercepted; no live writes.');
} finally {await browser.close();await server.close();}
