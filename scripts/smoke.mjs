import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright-core';
import { preview } from 'vite';

// Uses the locally installed Edge browser. Set BROWSER_PATH for another machine.
const server = await preview({ preview: { host: '127.0.0.1', port: 4173, strictPort: true } });
const browser = await chromium.launch({ executablePath: process.env.BROWSER_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, reducedMotion: 'reduce' });
const page = await context.newPage();
const errors = [];
page.on('pageerror', e => errors.push(e.message));
const state = () => page.evaluate(() => JSON.parse(localStorage.getItem('orbit-erp-v1')));
const nav = async (name) => { await page.locator('aside').getByRole('button', { name, exact: true }).click(); };
const dialog = () => page.getByRole('dialog');
const openEmployee = async (name) => page.getByRole('button', { name: `View ${name}`, exact: true }).click();

try {
  await page.goto('http://127.0.0.1:4173', { waitUntil: 'networkidle' });
  await page.getByRole('heading', { name: /Good morning/ }).waitFor();
  assert.match(await page.getByRole('heading', { name: /Good morning/ }).innerText(), /👋/, 'Unicode characters must render correctly');
  await mkdir('qa', { recursive: true });
  await page.screenshot({ path: 'qa/desktop-overview.png', fullPage: true });
  assert.equal((await state()).employees.length, 12);

  await nav('Employees');
  await page.getByRole('button', { name: 'Add employee', exact: true }).click();
  await dialog().getByLabel('Full name').fill('Jamie Test');
  await dialog().getByLabel('Work email').fill('jamie.test@example.com');
  await dialog().getByLabel('Job title').fill('Frontend Engineer');
  await dialog().getByLabel('Department', { exact: true }).selectOption('Engineering');
  await dialog().getByLabel('Monthly salary').fill('6000.50');
  await dialog().getByRole('button', { name: 'Add employee', exact: true }).click();
  await page.getByLabel('Search employees...').fill('Jamie Test');
  await page.getByText('Jamie Test', { exact: true }).waitFor();
  const employee = (await state()).employees.find(e => e.name === 'Jamie Test');
  assert.equal(employee.salary, 6000.5);
  await openEmployee('Jamie Test');
  await dialog().getByText('$6,000.50', { exact: true }).waitFor();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Grid view' }).click();
  assert.equal(await page.locator('.employee-card').count(), 1);

  await nav('Attendance');
  await page.getByLabel('Attendance for Jamie Test').selectOption('Present');
  assert.equal((await state()).attendance[employee.id].status, 'Present');

  await page.locator('aside .nav-item').filter({ hasText: 'Leave requests' }).click();
  await page.getByRole('button', { name: 'New leave request' }).click();
  await dialog().getByLabel('Employee', { exact: true }).selectOption(employee.id);
  await dialog().getByLabel('Start date').fill('2026-10-25');
  await dialog().getByLabel('End date').fill('2026-10-24');
  await dialog().getByLabel('Reason').fill('Family trip');
  await dialog().getByRole('button', { name: 'Submit request' }).click();
  await dialog().getByRole('alert').waitFor();
  await dialog().getByLabel('End date').fill('2026-10-26');
  await dialog().getByRole('button', { name: 'Submit request' }).click();
  const leave = (await state()).leaves.find(l => l.employeeId === employee.id);
  await page.getByRole('button', { name: `Approve ${leave.id}`, exact: true }).click();
  assert.equal((await state()).leaves.find(l => l.id === leave.id).status, 'Approved');

  await nav('Invoices');
  await page.getByRole('button', { name: 'Create invoice', exact: true }).click();
  await dialog().getByLabel('Client name').fill('Test Client');
  await dialog().getByLabel('Client email').fill('billing@example.com');
  await dialog().getByLabel('Amount (USD)').fill('1500.75');
  await dialog().getByLabel('Description').fill('Frontend implementation');
  await dialog().getByRole('button', { name: 'Create invoice', exact: true }).click();
  const invoice = (await state()).invoices.find(i => i.client === 'Test Client');
  await page.getByRole('button', { name: `Open ${invoice.id}` }).click();
  await dialog().getByRole('button', { name: 'Finalize invoice' }).click();
  await page.getByRole('button', { name: `Open ${invoice.id}` }).click();
  await dialog().getByRole('button', { name: 'Record payment' }).click();
  assert.equal((await state()).invoices.find(i => i.id === invoice.id).status, 'Paid');

  await nav('Expenses');
  await page.getByRole('button', { name: 'Add expense' }).click();
  await dialog().getByLabel('Employee', { exact: true }).selectOption(employee.id);
  await dialog().getByLabel('Amount (USD)').fill('125.25');
  await dialog().getByLabel('Description').fill('Test equipment');
  await dialog().getByRole('button', { name: 'Submit expense' }).click();
  const expense = (await state()).expenses.find(e => e.description === 'Test equipment');
  await page.getByRole('button', { name: `Review ${expense.id}` }).click();
  await dialog().getByRole('button', { name: 'Approve expense' }).click();
  await page.getByRole('button', { name: `Review ${expense.id}` }).click();
  await dialog().getByRole('button', { name: 'Record reimbursement' }).click();
  assert.equal((await state()).expenses.find(e => e.id === expense.id).status, 'Paid');

  await nav('Payroll');
  await page.getByRole('button', { name: 'Run payroll' }).click();
  await dialog().getByRole('button', { name: 'Generate payroll' }).click();
  const payroll = (await state()).payroll;
  assert.equal(payroll.employees.length, 13);
  assert.equal(payroll.total, (await state()).employees.reduce((n, e) => n + e.salary, 0));
  await page.getByRole('button', { name: 'Review payroll' }).click();
  await dialog().getByRole('button', { name: 'Approve payroll' }).click();
  await page.getByRole('button', { name: 'Review payroll' }).click();
  await dialog().getByRole('button', { name: 'Record payment' }).click();
  assert.equal((await state()).payroll.status, 'Paid');
  assert.equal(await page.getByRole('button', { name: 'Payroll completed' }).isDisabled(), true);

  await nav('Accounts');
  await page.getByText('Payment from Test Client', { exact: true }).waitFor();
  await page.getByText('October team payroll', { exact: true }).waitFor();
  const s = await state();
  const balance = 125000 + s.invoices.filter(i => i.status === 'Paid').reduce((n, i) => n + i.amount, 0) - s.expenses.filter(e => e.status === 'Paid').reduce((n, e) => n + e.amount, 0) - s.payroll.total;
  const balanceText = await page.locator('.bank-card h2').innerText();
  assert.equal(Number(balanceText.replace(/[^0-9.-]/g, '')), balance);

  await nav('Reports');
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download report' }).click();
  const download = await downloadPromise;
  assert.match(download.suggestedFilename(), /financial-summary-2026-10\.csv$/);
  await nav('Settings');
  await page.getByLabel('Company name').fill('Test Workspace');
  await page.getByRole('button', { name: 'Save changes' }).click();
  await page.reload({ waitUntil: 'networkidle' });
  assert.equal(await page.getByLabel('Company name').inputValue(), 'Test Workspace');

  // A fresh context keeps screenshots free of the test data.
  const mobile = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, deviceScaleFactor: 1 });
  const mobilePage = await mobile.newPage();
  mobilePage.on('pageerror', e => errors.push(e.message));
  await mobilePage.goto('http://127.0.0.1:4173', { waitUntil: 'networkidle' });
  assert.equal(await mobilePage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Mobile overview must not overflow horizontally');
  await mobilePage.screenshot({ path: 'qa/mobile-overview.png', fullPage: true });
  await mobilePage.getByRole('button', { name: 'Open navigation' }).click();
  await mobilePage.locator('aside').getByRole('button', { name: 'Employees', exact: true }).click();
  await mobilePage.getByRole('heading', { name: 'Good people. Great potential.' }).waitFor();
  assert.equal(await mobilePage.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Mobile employees must not overflow horizontally');
  assert.deepEqual(errors, [], 'No browser runtime errors');
  console.log('PASS: employee creation, decimal amounts, attendance, leave validation/approval, invoice lifecycle, expense approval/payment, payroll lifecycle, account reconciliation, CSV export, persistence, and mobile navigation.');
  console.log('Screenshots: qa/desktop-overview.png and qa/mobile-overview.png');
} finally {
  await browser.close();
  await new Promise(resolve => server.httpServer.close(resolve));
}
