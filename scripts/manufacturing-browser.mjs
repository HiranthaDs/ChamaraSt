import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright-core';
import { preview } from 'vite';
const server=await preview({preview:{host:'127.0.0.1',port:4174,strictPort:true}});
const browser=await chromium.launch({executablePath:process.env.BROWSER_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
const context=await browser.newContext({viewport:{width:1536,height:1080},reducedMotion:'reduce'});const page=await context.newPage();page.setDefaultTimeout(12000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const state=()=>page.evaluate(()=>JSON.parse(localStorage.getItem('orbit-erp-v1')));
const nav=async id=>{await page.goto(`http://127.0.0.1:4174/#${id}`);await page.locator('.mf-context').waitFor();};
const dialog=()=>page.getByRole('dialog');
const role=async r=>page.getByLabel('Manufacturing role').selectOption(r);
try{
  await mkdir('qa',{recursive:true});
  await nav('factory');await page.screenshot({path:'qa/manufacturing-overview.png',fullPage:true});
  await page.getByRole('button',{name:'Guided walkthrough'}).click();await dialog().getByRole('heading',{name:'One connected manufacturing story'}).waitFor();await page.keyboard.press('Escape');
  await nav('materials');await page.getByRole('button',{name:'Receive material',exact:true}).click();await dialog().getByRole('button',{name:'Register physical sheets'}).click();
  assert.equal((await state()).manufacturing.sheets.length,24);
  await page.getByRole('button',{name:'Offcut library',exact:true}).click();await page.getByText('Material with a second life',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Product catalog',exact:true}).click();await page.getByRole('button',{name:'View BOM'}).first().click();await dialog().getByLabel('Production quantity').fill('50');assert.ok(await dialog().getByText('25 L',{exact:true}).count());await page.keyboard.press('Escape');
  await nav('cutting');await role('Cutting Operator');await page.getByRole('button',{name:'Optimize layout',exact:true}).click();await page.getByRole('button',{name:'Save cutting plan'}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Save cutting plan'}).isEnabled(),true);
  await page.screenshot({path:'qa/cutting-studio.png',fullPage:true});
  const before=(await state()).manufacturing.materials.find(m=>m.id==='steel-parts').onHand;
  await page.getByRole('button',{name:'Save cutting plan'}).click();assert.equal((await state()).manufacturing.materials.find(m=>m.id==='steel-parts').onHand,before);
  await page.getByRole('button',{name:'Submit for review'}).click();
  await role('Supervisor');await page.getByRole('button',{name:'Approve plan',exact:true}).click();
  await role('Cutting Operator');await page.getByRole('button',{name:'Execute cut',exact:true}).click();await page.getByRole('button',{name:'Confirm actuals'}).click();await dialog().getByRole('button',{name:'Post stock update'}).click();
  assert.equal((await state()).manufacturing.parts.length,6);
  await nav('production');await page.screenshot({path:'qa/manufacturing-production.png',fullPage:true});
  for(const tab of ['Schedule','Factory floor','Workforce']){await page.locator('.mf-tabs').getByRole('button',{name:tab,exact:true}).click();assert.equal(await page.locator('main').innerText().then(s=>s.length>100),true);}
  await nav('quality');await role('Supervisor');await page.getByRole('button',{name:'Approve',exact:true}).click();assert.equal((await state()).manufacturing.jobs.find(j=>j.id==='PR-101').stage,2);
  await nav('warehouse');await page.getByRole('button',{name:'Find a serial'}).click();await dialog().getByLabel('Serial number').fill('FG-RB-0001');await dialog().getByRole('button',{name:'Open product passport'}).click();await dialog().getByText('Product passport · FG-RB-0001',{exact:true}).waitFor();await dialog().getByRole('img',{name:'QR link to FG-RB-0001'}).waitFor();await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Toggle sidebar',exact:true}).click();assert.ok(await page.locator('.app-shell').evaluate(el=>el.classList.contains('sidebar-collapsed')));await page.getByRole('button',{name:'Toggle sidebar',exact:true}).click();
  await page.keyboard.press('Control+k');await dialog().getByLabel('Search people, invoices, or pages...').fill('FG-RB-0001');await dialog().getByRole('button').filter({hasText:'FG-RB-0001'}).click();await dialog().getByText('Product passport · FG-RB-0001',{exact:true}).waitFor();await page.keyboard.press('Escape');
  await nav('distribution');await role('Warehouse Manager');await page.screenshot({path:'qa/manufacturing-distribution.png',fullPage:true});
  for(const label of ['Allocate stock','Confirm picked','Confirm packed','Dispatch shipment']){await page.getByRole('button',{name:label,exact:true}).first().click();await dialog().getByRole('button',{name:'Confirm',exact:true}).click();}
  await role('Finance Officer');await page.getByRole('button',{name:'Create invoice',exact:true}).click();const invoice=(await state()).invoices.find(i=>i.currency==='LKR');assert.ok(invoice);
  await page.getByRole('button',{name:'Open Finance invoices'}).click();await page.getByLabel('Invoice currency').selectOption('LKR');await page.getByRole('button',{name:invoice.id,exact:true}).click();assert.match(await dialog().innerText(),/LKR/);await dialog().getByRole('button',{name:'Record payment',exact:true}).click();assert.ok((await state()).manufacturing.costs.some(c=>c.reference===invoice.id&&c.kind==='Customer payment'));
  await nav('manufacturing-reports');await page.getByRole('button',{name:'Ask the copilot'}).click();await dialog().getByRole('button',{name:'Which offcuts can be reused?'}).click();await dialog().getByText(/offcuts are available/).waitFor();await page.keyboard.press('Escape');
  await page.keyboard.press('Control+k');await page.getByRole('dialog').getByLabel('Search people, invoices, or pages...').fill('Cutting');await page.getByRole('dialog').getByRole('button',{name:'Cutting Studio',exact:true}).click();await page.getByRole('heading',{name:'Make more from every sheet.'}).waitFor();
  const mobile=await browser.newContext({viewport:{width:390,height:844},isMobile:true});const mp=await mobile.newPage();mp.on('pageerror',e=>errors.push(e.message));
  for(const id of ['factory','materials','cutting','production','quality','warehouse','distribution','manufacturing-reports']){
    await mp.goto(`http://127.0.0.1:4174/#${id}`);await mp.locator('.mf-context').waitFor();
    assert.ok(await mp.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Mobile horizontal overflow: ${id}`);
    if(id==='factory')await mp.screenshot({path:'qa/manufacturing-mobile.png',fullPage:true});
    if(id==='cutting'){await mp.getByRole('button',{name:'Optimize layout',exact:true}).click();await mp.screenshot({path:'qa/cutting-mobile.png',fullPage:true});}
  }
  assert.deepEqual(errors,[]);console.log('PASS: all manufacturing routes, batch receiving, BOM calculator, cutting approval and execution, quality review, serial passport, distribution and existing Finance LKR payment, copilot, keyboard navigation, mobile overflow, and no runtime errors.');
}finally{await browser.close();await new Promise(resolve=>server.httpServer.close(resolve));}
