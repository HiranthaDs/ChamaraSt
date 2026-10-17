import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright-core';
import { preview } from 'vite';
import { initialState, emptyState } from '../src/data.js';
import { emptyManufacturing } from '../src/manufacturing/store.js';

// All requests use fixtures. This visual check never writes to the ERP database.
const server = await preview({ configFile: false, preview: { host: '127.0.0.1', port: 4187, strictPort: true } });
let browser;
try {
  browser = await chromium.launch({ executablePath: process.env.BROWSER_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true });
  await mkdir('qa/dashboard-theme', { recursive: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let state = { ...structuredClone(initialState), manufacturing: emptyManufacturing() };
  const people = [
    { id: 'QA-MANAGER', name: 'Factory Manager', role: 'Factory Manager', department: 'Manufacturing' },
    { id: 'QA-OFFICER', name: 'Sales Officer', role: 'Sales Officer', department: 'Sales' },
    { id: 'QA-SALESMAN', name: 'Field Salesman', role: 'Salesman', department: 'Sales', supervisorId: 'QA-OFFICER' },
    { id: 'QA-UNASSIGNED', name: 'New Salesman', role: 'Salesman', department: 'Sales' },
    { id: 'QA-SECURITY', name: 'Gate Officer', role: 'Gate Security Officer', department: 'Operations' },
  ].map(person => ({ ...person, status: 'Active', joined: '2026-10-01' }));
  state.employees.push(...people);
  state.invoices.push({ id: 'QA-LKR', client: 'LKR Customer', amount: 95000, currency: 'LKR', status: 'Paid', issued: '2026-10-01' });
  await page.routeWebSocket('**/api/sales-tracking/ws**', () => {});
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    let json = [];
    if (path === '/api/state') json = { state };
    if (path.endsWith('/sessions/active')) json = null;
    if (path.endsWith('/metadata')) json = { types: [], catalogs: {}, field_jobs: [], checkpoints: [{ id: 'MAIN', name: 'Main gate', active: true }], permissions: { scan: true, create: false, warehouse: false, approve: false, settings: false } };
    if (path.includes('/salesmen/')) json = { employee: people[2], summary: {}, sessions: [], points: [], stops: [], visits: [] };
    await route.fulfill({ json });
  });
  async function portal(department, hash, identity = null) {
    await page.goto('http://127.0.0.1:4187');
    await page.evaluate(({ department, identity }) => {
      sessionStorage.setItem('orbit-demo-department', department);
      if (identity) sessionStorage.setItem('orbit-demo-sales-actor', JSON.stringify(identity));
    }, { department, identity });
    if (department === 'manufacturing') state.manufacturing.actor = { role: 'Factory Manager', employeeId: 'QA-MANAGER' };
    await page.goto(`http://127.0.0.1:4187/#${hash}`);
    await page.reload();
    await page.locator('.app-shell').waitFor();
    await page.getByTitle('Database connected', { exact: true }).waitFor().catch(() => {});
    await page.waitForTimeout(300);
  }
  async function screenshot(name) {
    await page.screenshot({ path: `qa/dashboard-theme/${name}.png`, fullPage: true });
  }
  async function mobile(name) {
    await page.setViewportSize({ width: 1024, height: 900 });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name}: tablet horizontal overflow`);
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.getByRole('button', { name: 'Toggle sidebar', exact: true }).isVisible(), false);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name}: mobile horizontal overflow`);
    await screenshot(`${name}-mobile`);
    await page.getByRole('button', { name: 'Open navigation', exact: true }).click();
    await page.locator('.sidebar.open').waitFor();
    await page.locator('.sidebar-scrim').click({ position: { x: 350, y: 300 } });
    await page.setViewportSize({ width: 1440, height: 1050 });
  }
  await portal('finance', 'finance-dashboard');
  await page.getByRole('heading', { name: 'Your finances, at a glance.' }).waitFor();
  assert.match(await page.locator('.dashboard-stat').nth(1).innerText(), /69,300/);
  await screenshot('finance');
  await page.getByLabel('Dashboard currency').selectOption('LKR');
  assert.match(await page.locator('.dashboard-stat').nth(1).innerText(), /95,000/);
  assert.match(await page.locator('.dashboard-stat').nth(2).innerText(), /0/);
  await page.getByLabel('Chart period').selectOption('12');
  assert.equal(await page.locator('.dashboard-chart-month').count(), 12);
  await mobile('finance');
  await page.getByRole('button', { name: 'Toggle sidebar', exact: true }).click();
  assert.ok(await page.locator('.app-shell').evaluate(element => element.classList.contains('sidebar-collapsed')));
  await page.getByRole('button', { name: 'Toggle sidebar', exact: true }).click();
  await portal('hr', 'hr-dashboard');
  await page.getByRole('heading', { name: 'Your people, in one place.' }).waitFor();
  await screenshot('hr');
  await mobile('hr');
  await page.getByRole('button', { name: 'Team directory', exact: true }).click();
  assert.equal(new URL(page.url()).hash, '#employees');
  await portal('manufacturing', 'factory');
  await page.locator('.mf-kpis').waitFor();
  await screenshot('manufacturing');
  await mobile('manufacturing');
  await portal('sales', 'sales-dashboard', { role: 'Sales Officer', employeeId: 'QA-OFFICER' });
  await page.getByRole('heading', { name: 'Your salesmen', exact: true }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Assign to my team', exact: true }).count(), 1);
  await screenshot('sales');
  await mobile('sales');
  await page.locator('.sf-salesman-bar').first().click();
  await page.locator('.sf-salesman-profile').waitFor();
  await screenshot('sales-profile');
  await mobile('sales-profile');
  await portal('sales', 'sales-dashboard', { role: 'Salesman', employeeId: 'QA-SALESMAN' });
  await page.locator('.sf-page-head').waitFor();
  await screenshot('salesman');
  await mobile('salesman');
  await portal('security', 'gate-dashboard', { role: 'Gate Security Officer', employeeId: 'QA-SECURITY' });
  await page.locator('.gp .metrics-grid').waitFor();
  await screenshot('security');
  await mobile('security');
  state = { ...structuredClone(emptyState), manufacturing: emptyManufacturing() };
  await portal('finance', 'finance-dashboard');
  assert.ok((await page.locator('.dashboard-stat strong').allTextContents()).every(value => value === '$0'));
  await page.getByText('Your invoices and expenses will appear here.', { exact: true }).waitFor();
  await screenshot('finance-empty');
  await portal('hr', 'hr-dashboard');
  await page.getByText('Your employee directory is empty.', { exact: true }).waitFor();
  await screenshot('hr-empty');
  assert.deepEqual(errors, []);
  console.log('PASS: five department dashboards, separate salesman profile, USD/LKR isolation, period selector, empty states, navigation, assignment controls, desktop/mobile layouts; no browser runtime errors. All API data mocked.');
} finally {
  await browser?.close();
  await new Promise(resolve => server.httpServer.close(resolve));
}
