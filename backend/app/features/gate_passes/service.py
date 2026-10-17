import base64
import secrets
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException
from .models import PassInput, ActionInput
from .policy import (SECURITY, WAREHOUSE, MANAGEMENT, REQUESTERS, CHECKS, TERMINAL,
                     require, token_hash, effective_status, return_status, authorize_action)
from .repository import GateRepository, MASTER_TABLES, new_id


class GateService:
    def __init__(self, repository: GateRepository, actor):
        self.repo, self.actor = repository, actor

    def get(self, ident, lock=False):
        row = self.repo.get(ident, lock)
        self.repo.can_read(self.actor, row)
        return row

    def detail(self, ident):
        row = self.get(ident)
        row.pop('token_hash', None)
        row['status'] = effective_status(row)
        row['items'] = self.repo.items(ident)
        row['return_status'] = return_status(row['items'], row['return_due_at']) if row['return_required'] else None
        for key, table in [('approvals', 'gate_pass_approvals'), ('verifications', 'gate_pass_verifications'),
                           ('movements', 'gate_pass_movements'), ('audit', 'gate_pass_audit_logs')]:
            row[key] = self.repo.all(f'select * from public.{table} where pass_id=%s order by created_at', (ident,))
        row['attachments'] = self.repo.all('select id,filename,mime_type,uploaded_by,created_at from public.gate_pass_attachments where pass_id=%s order by created_at', (ident,))
        row['returns'] = self.repo.all('''select r.* from public.gate_pass_returns r join public.gate_pass_items i on i.id=r.original_item_id
                                      where i.pass_id=%s order by r.created_at''', (ident,))
        row['related_passes'] = self.repo.all('select id,number,status,type_code from public.gate_passes where parent_pass_id=%s', (ident,))
        return row

    def metadata(self):
        catalogs = {}
        for kind, table in MASTER_TABLES.items():
            catalogs[kind] = [r['payload'] for r in self.repo.all(f'select payload from public.{table} order by id limit 2000')]
        if self.actor['role'] in {'Salesman', 'Sales Officer'}:
            field = 'salesman_id' if self.actor['role'] == 'Salesman' else 'sales_officer_id'
            jobs = self.repo.all(f'select * from public.sales_field_jobs where {field}=%s order by work_date desc', (self.actor['id'],))
            shops = {s for j in jobs for s in j['shop_ids']}
            catalogs['sales_order'] = [o for o in catalogs['sales_order'] if o.get('shopId') in shops]
            allowed_orders = {o['id'] for o in catalogs['sales_order']}
            catalogs['invoice'] = [i for i in catalogs['invoice'] if i.get('manufacturingOrder') in allowed_orders]
            catalogs['good'] = [g for g in catalogs['good'] if g.get('orderId') in allowed_orders]
            catalogs['purchase'] = []
            catalogs['production_order'] = []
            # Sales users only need catalogs to select their linked shipment, not plant stock.
            for kind in ('material', 'sheet', 'asset'):
                catalogs[kind] = []
        else:
            jobs = self.repo.all('select * from public.sales_field_jobs order by work_date desc limit 500')
        return dict(types=self.repo.all('select * from public.gate_pass_types order by name'),
                    checkpoints=self.repo.all('select * from public.gate_checkpoints order by name'),
                    catalogs=catalogs, field_jobs=jobs,
                    permissions=dict(create=self.actor['role'] in REQUESTERS, warehouse=self.actor['role'] in WAREHOUSE,
                                     scan=self.actor['role'] in SECURITY, settings=self.actor['role'] in MANAGEMENT,
                                     approve=self.actor['role'] in {'Supervisor', 'Factory Manager', 'Finance Officer'}))

    def validate_references(self, body, policy):
        checkpoint = self.repo.one('select * from public.gate_checkpoints where id=%s and active', (body.checkpoint_id,))
        require(checkpoint and checkpoint['direction'] in ('both', policy['direction']), 'Choose an active checkpoint for this direction.', 422)
        for field, kind in [('sales_order_id', 'sales_order'), ('purchase_id', 'purchase'), ('production_order_id', 'production_order'), ('invoice_id', 'invoice')]:
            if getattr(body, field):
                self.repo.master(kind, getattr(body, field))
        if body.type_code in {'finished_goods_outward', 'customer_return'}:
            require(body.sales_order_id, 'Link an existing sales order.', 422)
        if body.type_code in {'material_inward', 'supplier_return'}:
            require(body.purchase_id, 'Link an existing purchase record.', 422)
            purchase = self.repo.master('purchase', body.purchase_id)
            require(purchase.get('status') in {'Approved', 'Received'}, 'The purchase must be approved or received.')
            require(all(i.kind == 'material' and i.reference_id == purchase.get('materialId') for i in body.items), 'Items must match the linked purchase material.')
            require(sum(i.quantity for i in body.items) <= Decimal(str(purchase.get('quantity', 0))), 'Quantity exceeds the linked purchase.')
        if body.type_code == 'subcontract_outward':
            require(body.production_order_id, 'Link an existing production order.', 422)
        if policy['return_required']:
            require(body.return_due_at, 'Enter the expected return date.', 422)
        if body.invoice_id:
            invoice = self.repo.master('invoice', body.invoice_id)
            require(body.sales_order_id and invoice.get('manufacturingOrder') == body.sales_order_id, 'Invoice must belong to the selected order.')
            require(invoice.get('status') not in {'Cancelled', 'Void'}, 'Invoice is cancelled.')
        if body.field_job_id:
            job = self.repo.one('select * from public.sales_field_jobs where id=%s', (body.field_job_id,))
            require(job and job['status'] != 'cancelled', 'Field job is missing or cancelled.', 422)
            if self.actor['role'] in {'Salesman', 'Sales Officer'}:
                require(self.actor['id'] == job['salesman_id' if self.actor['role'] == 'Salesman' else 'sales_officer_id'], 'This field job is not assigned to you.', 403)
            if body.sales_order_id:
                order = self.repo.master('sales_order', body.sales_order_id)
                require(order.get('shopId') in job['shop_ids'], 'Sales order shop is outside this field job.')
        if self.actor['role'] in {'Salesman', 'Sales Officer'}:
            require(body.type_code in {'finished_goods_outward', 'customer_return'}, 'Sales roles create shipment or customer-return passes only.', 403)
            require(body.field_job_id, 'Select your assigned field job.', 422)
        if body.type_code in {'returnable_inward', 'branch_receipt'}:
            require(body.parent_pass_id, 'Select the original outward pass.', 422)
            parent = self.get(body.parent_pass_id)
            require(parent['direction'] == 'outward', 'The original pass must be outward.')
            require(parent['return_required'] if body.type_code == 'returnable_inward' else parent['type_code'] == 'branch_transfer', 'The original pass is not eligible for this receipt.')
            require(parent['status'] not in {'DRAFT', 'REJECTED'}, 'The original pass has no authorized dispatch.')
        else:
            require(not body.parent_pass_id and all(not i.original_item_id for i in body.items), 'Original outward references are only for return/branch receipts.', 422)

    def normalize_items(self, body):
        result = []
        for item in body.items:
            source = self.repo.master(item.kind, item.reference_id)
            if item.kind in {'good', 'sheet', 'asset'}:
                require(item.quantity == 1, 'Each physical serial or asset must have quantity 1.', 422)
            if body.type_code == 'finished_goods_outward':
                require(item.kind == 'good', 'Finished-goods passes require exact allocated serials.', 422)
            if body.type_code in {'returnable_inward', 'branch_receipt'}:
                original = self.repo.one('select * from public.gate_pass_items where id=%s and pass_id=%s', (item.original_item_id, body.parent_pass_id))
                require(original and original['kind'] == item.kind and original['reference_id'] == item.reference_id, 'Return line does not match the original dispatch.', 422)
                require(item.quantity <= original['moved_quantity']-original['returned_quantity']-original['written_off_quantity'], 'Return quantity exceeds the outstanding quantity.')
            values = item.model_dump()
            values['id'] = new_id('GI')
            values['description'] = source.get('name') or source.get('material') or item.reference_id
            values['unit'] = source.get('unit', 'pcs')
            values[{'material': 'material_id', 'product': 'product_id', 'good': 'good_id', 'sheet': 'sheet_id', 'asset': 'asset_id'}[item.kind]] = item.reference_id
            result.append(values)
        return result

    def create(self, body: PassInput, ident=None):
        require(self.actor['role'] in REQUESTERS, 'This role cannot create gate passes.', 403)
        self.repo.lock_workspace()
        if ident:
            old = self.get(ident, True)
            require(old['requester_id'] == self.actor['id'] and effective_status(old) == 'DRAFT', 'Only your editable drafts can be changed.', 403)
        policy = self.repo.one('select * from public.gate_pass_types where code=%s and enabled', (body.type_code,))
        require(policy, 'This pass type is unavailable.', 422)
        require(body.valid_until > datetime.now(timezone.utc), 'Pass validity must be in the future.', 422)
        self.validate_references(body, policy)
        items = self.normalize_items(body)
        values = body.model_dump(exclude={'items'})
        values.update(direction=policy['direction'], return_required=policy['return_required'])
        if ident:
            self.repo.update(ident, values)
            self.repo.db.execute('delete from public.gate_pass_items where pass_id=%s', (ident,))
        else:
            ident = new_id('GP')
            sequence = self.repo.one("select nextval('public.gate_pass_number_seq') as n")['n']
            self.repo.insert('gate_passes', dict(id=ident, number=f'GP-{datetime.now(timezone.utc):%Y}-{sequence:06d}',
                 requester_id=self.actor['id'], requester_department=self.actor['payload'].get('department', ''), **values))
        for values in items:
            self.repo.insert('gate_pass_items', dict(pass_id=ident, **values))
        self.repo.audit(self.actor, 'DRAFT_UPDATED' if ident and 'old' in locals() else 'CREATED', ident, after='DRAFT')
        return self.detail(ident)

    def validate_stock(self, row, items):
        order = self.repo.master('sales_order', row['sales_order_id']) if row['sales_order_id'] else None
        if row['field_job_id']:
            job = self.repo.one('select * from public.sales_field_jobs where id=%s', (row['field_job_id'],))
            require(job and job['status'] != 'cancelled', 'Linked field job is cancelled.')
            if order:
                require(order.get('shopId') in job['shop_ids'], 'Field job no longer includes this customer.')
        if row['invoice_id']:
            inv = self.repo.master('invoice', row['invoice_id'])
            require(inv.get('manufacturingOrder') == row['sales_order_id'] and inv.get('status') not in {'Cancelled', 'Void'}, 'Linked invoice is no longer valid.')
        for item in items:
            remaining = item['quantity']-item['moved_quantity']
            if remaining <= 0:
                continue
            source = self.repo.master(item['kind'], item['reference_id'])
            if row['direction'] == 'inward':
                if item['original_item_id']:
                    original = self.repo.one('select * from public.gate_pass_items where id=%s for update', (item['original_item_id'],))
                    require(remaining <= original['moved_quantity']-original['returned_quantity']-original['written_off_quantity'], 'Original outstanding quantity changed.')
                if row['type_code'] == 'customer_return':
                    require(order and order.get('status') in {'Dispatched', 'Delivered'}, 'Customer returns require a dispatched order.')
                    require(item['kind'] == 'good' and item['reference_id'] in order.get('serials', []), 'Return the exact serials from the sales order.')
                    prior = self.repo.one('''select 1 from public.gate_pass_items i join public.gate_passes p on p.id=i.pass_id
                      where p.id<>%s and p.type_code='customer_return' and i.reference_id=%s and i.moved_quantity>0 limit 1''', (row['id'], item['reference_id']))
                    require(not prior, 'This customer serial has already returned.')
                continue
            # Reserve against all submitted live passes and actual gate movements. Gate
            # reservations are separate from, and never pretend to be, inventory postings.
            used = self.repo.one('''select coalesce(sum(case when p.status in ('REJECTED','CANCELLED','EXPIRED','COMPLETED') or p.valid_until<=now()
                  then i.moved_quantity-i.returned_quantity else i.quantity-i.returned_quantity end),0) as quantity
                from public.gate_pass_items i join public.gate_passes p on p.id=i.pass_id
                where p.id<>%s and p.direction='outward' and p.status<>'DRAFT' and i.kind=%s and i.reference_id=%s''',
                (row['id'], item['kind'], item['reference_id']))['quantity']
            if item['kind'] == 'good':
                require(order and source.get('orderId') == row['sales_order_id'] and item['reference_id'] in order.get('serials', []), 'Serial must be allocated to the linked sales order.')
                require(source.get('qc') == 'Pass' and source.get('status') in {'Allocated', 'Dispatched'}, 'Serial is not quality-released allocated stock.')
                require(order.get('status') in {'Packed', 'Dispatched'}, 'Pack the linked shipment before gate verification.')
                available = Decimal(1)
            elif item['kind'] == 'material':
                available = Decimal(str(source.get('onHand', 0))) - Decimal(str(source.get('reserved', 0)))
            elif item['kind'] == 'sheet':
                require(source.get('status') == 'Available', 'The physical sheet is unavailable or reserved for cutting.')
                available = Decimal(1)
            elif item['kind'] == 'asset':
                require(row['type_code'] in {'returnable_outward', 'nonreturnable_outward', 'branch_transfer', 'subcontract_outward'}, 'This movement type cannot move an asset.')
                require(source.get('status') != 'Running', 'Stop the machine before authorizing its removal.')
                available = Decimal(1)
            else:
                require(False, 'Outward products must use existing physical serials, not catalog quantities.')
            require(item['quantity'] + used <= available, f'Insufficient uncommitted stock for {item["reference_id"]}. Earlier gate movements may require inventory reconciliation.')

    def action(self, ident, body: ActionInput):
        self.repo.lock_workspace()
        row = self.get(ident, True)
        approvals = self.repo.approvals(ident)
        authorize_action(self.actor, row, body.action, approvals)
        items = self.repo.items(ident)
        action, old, updates = body.action, row['status'], {}
        require(action in {'exception', 'resolve_exception', 'cancel'} or not row['exception_open'], 'Resolve the security exception before continuing.')
        if action == 'submit':
            policy = self.repo.one('select * from public.gate_pass_types where code=%s and enabled', (row['type_code'],))
            require(policy, 'This pass type is disabled.')
            require(not policy['require_document'] or row['document_reference'] or self.repo.one('select 1 from public.gate_pass_attachments where pass_id=%s', (ident,)), 'A supporting document reference or attachment is required.')
            require(not policy['require_invoice'] or row['invoice_id'], 'An existing linked invoice is required.')
            self.validate_stock(row, items)
            roles = list(policy['approval_roles'])
            if row['declared_value'] >= policy['high_value_threshold'] and 'Factory Manager' not in roles:
                roles.append('Factory Manager')
            updates.update(status='PENDING_WAREHOUSE_VERIFICATION', approval_roles=roles, allow_partial=policy['allow_partial'])
        elif action == 'verify':
            require(all(body.checks.get(k) for k in ('items', 'quantities', 'serials', 'documents')), 'Complete all warehouse checks.')
            self.validate_stock(row, items)
            self.repo.insert('gate_pass_verifications', dict(pass_id=ident, actor_id=self.actor['id'], checks=body.checks, note=body.reason))
            updates.update(status='PENDING_APPROVAL', verified_by=self.actor['id'])
        elif action in {'approve', 'reject'}:
            if action == 'reject':
                require(len(body.reason) >= 5, 'Give a reason for rejection.', 422)
            else:
                self.validate_stock(row, items)
            self.repo.insert('gate_pass_approvals', dict(pass_id=ident, step=len(approvals)+1, actor_id=self.actor['id'], role=self.actor['role'], decision='APPROVED' if action == 'approve' else 'REJECTED', reason=body.reason))
            updates['status'] = 'REJECTED' if action == 'reject' else ('APPROVED' if len(approvals)+1 == len(row['approval_roles']) else 'PENDING_APPROVAL')
        elif action == 'cancel':
            require(len(body.reason) >= 5, 'Give a reason for cancellation.', 422)
            updates.update(status='CANCELLED', token_hash=None)
        elif action == 'ready':
            self.validate_stock(row, items)
            updates['status'] = 'READY_AT_GATE'
        elif action in {'inspect', 'confirm'}:
            require(body.checkpoint_id == row['checkpoint_id'], 'Wrong checkpoint.')
            cp = self.repo.one('select * from public.gate_checkpoints where id=%s and active', (body.checkpoint_id,))
            require(cp and cp['direction'] in {'both', row['direction']}, 'Checkpoint is unavailable for this direction.')
            require(datetime.now(timezone.utc) >= row['expected_at'], 'The movement validity window has not started.')
            self.validate_stock(row, items)
            if action == 'inspect':
                # Inspection is server-side verification even when using a manually selected pass.
                updates.update(status='UNDER_GATE_INSPECTION', inspected_by=self.actor['id'])
            else:
                require(body.token and row['token_hash'] and secrets.compare_digest(token_hash(body.token), row['token_hash']), 'This confirmation token is invalid or already used.')
                require(all(body.checks.get(k) is True for k in CHECKS), 'Complete every physical inspection check.')
                require(set(body.quantities).issubset({i['id'] for i in items}), 'Unknown item in movement quantities.', 422)
                quantities = {i['id']: body.quantities.get(i['id'], Decimal(0)) for i in items}
                require(any(q > 0 for q in quantities.values()), 'Enter at least one movement quantity.', 422)
                for i in items:
                    q = quantities[i['id']]
                    require(q <= i['quantity']-i['moved_quantity'], 'Movement exceeds the remaining authorized quantity.')
                    require(i['kind'] not in {'good', 'sheet', 'asset'} or q in (0, 1), 'Serials cannot move in fractions.')
                    require(row['allow_partial'] or q == i['quantity']-i['moved_quantity'], 'This policy requires a complete movement.')
                movement = new_id('GM')
                self.repo.insert('gate_pass_movements', dict(id=movement, pass_id=ident, actor_id=self.actor['id'], checkpoint_id=body.checkpoint_id, direction=row['direction'], generation=row['token_generation'], checks=body.checks, quantities={k:str(v) for k,v in quantities.items()}))
                for item in items:
                    q = quantities[item['id']]
                    if not q:
                        continue
                    self.repo.db.execute('update public.gate_pass_items set moved_quantity=moved_quantity+%s where id=%s', (q, item['id']))
                    if item['original_item_id']:
                        self.repo.db.execute('update public.gate_pass_items set returned_quantity=returned_quantity+%s where id=%s', (q, item['original_item_id']))
                        self.repo.insert('gate_pass_returns', dict(original_item_id=item['original_item_id'], inward_pass_id=ident, movement_id=movement, quantity=q, condition=item['condition'], actor_id=self.actor['id']))
                        self.repo.audit(self.actor, 'RETURN_RECEIVED', row['parent_pass_id'], details={'inward_pass_id': ident, 'quantity': str(q), 'item': item['original_item_id']})
                complete = all(quantities[i['id']] == i['quantity']-i['moved_quantity'] for i in items)
                updates.update(status='COMPLETED' if complete else 'READY_AT_GATE', token_hash=None, inspected_by=None)
                if row['field_job_id']:
                    # Records the gate handoff; deliberately never starts a tracking session.
                    job = self.repo.one('select * from public.sales_field_jobs where id=%s', (row['field_job_id'],))
                    session = self.repo.one("select id from public.sales_tracking_sessions where job_id=%s and status='active' order by started_at desc limit 1", (job['id'],))
                    self.repo.insert('sales_tracking_events', dict(employee_id=job['salesman_id'], job_id=job['id'],
                        session_id=session['id'] if session else None,
                        event_type='gate_exit' if row['direction'] == 'outward' else 'gate_entry',
                        details={'pass_id':ident, 'number':row['number'], 'movement_id':movement}))
                    if row['direction'] == 'outward' and any(quantities.values()):
                        destination_lat = destination_lon = None
                        if row['sales_order_id']:
                            order = self.repo.master('sales_order', row['sales_order_id'])
                            shop_id = order.get('shopId') or order.get('shop_id')
                            shop_row = self.repo.one("select payload->'manufacturing'->'shops' as shops from public.erp_state where id='main'")
                            for shop in (shop_row or {}).get('shops') or []:
                                if str(shop.get('id')) == str(shop_id):
                                    try:
                                        candidate_lat = float(shop.get('latitude', shop.get('lat')))
                                        candidate_lon = float(shop.get('longitude', shop.get('lng', shop.get('lon'))))
                                        if -90 <= candidate_lat <= 90 and -180 <= candidate_lon <= 180:
                                            destination_lat, destination_lon = candidate_lat, candidate_lon
                                    except (TypeError, ValueError):
                                        pass
                                    break
                        shipment_id = new_id('SHIP')
                        created = self.repo.one('''insert into public.shipment_tracking
                            (id,gate_pass_id,sales_order_id,field_job_id,tracking_session_id,assigned_employee_id,
                             destination,destination_latitude,destination_longitude,vehicle_number,shipment_status,tracking_status)
                            values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'IN_TRANSIT',%s)
                            on conflict(gate_pass_id) do update set
                              tracking_session_id=coalesce(public.shipment_tracking.tracking_session_id,excluded.tracking_session_id),
                              shipment_status=case when public.shipment_tracking.shipment_status='DISPATCHED' then 'IN_TRANSIT' else public.shipment_tracking.shipment_status end,
                              updated_at=now()
                            returning id''',
                            (shipment_id, ident, row['sales_order_id'], job['id'], session['id'] if session else None,
                             job['salesman_id'], row['destination'], destination_lat, destination_lon,
                             row['vehicle_number'], 'LIVE' if session else 'AWAITING_LOCATION'))
                        self.repo.insert('sales_tracking_events', dict(employee_id=job['salesman_id'], job_id=job['id'],
                            session_id=session['id'] if session else None, event_type='shipment_dispatched',
                            details={'shipment_id':created['id'], 'pass_id':ident, 'number':row['number'], 'movement_id':movement}))
        elif action in {'exception', 'resolve_exception'}:
            require(len(body.reason) >= 5, 'Explain the security exception or resolution.', 422)
            require(not row['exception_open'] if action == 'exception' else row['exception_open'], 'Exception is already in this state.')
            updates.update(exception_open=action == 'exception', token_hash=None)
            if row['status'] == 'UNDER_GATE_INSPECTION':
                updates.update(status='READY_AT_GATE', inspected_by=None)
        elif action == 'write_off':
            require(len(body.reason) >= 10, 'Document the reason for the authorized write-off.', 422)
            require(set(body.quantities).issubset({i['id'] for i in items}), 'Unknown item.', 422)
            require(any(q > 0 for q in body.quantities.values()), 'Enter quantities to write off.', 422)
            for item in items:
                q = body.quantities.get(item['id'], Decimal(0))
                require(q <= item['moved_quantity']-item['returned_quantity']-item['written_off_quantity'], 'Write-off exceeds outstanding quantity.')
                if q:
                    self.repo.db.execute('update public.gate_pass_items set written_off_quantity=written_off_quantity+%s where id=%s', (q, item['id']))
                    self.repo.insert('gate_pass_returns', dict(original_item_id=item['id'], quantity=q, condition='Written off', written_off=True, actor_id=self.actor['id'], reason=body.reason))
            updates['token_hash'] = None
        self.repo.update(ident, updates)
        self.repo.audit(self.actor, action.upper(), ident, old, updates.get('status', old), {'reason':body.reason, 'quantities':{k:str(v) for k,v in body.quantities.items()}})
        return self.detail(ident)

    def issue_token(self, ident):
        self.repo.lock_workspace()
        row = self.get(ident, True)
        require(self.actor['id'] == row['requester_id'] or self.actor['role'] in WAREHOUSE | SECURITY | MANAGEMENT or (self.actor['role'] in {'Salesman', 'Sales Officer'} and row['field_job_id']), 'You cannot issue this pass QR.', 403)
        require(effective_status(row) in {'APPROVED', 'READY_AT_GATE', 'UNDER_GATE_INSPECTION'} and not row['exception_open'], 'This pass is not eligible for a QR.')
        require(row['status'] != 'UNDER_GATE_INSPECTION' or row['inspected_by'] == self.actor['id'], 'The inspecting officer controls the current confirmation token.', 403)
        token = secrets.token_urlsafe(32)
        self.repo.update(ident, {'token_hash':token_hash(token), 'token_generation':row['token_generation']+1})
        self.repo.audit(self.actor, 'QR_ISSUED', ident, row['status'], row['status'])
        return {'token':token, 'qr_payload':'orbit-gate:'+token, 'number':row['number'], 'valid_until':row['valid_until']}

    def scan(self, body):
        require(self.actor['role'] in SECURITY, 'Security role required.', 403)
        self.repo.lock_workspace()
        count = self.repo.one("select count(*) as n from public.gate_pass_scan_logs where actor_id=%s and created_at>now()-interval '1 minute'", (self.actor['id'],))['n']
        row, reason = None, ''
        try:
            require(count < 60, 'Too many scans. Wait one minute.', 429)
            if body.code.startswith('GP-'):
                row = self.repo.one('select * from public.gate_passes where number=%s', (body.code.upper(),))
            else:
                raw = body.code.removeprefix('orbit-gate:')
                row = self.repo.one('select * from public.gate_passes where token_hash=%s', (token_hash(raw),))
            require(row, 'Unknown or revoked QR / pass number.', 404)
            authorize_action(self.actor, row, 'confirm' if row['status'] == 'UNDER_GATE_INSPECTION' else 'inspect', self.repo.approvals(row['id']))
            require(row['checkpoint_id'] == body.checkpoint_id and row['direction'] == body.direction, 'Wrong checkpoint or movement direction.')
            cp = self.repo.one('select * from public.gate_checkpoints where id=%s and active', (body.checkpoint_id,))
            require(cp and cp['direction'] in {'both', body.direction}, 'Checkpoint is inactive or has the wrong direction.')
            require(not row['exception_open'], 'A security exception blocks this pass.')
            require(datetime.now(timezone.utc) >= row['expected_at'], 'The validity window has not started.')
            self.validate_stock(row, self.repo.items(row['id']))
        except HTTPException as exc:
            reason = exc.detail
        self.repo.insert('gate_pass_scan_logs', dict(pass_id=row['id'] if row else None, actor_id=self.actor['id'], checkpoint_id=body.checkpoint_id, direction=body.direction, accepted=not reason, reason=reason or 'Verified; physical inspection still required'))
        # Return invalid attempts normally so their audit record commits as well.
        return {'valid':not reason, 'reason':reason, 'pass':self.detail(row['id']) if row and not reason else None}

    def attach(self, ident, body):
        self.repo.lock_workspace()
        row = self.get(ident, True)
        require(row['requester_id'] == self.actor['id'] and effective_status(row) == 'DRAFT', 'Attachments can only be added to your draft.', 403)
        try:
            content = base64.b64decode(body.content_base64, validate=True)
        except Exception:
            raise HTTPException(422, 'Invalid attachment encoding.')
        require(len(content) <= 5242880, 'Maximum attachment size is 5 MB.', 413)
        signature = {'application/pdf':b'%PDF-', 'image/png':b'\x89PNG\r\n\x1a\n', 'image/jpeg':b'\xff\xd8\xff'}[body.mime_type]
        require(content.startswith(signature), 'The attachment content does not match its file type.', 422)
        count = self.repo.one('select count(*) as n from public.gate_pass_attachments where pass_id=%s', (ident,))['n']
        require(count < 10, 'Maximum 10 attachments per pass.')
        attachment = new_id('GA')
        self.repo.insert('gate_pass_attachments', dict(id=attachment, pass_id=ident, filename=body.filename, mime_type=body.mime_type, content=content, uploaded_by=self.actor['id']))
        self.repo.audit(self.actor, 'ATTACHMENT_ADDED', ident, details={'filename':body.filename})
        return {'id':attachment}
