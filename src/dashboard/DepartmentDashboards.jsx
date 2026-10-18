import { useState } from 'react';
import { ArrowDownLeft, ArrowRight, ArrowUpRight, BriefcaseBusiness, CalendarDays, CheckCheck, Clock3, FileText, Receipt, TrendingUp, Users, Wallet } from 'lucide-react';
import { initials, sum } from '../data';

const palette = ['#c8261e', '#222222', '#e26760', '#737373', '#c4c4c4', '#f1b8b4'];
const money = (value, currency) => new Intl.NumberFormat('en-US', { style: 'currency', currency, maximumFractionDigits: 0 }).format(value);
const localMonth = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
const displayDate = value => value ? new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'No date';

function Heading({ department, title, description, children }) {
  return <div className="page-title"><div><span className="eyebrow">{department} / OVERVIEW</span><h1>{title}</h1><p>{description}</p></div><div className="title-actions">{children}</div></div>;
}

function Stat({ label, value, detail, icon: Icon, featured = false, onClick }) {
  return <button className={`dashboard-stat ${featured ? 'featured' : ''}`} onClick={onClick}>
    <span className="dashboard-stat-top"><span className="dashboard-stat-icon"><Icon size={19} /></span><ArrowUpRight size={17} /></span>
    <span className="dashboard-stat-label">{label}</span><strong>{value}</strong><small>{detail}</small>
  </button>;
}

function QuickLinks({ items, navigate }) {
  return <nav className="dashboard-quick-links" aria-label="Department shortcuts">{items.map(([id, label, Icon]) => <button key={id} onClick={() => navigate(id)}><span><Icon size={19} /></span>{label}<ArrowUpRight size={15} /></button>)}</nav>;
}

function CardHeader({ title, subtitle, children }) {
  return <div className="panel-heading"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div>{children}</div>;
}

function Blank({ children }) { return <div className="dashboard-blank"><span><BriefcaseBusiness size={22} /></span><p>{children}</p></div>; }

function Breakdown({ items, total, label, format = String }) {
  let offset = 0;
  const segments = items.filter(item => item.value > 0).map((item, index) => {
    const from = offset;
    offset += item.value / (total || 1) * 100;
    return `${palette[index % palette.length]} ${from}% ${offset}%`;
  });
  const visible = items.filter(item => item.value > 0);
  return <div className="dashboard-breakdown">
    <div className="dashboard-ring" role="img" aria-label={`${label}: ${format(total)}. ${visible.map(item => `${item.label}: ${format(item.value)}`).join(', ')}`} style={{ background: segments.length ? `conic-gradient(${segments.join(',')})` : 'var(--border)' }}><div><span>{label}</span><strong>{format(total)}</strong></div></div>
    <div className="dashboard-legend">{visible.map((item, index) => <div key={item.label}><i style={{ background: palette[index % palette.length] }} /><span>{item.label}</span><strong>{format(item.value)}</strong></div>)}{!visible.length && <p className="dashboard-muted">No records to display yet.</p>}</div>
  </div>;
}

function RecentActivity({ data, kinds }) {
  const rows = (data.activity || []).filter(item => kinds.includes(item.kind)).slice(0, 5);
  return <section className="panel dashboard-activity"><CardHeader title="Recent activity" subtitle="Updates from your workspace" />{rows.length ? <div className="dashboard-activity-list">{rows.map(item => <div key={item.id}><span><CheckCheck size={15} /></span><div><strong>{item.title}</strong><small>{item.detail}</small></div></div>)}</div> : <Blank>Updates will appear as your team works.</Blank>}</section>;
}

export function HRDashboard({ data, navigate }) {
  const active = data.employees.filter(employee => employee.status !== 'Inactive');
  const present = active.filter(employee => ['Present', 'Late'].includes(data.attendance[employee.id]?.status)).length;
  const pending = data.leaves.filter(leave => leave.status === 'Pending');
  const teams = Object.entries(active.reduce((counts, employee) => { const name = employee.department || 'Unassigned'; counts[name] = (counts[name] || 0) + 1; return counts; }, {})).sort((a, b) => b[1] - a[1]);
  const attendance = ['Present', 'Late', 'On leave', 'Absent', 'Not recorded'].map(status => ({ label: status, value: active.filter(employee => (data.attendance[employee.id]?.status || 'Not recorded') === status).length }));
  const latest = [...data.employees].sort((a, b) => (b.joined || '').localeCompare(a.joined || '')).slice(0, 5);
  return <div className="department-dashboard">
    <Heading department="HUMAN RESOURCES" title="Your people, in one place." description="A little clarity for every team, every working day."><button className="button" onClick={() => navigate('employees')}><Users size={16} />Employee directory</button><button className="button primary" onClick={() => navigate('leave')}>Review requests<ArrowRight size={16} /></button></Heading>
    <div className="dashboard-stats">
      <Stat featured label="Your workforce" value={active.length} detail="Active team members across departments" icon={Users} onClick={() => navigate('employees')} />
      <Stat label="At work today" value={present} detail="Present and late attendance records" icon={BriefcaseBusiness} onClick={() => navigate('attendance')} />
      <Stat label="Leave requests" value={pending.length} detail="Awaiting your review" icon={CalendarDays} onClick={() => navigate('leave')} />
      <Stat label="Payroll status" value={data.payroll?.status || 'Not generated'} detail="Current payroll cycle" icon={Wallet} onClick={() => navigate('payroll')} />
    </div>
    <QuickLinks navigate={navigate} items={ [['employees', 'Team directory', Users], ['attendance', 'Attendance', Clock3], ['leave', 'Leave requests', CalendarDays], ['payroll', 'Payroll', Wallet]] } />
    <div className="department-dashboard-grid"><div className="dashboard-main-column">
      <section className="panel"><CardHeader title="Team distribution" subtitle="Active employees by department"><span className="dashboard-period">{teams.length} departments</span></CardHeader><div className="dashboard-team-chart">{teams.length ? teams.map(([name, count], index) => <div key={name}><div><span>{name}</span><strong>{count} <small>{count === 1 ? 'person' : 'people'}</small></strong></div><div className="dashboard-progress" role="img" aria-label={`${name}: ${count} of ${active.length} employees`}><span style={{ width: `${count / active.length * 100}%`, background: palette[index % palette.length] }} /></div></div>) : <Blank>Add your first employee to build your team overview.</Blank>}</div></section>
      <section className="panel"><CardHeader title="Recently joined" subtitle="Your latest employee records"><button className="text-button" onClick={() => navigate('employees')}>View directory<ArrowRight size={14} /></button></CardHeader><div className="table-wrap"><table><thead><tr><th>TEAM MEMBER</th><th>DEPARTMENT</th><th>JOINED</th><th>STATUS</th></tr></thead><tbody>{latest.map(employee => <tr key={employee.id}><td><div className="person-cell"><span className="avatar green">{initials(employee.name)}</span><div><strong>{employee.name}</strong><span>{employee.role}</span></div></div></td><td>{employee.department || 'Unassigned'}</td><td>{displayDate(employee.joined)}</td><td><span className={`badge ${employee.status === 'Active' ? 'positive' : 'neutral'}`}>{employee.status}</span></td></tr>)}</tbody></table></div>{!latest.length && <Blank>Your employee directory is empty.</Blank>}</section>
    </div><aside className="dashboard-side-column">
      <section className="panel"><CardHeader title="Attendance today" subtitle={new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric' })} /><Breakdown items={attendance} total={active.length} label="Team members" /></section>
      <section className="panel"><CardHeader title="Needs your attention" subtitle="Pending leave requests" />{pending.length ? <div className="dashboard-request-list">{pending.slice(0, 4).map(leave => <button key={leave.id} onClick={() => navigate('leave')}><span className="dashboard-request-icon"><CalendarDays size={17} /></span><span><strong>{data.employees.find(employee => employee.id === leave.employeeId)?.name || leave.employeeId}</strong><small>{leave.type} · {displayDate(leave.start)}</small></span><ArrowUpRight size={15} /></button>)}</div> : <Blank>All caught up. No pending leave requests.</Blank>}</section>
      <RecentActivity data={data} kinds={['people', 'payroll']} />
    </aside></div>
  </div>;
}

export function FinanceDashboard({ data, navigate }) {
  const [currency, setCurrency] = useState('USD');
  const [period, setPeriod] = useState(6);
  const invoices = data.invoices.filter(invoice => (invoice.currency || 'USD') === currency);
  const expenses = data.expenses.filter(expense => (expense.currency || 'USD') === currency);
  const paidInvoices = invoices.filter(invoice => invoice.status === 'Paid');
  const paidExpenses = expenses.filter(expense => expense.status === 'Paid');
  const income = sum(paidInvoices), expenseTotal = sum(paidExpenses);
  const payroll = currency === 'USD' && data.payroll?.status === 'Paid' ? Number(data.payroll.total || 0) : 0;
  const cashOut = expenseTotal + payroll;
  const outstanding = sum(invoices.filter(invoice => ['Pending', 'Overdue'].includes(invoice.status)));
  const fmt = value => money(value, currency);
  const now = new Date();
  const months = Array.from({ length: period }, (_, index) => {
    const date = new Date(now.getFullYear(), now.getMonth() - period + 1 + index, 1), key = localMonth(date);
    return { key, label: date.toLocaleDateString('en-US', { month: 'short' }), income: sum(paidInvoices.filter(invoice => (invoice.issued || '').startsWith(key))), expense: sum(paidExpenses.filter(expense => (expense.date || '').startsWith(key))) };
  });
  const maximum = Math.max(1, ...months.flatMap(month => [month.income, month.expense]));
  const categories = Object.entries(paidExpenses.reduce((groups, expense) => { const name = expense.category || 'Other'; groups[name] = (groups[name] || 0) + Number(expense.amount || 0); return groups; }, {})).sort((a, b) => b[1] - a[1]).map(([label, value]) => ({ label, value }));
  const recent = [...invoices.map(invoice => ({ ...invoice, key: `invoice-${invoice.id}`, name: invoice.client, type: 'Invoice', date: invoice.issued, route: 'invoices' })), ...expenses.map(expense => ({ ...expense, key: `expense-${expense.id}`, name: expense.description || expense.category, type: 'Expense', route: 'expenses' }))].sort((a, b) => (b.date || '').localeCompare(a.date || '')).slice(0, 6);
  return <div className="department-dashboard">
    <Heading department="FINANCE" title="Your finances, at a glance." description="Keep an eye on your income, spending, and what comes next."><label className="dashboard-currency">Currency<select aria-label="Dashboard currency" value={currency} onChange={event => setCurrency(event.target.value)}><option value="USD">USD</option><option value="LKR">LKR</option></select></label><button className="button primary" onClick={() => navigate('reports')}><TrendingUp size={16} />View reports</button></Heading>
    <div className="dashboard-stats">
      <Stat featured label="Recorded cash position" value={fmt(income - cashOut)} detail={`Paid income less expenses${currency === 'USD' ? ' & payroll' : ''}`} icon={Wallet} onClick={() => navigate('accounts')} />
      <Stat label="Collected income" value={fmt(income)} detail={`${paidInvoices.length} paid invoices · all time`} icon={ArrowDownLeft} onClick={() => navigate('invoices')} />
      <Stat label="Paid expenses" value={fmt(cashOut)} detail={currency === 'USD' ? 'Expense register & paid payroll' : 'Expense register · all time'} icon={Receipt} onClick={() => navigate('expenses')} />
      <Stat label="Outstanding" value={fmt(outstanding)} detail="Pending and overdue invoices" icon={Clock3} onClick={() => navigate('invoices')} />
    </div>
    <QuickLinks navigate={navigate} items={ [['invoices', 'Invoices', FileText], ['expenses', 'Expenses', Receipt], ['accounts', 'Accounts', Wallet], ['reports', 'Reports', TrendingUp]] } />
    <div className="department-dashboard-grid"><div className="dashboard-main-column">
      <section className="panel"><CardHeader title="Income & expenses" subtitle="Paid records by document month; excludes payroll"><select className="compact-select" aria-label="Chart period" value={period} onChange={event => setPeriod(Number(event.target.value))}><option value={6}>Last 6 months</option><option value={12}>Last 12 months</option></select></CardHeader>
        <div className="dashboard-chart-summary"><div><span>Income in period</span><strong>{fmt(sum(months, 'income'))}</strong></div><div className="dashboard-chart-key"><span><i />Income</span><span><i />Expenses</span></div></div>
        <div className="dashboard-bar-chart" role="img" aria-label={`Income and expense chart in ${currency}`}><div className="dashboard-chart-axis"><span>{fmt(maximum === 1 && !months.some(month => month.income || month.expense) ? 0 : maximum)}</span><span>0</span></div><div className="dashboard-chart-columns">{months.map(month => <div className="dashboard-chart-month" key={month.key}><div className="dashboard-bar-pair" tabIndex={0} aria-label={`${month.key}: income ${fmt(month.income)}, expenses ${fmt(month.expense)}`}><span style={{ height: `${month.income / maximum * 100}%` }} /><span style={{ height: `${month.expense / maximum * 100}%` }} /><div className="dashboard-chart-tooltip">{month.key}<br />Income {fmt(month.income)}<br />Expenses {fmt(month.expense)}</div></div><small>{month.label}</small></div>)}</div></div>
        {!months.some(month => month.income || month.expense) && <p className="dashboard-chart-note">No paid records in this period. Your chart will grow with your business.</p>}
      </section>
      <section className="panel"><CardHeader title="Recent financial records" subtitle={`Latest invoices and expenses · ${currency}`} /><div className="table-wrap"><table><thead><tr><th>RECORD</th><th>DATE</th><th>AMOUNT</th><th>STATUS</th><th><span className="sr-only">Open</span></th></tr></thead><tbody>{recent.map(row => <tr key={row.key}><td><strong>{row.name || row.id}</strong><small className="cell-subtitle">{row.type} · {row.id}</small></td><td>{displayDate(row.date)}</td><td className="tabular"><strong>{fmt(row.amount)}</strong></td><td><span className={`badge ${row.status === 'Paid' ? 'positive' : row.status === 'Overdue' ? 'negative' : 'neutral'}`}>{row.status}</span></td><td><button className="icon-button" aria-label={`Open ${row.type.toLowerCase()} register for ${row.id}`} onClick={() => navigate(row.route)}><ArrowUpRight size={16} /></button></td></tr>)}</tbody></table></div>{!recent.length && <Blank>Your invoices and expenses will appear here.</Blank>}</section>
    </div><aside className="dashboard-side-column">
      <section className="panel"><CardHeader title="Spending breakdown" subtitle="Paid expenses · all time, excludes payroll" /><Breakdown items={categories} total={expenseTotal} label="Total expenses" format={fmt} /></section>
      <section className="panel dashboard-review-card"><span className="dashboard-review-icon"><FileText size={20} /></span><div><h2>Ready for review</h2><p>{expenses.filter(expense => expense.status === 'Pending').length} expenses are waiting for approval.</p></div><button className="button" onClick={() => navigate('expenses')}>Review expenses<ArrowRight size={15} /></button></section>
      <RecentActivity data={data} kinds={['finance']} />
    </aside></div>
    <p className="footnote">Totals are shown in {currency}. Currencies are kept separate. Recorded cash position excludes opening balances and unrecorded movements.</p>
  </div>;
}
