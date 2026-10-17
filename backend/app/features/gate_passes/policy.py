from datetime import datetime, timezone
from hashlib import sha256
from fastapi import HTTPException

SECURITY = {'Gate Security Officer', 'Security Supervisor'}
WAREHOUSE = {'Warehouse Manager', 'Inventory Officer'}
MANAGEMENT = {'Factory Manager'}
REQUESTERS = {'Factory Manager', 'Production Planner', 'Supervisor', 'Inventory Officer', 'Warehouse Manager', 'Procurement Officer', 'Sales Officer', 'Salesman', 'Transport Officer'}
READERS = REQUESTERS | SECURITY | {'Finance Officer', 'Quality Inspector'}
CHECKS = {'vehicle', 'driver', 'items', 'quantities', 'serials', 'documents', 'seal'}
TERMINAL = {'COMPLETED', 'REJECTED', 'CANCELLED', 'EXPIRED'}


def require(condition, message, code=409):
    if not condition:
        raise HTTPException(code, message)


def token_hash(token):
    return sha256(token.encode()).hexdigest()


def effective_status(row, now=None):
    if row['status'] not in TERMINAL and row['valid_until'] <= (now or datetime.now(timezone.utc)):
        return 'EXPIRED'
    return row['status']


def return_status(items, due, now=None):
    issued = sum(i['moved_quantity'] for i in items)
    closed = sum(i['returned_quantity'] + i['written_off_quantity'] for i in items)
    if not issued:
        return 'NOT_ISSUED'
    if closed >= issued:
        return 'CLOSED_WITH_WRITE_OFF' if any(i['written_off_quantity'] for i in items) else 'FULLY_RETURNED'
    if due and due < (now or datetime.now(timezone.utc)):
        return 'OVERDUE'
    return 'PARTIALLY_RETURNED' if closed else 'AWAITING_RETURN'


def authorize_action(actor, row, action, approvals):
    role, employee = actor['role'], actor['id']
    status = effective_status(row)
    requester = row['requester_id'] == employee
    if action in {'exception', 'resolve_exception'}:
        require(role in SECURITY, 'Security role required.', 403)
        if action == 'resolve_exception':
            require(role == 'Security Supervisor', 'Security Supervisor required.', 403)
        return
    if action == 'write_off':
        require(role in MANAGEMENT and not requester and row['return_required'], 'Independent Factory Manager required for a return write-off.', 403)
        return
    if action == 'cancel':
        require(requester or role in MANAGEMENT, 'Only the requester or Factory Manager may cancel.', 403)
        require(status not in TERMINAL, 'This pass is already closed.')
        return
    require(status not in TERMINAL, f'This pass is {status.lower()}.')
    if action == 'submit':
        require(requester and role in REQUESTERS, 'Only the requester may submit.', 403)
        require(status == 'DRAFT', 'Only drafts can be submitted.')
    elif action == 'verify':
        require(role in WAREHOUSE and not requester, 'An independent warehouse employee must verify.', 403)
        require(status == 'PENDING_WAREHOUSE_VERIFICATION', 'This pass is not awaiting warehouse verification.')
    elif action in {'approve', 'reject'}:
        require(status == 'PENDING_APPROVAL', 'This pass is not awaiting approval.')
        done = [a['actor_id'] for a in approvals if a['decision'] == 'APPROVED']
        steps = row['approval_roles']
        require(len(done) < len(steps) and role == steps[len(done)], 'The current approval step belongs to another role.', 403)
        require(not requester and employee != row['verified_by'] and employee not in done, 'Approval requires an independent employee at every step.', 403)
    elif action == 'ready':
        require(requester or role in WAREHOUSE, 'Requester or warehouse role required.', 403)
        require(status == 'APPROVED', 'Approval must finish before gate readiness.')
    elif action in {'inspect', 'confirm'}:
        require(role in SECURITY, 'Security role required.', 403)
        prior = {row['requester_id'], row['verified_by']} | {a['actor_id'] for a in approvals}
        require(employee not in prior, 'Gate inspection requires an independent security employee.', 403)
        require(status in ({'READY_AT_GATE'} if action == 'inspect' else {'UNDER_GATE_INSPECTION'}), 'Start a new inspection before confirming this movement.')
        if action == 'confirm':
            require(row['inspected_by'] == employee, 'Only the inspecting officer can confirm this movement.', 403)
