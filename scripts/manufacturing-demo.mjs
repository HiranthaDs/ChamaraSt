// Runs a complete, deterministic manufacturing demo against disposable in-memory data.
// No browser, Supabase connection, or live inventory writes are used.
import assert from 'node:assert/strict';
import { emptyState } from '../src/data.js';
import { emptyManufacturing, migrate, seedManufacturing, STAGES, transition } from '../src/manufacturing/store.js';

const identities = {
  planner: { role: 'Production Planner', employeeId: 'EMP-008' },
  operator: { role: 'Manufacturing Operator', employeeId: 'EMP-005' },
  supervisor: { role: 'Supervisor', employeeId: 'EMP-002' },
  inspector: { role: 'Quality Inspector', employeeId: 'EMP-011' },
  warehouse: { role: 'Warehouse Manager', employeeId: 'EMP-007' },
  sales: { role: 'Sales Officer', employeeId: 'EMP-010' },
};

const employees = [
  ['EMP-002', 'Phoenix Baker'], ['EMP-005', 'Drew Cano'], ['EMP-007', 'Andi Lane'],
  ['EMP-008', 'Kate Morrison'], ['EMP-010', 'Alex Morgan'], ['EMP-011', 'Samira Perera'],
].map(([id, name]) => ({ id, name, role: 'Demo employee', department: 'Manufacturing', status: 'Active' }));
const attendance = Object.fromEntries(employees.map(({ id }) => [id, { status: 'Present', checkIn: '08:00' }]));
const manufacturing = {
  ...seedManufacturing(), actor: identities.planner,
  jobs: [], goods: [], orders: [], cuts: [], parts: [], movements: [], costs: [], maintenance: [], purchases: [],
};
let state = migrate({ ...emptyState, employees, attendance, manufacturing: { ...emptyManufacturing(), ...manufacturing } });

function act(action, payload = {}, as = state.manufacturing.actor) {
  state = transition(state, 'actor', as);
  state = transition(state, action, payload);
  return state.manufacturing;
}

console.log('Starting isolated manufacturing demo (all values below are sample data).');

// Plan two Rear Buffers. The seeded BOM stock covers this quantity.
let m = act('job-create', {
  productId: 'RB-001', quantity: 2, operator: identities.operator.employeeId,
  machine: 'BEND-01', start: '2026-10-19', due: '2026-10-30', priority: 'Normal',
  notes: 'DEMO ONLY: standard Rear Buffer batch; verify dimensions and finish.',
}, identities.planner);
const job = m.jobs[0];
assert.equal(job.status, 'Planned');
console.log(`Created ${job.id}: ${job.quantity} × Rear Buffer.`);

m = act('job-reserve', { id: job.id }, identities.planner);
assert.equal(m.jobs[0].status, 'Ready');
console.log('Reserved BOM materials after the inventory availability check.');

// Run every configured stage; each is completed by the operator and independently approved.
while (state.manufacturing.jobs.find(row => row.id === job.id).status !== 'Completed') {
  let current = state.manufacturing.jobs.find(row => row.id === job.id);
  if (current.status === 'Ready') {
    act('job-start', { id: job.id }, identities.operator);
    current = state.manufacturing.jobs.find(row => row.id === job.id);
    assert.equal(current.status, 'Running');
    act('job-complete', {
      id: job.id, hours: 1,
      notes: `DEMO ONLY: ${STAGES[current.stage]} completed; sample evidence recorded.`,
    }, identities.operator);
    current = state.manufacturing.jobs.find(row => row.id === job.id);
    assert.equal(current.status, 'Awaiting approval');
    act('job-review', { id: job.id, decision: 'Approve', reason: 'DEMO ONLY: independent sample review passed.' }, identities.supervisor);
    current = state.manufacturing.jobs.find(row => row.id === job.id);
  }
  if (current.status === 'Awaiting QC') {
    act('qc', {
      id: job.id, pass: true,
      notes: 'DEMO ONLY: sample dimensions within tolerance; surface and assembly checks passed.',
    }, identities.inspector);
    current = state.manufacturing.jobs.find(row => row.id === job.id);
  }
  assert.ok(['Ready', 'Completed'].includes(current.status), `Unexpected job state: ${current.status}`);
  console.log(`${current.status === 'Completed' ? 'Finished' : 'Approved'} ${STAGES[Math.min(current.stage, STAGES.length - 1)]}.`);
}

m = state.manufacturing;
const finishedGoods = m.goods.filter(good => good.jobId === job.id && good.status === 'Receiving');
assert.equal(finishedGoods.length, job.quantity, 'Production must release the planned quantity.');
console.log(`Released ${finishedGoods.length} finished serials to warehouse receiving.`);

for (const good of finishedGoods) {
  act('goods-move', { id: good.id, bin: 'WH1-A1' }, identities.warehouse);
  assert.equal(state.manufacturing.goods.find(row => row.id === good.id).status, 'Available');
}
console.log(`Put away all ${finishedGoods.length} serials in WH1-A1 after the capacity check.`);

// Create and fulfill a customer request using exactly the two newly produced serials.
m = act('order-create', {
  shopId: 'SHOP-01', productId: 'RB-001', quantity: 2, due: '2026-10-30',
}, identities.sales);
const order = m.orders[0];
assert.equal(order.status, 'Requested');
for (const expected of ['Allocated', 'Picked', 'Packed', 'Dispatched']) {
  act('order-advance', { id: order.id }, identities.warehouse);
  assert.equal(state.manufacturing.orders.find(row => row.id === order.id).status, expected);
  console.log(`Shop request ${order.id}: ${expected}.`);
}
act('order-advance', {
  id: order.id, proof: `DEMO ONLY: sample proof of delivery for ${order.id}; not a real shipment.`,
}, identities.warehouse);
assert.equal(state.manufacturing.orders.find(row => row.id === order.id).status, 'Delivered');
assert.equal(state.manufacturing.goods.filter(good => good.jobId === job.id && good.status === 'Dispatched').length, 2);

console.log(`\nDEMO COMPLETE: ${job.id} → ${order.id} → Delivered.`);
console.log('All changes existed only in memory and were discarded when this script exited.');
