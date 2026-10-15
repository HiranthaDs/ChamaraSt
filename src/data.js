export const departments = ['Engineering', 'Design', 'Marketing', 'Finance', 'People & Culture', 'Operations'];
export const seedEmployees = [
  { id: 'EMP-001', name: 'Olivia Rhye', email: 'olivia@acme.co', role: 'Product Designer', department: 'Design', status: 'Active', employment: 'Full-time', salary: 5800, joined: '2024-02-12', color: 'peach' },
  { id: 'EMP-002', name: 'Phoenix Baker', email: 'phoenix@acme.co', role: 'Engineering Lead', department: 'Engineering', status: 'Active', employment: 'Full-time', salary: 8200, joined: '2023-06-05', color: 'purple' },
  { id: 'EMP-003', name: 'Lana Steiner', email: 'lana@acme.co', role: 'People Partner', department: 'People & Culture', status: 'Active', employment: 'Full-time', salary: 5200, joined: '2024-01-08', color: 'green' },
  { id: 'EMP-004', name: 'Demi Wilkinson', email: 'demi@acme.co', role: 'Marketing Manager', department: 'Marketing', status: 'On leave', employment: 'Full-time', salary: 6100, joined: '2023-09-18', color: 'pink' },
  { id: 'EMP-005', name: 'Drew Cano', email: 'drew@acme.co', role: 'Frontend Developer', department: 'Engineering', status: 'Active', employment: 'Full-time', salary: 6500, joined: '2025-03-10', color: 'blue' },
  { id: 'EMP-006', name: 'Natali Craig', email: 'natali@acme.co', role: 'Financial Analyst', department: 'Finance', status: 'Active', employment: 'Full-time', salary: 5600, joined: '2024-07-22', color: 'yellow' },
  { id: 'EMP-007', name: 'Andi Lane', email: 'andi@acme.co', role: 'Brand Designer', department: 'Design', status: 'Active', employment: 'Contract', salary: 4800, joined: '2026-09-01', color: 'purple' },
  { id: 'EMP-008', name: 'Kate Morrison', email: 'kate@acme.co', role: 'Operations Manager', department: 'Operations', status: 'Active', employment: 'Full-time', salary: 6300, joined: '2023-11-06', color: 'peach' },
  { id: 'EMP-009', name: 'Koray Okumus', email: 'koray@acme.co', role: 'Backend Developer', department: 'Engineering', status: 'Active', employment: 'Full-time', salary: 6700, joined: '2025-05-19', color: 'green' },
  { id: 'EMP-010', name: 'Alex Morgan', email: 'alex@acme.co', role: 'Content Strategist', department: 'Marketing', status: 'Active', employment: 'Part-time', salary: 3200, joined: '2026-10-01', color: 'blue' },
  { id: 'EMP-011', name: 'Samira Perera', email: 'samira@acme.co', role: 'Accountant', department: 'Finance', status: 'Active', employment: 'Full-time', salary: 5100, joined: '2024-04-15', color: 'pink' },
  { id: 'EMP-012', name: 'Nimal Silva', email: 'nimal@acme.co', role: 'QA Engineer', department: 'Engineering', status: 'On leave', employment: 'Full-time', salary: 4900, joined: '2025-08-11', color: 'yellow' },
];
export const seedLeaves = [
  { id: 'LV-001', employeeId: 'EMP-001', type: 'Annual leave', start: '2026-10-22', end: '2026-10-23', reason: 'A short family trip.', status: 'Pending' },
  { id: 'LV-002', employeeId: 'EMP-005', type: 'Personal leave', start: '2026-10-20', end: '2026-10-20', reason: 'Personal appointment.', status: 'Pending' },
  { id: 'LV-003', employeeId: 'EMP-004', type: 'Annual leave', start: '2026-10-14', end: '2026-10-16', reason: 'Family holiday.', status: 'Approved' },
  { id: 'LV-004', employeeId: 'EMP-012', type: 'Sick leave', start: '2026-10-15', end: '2026-10-15', reason: 'Recovery day.', status: 'Approved' },
  { id: 'LV-005', employeeId: 'EMP-009', type: 'Annual leave', start: '2026-11-02', end: '2026-11-06', reason: 'Travel plans.', status: 'Pending' },
];
export const seedInvoices = [
  { id: 'INV-2026-001', client: 'Layers Studio', email: 'billing@layers.example', description: 'Product design retainer', amount: 12800, issued: '2026-10-01', due: '2026-10-10', status: 'Paid' },
  { id: 'INV-2026-002', client: 'Sisyphus', email: 'accounts@sisyphus.example', description: 'Platform development — phase 2', amount: 24500, issued: '2026-10-02', due: '2026-10-12', status: 'Paid' },
  { id: 'INV-2026-003', client: 'Circooles', email: 'hello@circooles.example', description: 'Brand strategy and identity', amount: 8400, issued: '2026-10-03', due: '2026-10-13', status: 'Overdue' },
  { id: 'INV-2026-004', client: 'Catalog', email: 'finance@catalog.example', description: 'October engineering services', amount: 18600, issued: '2026-10-05', due: '2026-10-20', status: 'Pending' },
  { id: 'INV-2026-005', client: 'Quotient', email: 'billing@quotient.example', description: 'Customer portal implementation', amount: 32000, issued: '2026-10-06', due: '2026-10-14', status: 'Paid' },
  { id: 'INV-2026-006', client: 'Hourglass', email: 'hello@hourglass.example', description: 'Digital experience consulting', amount: 6750, issued: '2026-10-10', due: '2026-10-25', status: 'Draft' },
];
export const seedExpenses = [
  { id: 'EXP-001', employeeId: 'EMP-005', category: 'Equipment', description: 'Development workstation', amount: 1850, date: '2026-10-14', status: 'Pending' },
  { id: 'EXP-002', employeeId: 'EMP-004', category: 'Travel', description: 'Client workshop travel', amount: 420, date: '2026-10-13', status: 'Pending' },
  { id: 'EXP-003', employeeId: 'EMP-008', category: 'Office', description: 'October office supplies', amount: 680, date: '2026-10-10', status: 'Approved' },
  { id: 'EXP-004', employeeId: 'EMP-002', category: 'Software', description: 'Team software subscriptions', amount: 1240, date: '2026-10-08', status: 'Paid' },
  { id: 'EXP-005', employeeId: 'EMP-003', category: 'Meals', description: 'New joiner welcome lunch', amount: 185, date: '2026-10-07', status: 'Paid' },
];
export const initialState = {
  employees: seedEmployees, leaves: seedLeaves, invoices: seedInvoices, expenses: seedExpenses,
  attendance: Object.fromEntries(seedEmployees.map((e, i) => [e.id, { status: e.status === 'On leave' ? 'On leave' : i === 4 ? 'Late' : 'Present', checkIn: e.status === 'On leave' ? '' : i === 4 ? '09:24' : ['08:52', '08:45', '08:58', '09:00'][i % 4] }])),
  payroll: null,
  settings: { company: 'Acme Studio', admin: 'Alex Johnson', email: 'alex@acme.co', weekStart: 'Monday' },
  activity: [{ id: 'a1', title: 'October invoices updated', detail: 'Finance · 15 Oct, 9:40 AM', kind: 'finance' }, { id: 'a2', title: 'Alex Morgan joined the team', detail: 'People & Culture · 1 Oct, 9:00 AM', kind: 'people' }, { id: 'a3', title: 'September payroll completed', detail: 'Payroll · 30 Sep, 4:30 PM', kind: 'payroll' }],
};

export const monthlyCashflow = [
  { month: 'May', income: 58000, expenses: 42000 }, { month: 'Jun', income: 72000, expenses: 48000 },
  { month: 'Jul', income: 63000, expenses: 44000 }, { month: 'Aug', income: 86000, expenses: 55000 },
  { month: 'Sep', income: 78000, expenses: 51000 },
];
export const money = (n, compact = false) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: compact || Number.isInteger(n) ? 0 : 2, maximumFractionDigits: compact ? 1 : 2, ...(compact ? { notation: 'compact' } : {}) }).format(n);
export const dateLabel = (s) => new Date(s + 'T12:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
export const initials = (name = '') => name.split(' ').map(x => x[0]).slice(0, 2).join('');
export const sum = (rows, field = 'amount') => rows.reduce((total, r) => total + Number(r[field] || 0), 0);
export const daysBetween = (start, end) => Math.round((new Date(end + 'T12:00:00') - new Date(start + 'T12:00:00')) / 86400000) + 1;
export function exportCsv(filename, rows) {
  if (!rows.length) return;
  const keys = Object.keys(rows[0]);
  const escape = (v) => '"' + String(v ?? '').replace(/^[=+@\-\t\r]/, "'$&").replaceAll('"', '""') + '"';
  const csv = '\uFEFF' + [keys.map(escape).join(','), ...rows.map(row => keys.map(key => escape(row[key])).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8;' }));
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
