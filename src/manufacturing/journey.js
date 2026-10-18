import { STAGES } from './store';

export function orderCoverage(m, order) {
  const available = m.goods.filter(g => g.productId === order.productId && g.status === 'Available' && g.qc === 'Pass' && g.bin !== 'QA-HOLD').length;
  const linked = m.jobs.filter(j => j.salesOrderId === order.id && !['Completed', 'Cancelled'].includes(j.status));
  const receiving = m.goods.filter(g => g.productId === order.productId && g.status === 'Receiving' && g.qc === 'Pass' && m.jobs.some(j => j.id === g.jobId && j.salesOrderId === order.id)).length;
  const planned = linked.reduce((n, j) => n + j.quantity, 0) + receiving;
  return { available, planned, linked, shortage: Math.max(0, order.quantity - available - planned) };
}

export function jobNext(job, meta, m) {
  if (meta?.blockers) return { title:'Resolve reported blockers', role:'Supervisor', destination:'record', detail:'Open the job blockers and record a resolution before continuing.' };
  if (job.status === 'Completed') {
    const receiving = m.goods.filter(g => g.jobId === job.id && g.status === 'Receiving');
    return receiving.length ? { title:'Put away finished goods', role:'Warehouse Manager', destination:'receiving', detail:`${receiving.length} units await a warehouse bin.` }
      : { title:job.salesOrderId ? 'Fulfil linked shop order' : 'Review and close stock batch', role:'Warehouse Manager', destination:job.salesOrderId?'sales':'record', detail:'Production is finished. Stock batches can close after reconciliation; sales are a separate flow.' };
  }
  if (job.status === 'Planned') return { title:'Check and reserve materials', role:'Inventory Officer', destination:'production', detail:'Resolve BOM shortages, then reserve materials for this batch.' };
  if (job.status === 'Awaiting approval') return { title:'Review completed stage', role:'Supervisor', destination:'production', detail:'A different employee checks the completion evidence.' };
  if (job.status === 'Awaiting QC') return { title:'Inspect product quality', role:'Quality Inspector', destination:'production', detail:'Record the actual inspection result and evidence.' };
  if (meta && !meta.approved_by && !job.materialsPosted) return { title:'Submit / approve production release', role:meta.status==='Pending Approval'?'Supervisor':'Production Planner', destination:'record', detail:'Use Change stage in the job record. Release approval must be independent of the creator.' };
  if (!meta && !job.materialsPosted) return { title:'Check production release', role:'Production Planner', destination:'record', detail:'Open the job record to check release approval before starting.' };
  return { title:job.status==='Running'?'Record stage completion':'Start / resume stage', role:'Manufacturing Operator', destination:'production', detail:`Assigned operator completes ${(job.route || STAGES)[job.stage] || 'the current operation'} and records actual hours and evidence.` };
}
