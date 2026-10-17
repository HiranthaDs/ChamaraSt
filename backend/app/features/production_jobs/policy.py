from fastapi import HTTPException

STAGES = ['Bending', 'Welding', 'Grinding', 'Painting', 'Assembly', 'Quality inspection', 'Packaging']
JOB_COLUMNS = ['Backlog','Pending Approval','Ready for Production','In Progress','Blocked / On Hold','Quality Inspection','Production Completed','Ready for Dispatch','Dispatched','Closed']
PROPOSAL_COLUMNS = ['Ideas','Submitted','Under Review','Feasibility Study','Design & Costing','Prototype Development','Prototype Testing','Awaiting Final Approval','Approved for Production','Launched','Rejected / Archived']
PLANNERS = {'Factory Manager','Production Planner','Supervisor'}
FINANCE = {'Factory Manager','Finance Officer'}
READERS = PLANNERS | FINANCE | {'Cutting Operator','Manufacturing Operator','Quality Inspector','Inventory Officer','Warehouse Manager','Procurement Officer','HR Manager','Sales Officer'}
WORKERS = {'Cutting Operator','Manufacturing Operator'}
REVIEW_ROLES = {
    'Technical': ['Supervisor','Production Planner'],
    'Materials': ['Inventory Officer','Procurement Officer','Warehouse Manager'],
    'Cost': ['Finance Officer'], 'Prototype': ['Supervisor'],
    'Quality': ['Quality Inspector'], 'Final': ['Factory Manager'],
}

def require(condition, message, status=409):
    if not condition:
        raise HTTPException(status, message)

def role(actor, allowed):
    require(actor['role'] in allowed, 'Your HR role cannot perform this operation.', 403)

def validate_dependencies(task_id, dependencies, edges):
    graph = {}
    for child, parent in edges:
        if child != task_id:
            graph.setdefault(child, []).append(parent)
    graph[task_id] = dependencies
    def visit(node, path):
        require(node not in path, 'Task dependencies must not contain a cycle.', 422)
        for parent in graph.get(node, []):
            visit(parent, path | {node})
    visit(task_id, set())

def progress(order, product, goods, tasks, weights=None):
    route = order.get('route') or product.get('route') or STAGES
    weights = weights or {stage: 1 for stage in route}
    approved = {h.get('stage') for h in order.get('history', []) if h.get('decision') in {'Approve','Pass'}}
    weighted = sum(weights.get(s, 1) for s in route if s in approved)
    total = sum(weights.get(s, 1) for s in route) or 1
    quantity = max(1, order.get('quantity', 1))
    accepted = sum(g.get('qc') == 'Pass' for g in goods)
    received = sum(g.get('qc') == 'Pass' and g.get('status') != 'Receiving' and g.get('bin') != 'QA-HOLD' for g in goods)
    qc = order.get('qc') == 'Pass' and 'Quality inspection' in approved
    complete = order.get('status') == 'Completed' and qc and received >= quantity
    return {'tasks': round(100 * sum(t['status']=='COMPLETED' for t in tasks) / max(1, len([t for t in tasks if t['status']!='CANCELLED']))),
            'manufacturing': 100 if complete else min(95, round(weighted / total * 95)),
            'quality': round(min(accepted,quantity)/quantity*100) if qc else 0,
            'warehouse': round(min(received,quantity)/quantity*100), 'accepted_units': accepted,
            'received_units': received, 'remaining_units': max(0,quantity-received),
            'rework': order.get('status')=='Rework', 'quality_approved': qc, 'manufactured': complete}

def cost_total(costs):
    return sum(costs[k] for k in ['material','cutting','waste','labor','machine','consumables','overhead','prototype']) - costs['offcut_credit']
