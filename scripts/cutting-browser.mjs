// UI uses the real Python geometry engine. ERP state / persistence are isolated fixtures.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir} from 'node:fs/promises';
import {chromium} from 'playwright-core';
import {createServer} from 'vite';
import {emptyState} from '../src/data.js';
import {emptyManufacturing} from '../src/manufacturing/store.js';
const server=await createServer({server:{host:'127.0.0.1',port:4197,strictPort:true}});await server.listen();
const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const context=await browser.newContext({viewport:{width:1600,height:1050}});const errors=[];let plans=[],lastPreview;
const state={...structuredClone(emptyState),employees:[{id:'CUT-UI',name:'Test manager',role:'Factory Manager',status:'Active',department:'Manufacturing'}],manufacturing:{...emptyManufacturing(),actor:{role:'Factory Manager',employeeId:'CUT-UI'}}};
await context.addInitScript(()=>sessionStorage.setItem('orbit-demo-department','manufacturing'));
function engine(kind,body){return new Promise((resolve,reject)=>{const child=spawn('backend/.venv/Scripts/python.exe',['-m','backend.tests.cutting_compute',kind],{windowsHide:true});let out='',err='';child.stdout.on('data',v=>out+=v);child.stderr.on('data',v=>err+=v);child.on('error',reject);child.on('exit',code=>{try{code?reject(Error(err)):resolve(JSON.parse(out));}catch(e){reject(e);}});child.stdin.end(JSON.stringify(body));});}
await context.route('**/api/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname,body=req.method()==='GET'?null:req.postDataJSON();let result=[];
  if(path==='/api/state')result=req.method()==='GET'?{state}:{};
  else if(path.endsWith('/cutting/preview')){result=await engine('preview',body);lastPreview=result;}
  else if(path.endsWith('/cutting/validate'))result=await engine('validate',body);
  else if(path.endsWith('/cutting/plans')){
    if(body){const layout=await engine('validate',{inputs:body.inputs,placements:body.placements,mode:body.mode});result={id:'CUT-UI-SAVED',inputs:body.inputs,layout,original_layout:layout,status:'Draft',version:1,createdBy:'CUT-UI'};plans=[result];}else result=plans;
  }
  try{await route.fulfill({status:result.detail?422:200,contentType:'application/json',body:JSON.stringify(result)});}catch{}
});
const page=await context.newPage();page.setDefaultTimeout(30000);page.on('pageerror',e=>errors.push(e.message));
async function ready(){await page.getByText('Validated layout',{exact:true}).waitFor();}
try{
  await page.goto('http://127.0.0.1:4197/#cutting');await ready();
  const parts=()=>page.locator('.cut-input details').filter({has:page.getByLabel('Part name',{exact:true})});
  await parts().nth(0).getByLabel('Part name',{exact:true}).fill('Circular plate');await parts().nth(0).getByLabel('Shape',{exact:true}).selectOption('circle');await parts().nth(0).getByLabel('Quantity',{exact:true}).fill('12');
  await page.getByRole('button',{name:'Add part',exact:true}).click();await parts().nth(1).getByLabel('Part name',{exact:true}).fill('Rectangle');await parts().nth(1).getByLabel('Quantity',{exact:true}).fill('8');
  await page.getByRole('button',{name:'Add part',exact:true}).click();await parts().nth(2).getByLabel('Part name',{exact:true}).fill('Square');await parts().nth(2).getByLabel('Shape',{exact:true}).selectOption('square');await parts().nth(2).getByLabel('Side',{exact:true}).fill('100');await parts().nth(2).getByLabel('Quantity',{exact:true}).fill('6');await ready();
  assert.equal(await page.locator('.cut-part').count(),26);assert.equal(await page.locator('.cut-part>circle').count(),12);assert.equal(await page.locator('.cut-comparison>button').count(),3);assert.ok(lastPreview.candidates.every(c=>c.placed===26));
  // Invalid manual edit remains visible, blocks save, and undo restores validation.
  await page.locator('.cut-part').first().click();await page.getByLabel('x',{exact:true}).fill('0');await page.getByRole('alert').filter({hasText:'violation'}).waitFor();assert.equal(await page.getByRole('button',{name:/Save draft/}).count(),0);
  await page.getByRole('button',{name:'Undo',exact:true}).click();await ready();
  await page.getByRole('button',{name:'Save draft',exact:true}).click();await page.getByText('CUT-UI-SAVED · Draft · v1',{exact:true}).waitFor();assert.equal(plans[0].layout.placed,26);
  await page.getByRole('button',{name:'Saved plans',exact:true}).click();await page.getByRole('button',{name:'Inspect',exact:true}).click();await ready();
  await mkdir('qa',{recursive:true});await page.screenshot({path:'qa/cutting-desktop.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2));await page.screenshot({path:'qa/cutting-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);console.log('PASS: real mixed-shape preview, 26 parts, three modes, manual rejection/undo, save/reopen, responsive UI, no browser exceptions.');
}finally{await browser.close();await server.close();}
