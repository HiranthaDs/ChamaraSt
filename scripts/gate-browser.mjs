import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { preview } from 'vite';
import { emptyState } from '../src/data.js';
import { emptyManufacturing } from '../src/manufacturing/store.js';

const server=await preview({preview:{host:'127.0.0.1',port:4185,strictPort:true}});
const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
try{
  const page=await browser.newPage({viewport:{width:1366,height:900}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const state={...structuredClone(emptyState),manufacturing:emptyManufacturing(),employees:[{id:'QA-SEC',name:'Security Test',role:'Gate Security Officer',status:'Active',department:'Operations'}]};
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    let response=[];
    if(path==='/api/state')response={state};
    if(path.endsWith('/metadata'))response={types:[],catalogs:{},field_jobs:[],checkpoints:[{id:'MAIN',name:'Main gate',active:true}],permissions:{scan:true,create:false,warehouse:false,approve:false,settings:false}};
    await route.fulfill({json:response});
  });
  await page.goto('http://127.0.0.1:4185');
  await page.getByRole('button',{name:/Gate & Security.*Verify movements/}).click();
  await page.getByRole('button',{name:/Enter Gate & Security dashboard/}).click();
  await page.getByRole('heading',{name:'Gate & security',exact:true}).waitFor();
  await page.getByRole('button',{name:'Scanner',exact:true}).click();
  await page.getByRole('heading',{name:'Verify a gate pass'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Create',exact:true}).count(),0);
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow');
  assert.deepEqual(errors,[]);
  console.log('PASS: portal login, security dashboard, scanner, role navigation and mobile width; mocked API, no runtime errors.');
}finally{await browser.close();await new Promise(resolve=>server.httpServer.close(resolve));}
