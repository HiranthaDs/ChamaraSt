from uuid import uuid4
from psycopg import sql
from psycopg.types.json import Jsonb
from .policy import require

MASTER_TABLES = {
    'material': 'manufacturing_materials', 'product': 'products', 'good': 'finished_goods',
    'sheet': 'physical_sheets', 'asset': 'machines', 'sales_order': 'sales_orders',
    'purchase': 'purchase_requests', 'production_order': 'production_orders', 'invoice': 'invoices',
}


class GateRepository:
    def __init__(self, connection):
        self.db = connection

    def one(self, query, params=()):
        return self.db.execute(query, params).fetchone()

    def all(self, query, params=()):
        return self.db.execute(query, params).fetchall()

    def lock_workspace(self):
        # Same lock order as the legacy snapshot writer. Prevent concurrent inventory edits
        # during validation and serialize cross-pass quantities/returns within this module.
        self.db.execute("select id from public.erp_state where id='main' for update")
        self.db.execute('select pg_advisory_xact_lock(2026101701)')

    def master(self, kind, ident):
        require(kind in MASTER_TABLES, 'Unsupported reference type.', 422)
        row = self.one(sql.SQL('select payload from public.{} where id=%s').format(sql.Identifier(MASTER_TABLES[kind])), (ident,))
        require(row is not None, f'{kind.replace("_", " ").title()} {ident} does not exist.', 422)
        return row['payload']

    def insert(self, table, values):
        query = sql.SQL('insert into public.{} ({}) values ({}) returning *').format(
            sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, values)),
            sql.SQL(',').join(sql.Placeholder() for _ in values))
        return self.one(query, tuple(Jsonb(v) if isinstance(v, (dict, list)) else v for v in values.values()))

    def update(self, ident, values):
        query = sql.SQL('update public.gate_passes set {}, version=version+1, updated_at=now() where id=%s returning *').format(
            sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in values))
        return self.one(query, (*[Jsonb(v) if isinstance(v, (dict, list)) else v for v in values.values()], ident))

    def get(self, ident, lock=False):
        row = self.one('select * from public.gate_passes where id=%s' + (' for update' if lock else ''), (ident,))
        require(row is not None, 'Gate pass not found.', 404)
        return row

    def items(self, ident):
        return self.all('select * from public.gate_pass_items where pass_id=%s order by id', (ident,))

    def approvals(self, ident):
        return self.all('select * from public.gate_pass_approvals where pass_id=%s order by step', (ident,))

    def audit(self, actor, action, ident=None, before=None, after=None, details=None):
        self.insert('gate_pass_audit_logs', dict(pass_id=ident, actor_id=actor['id'], action=action,
                                               from_status=before, to_status=after, details=details or {}))

    def scope(self, actor, alias='p'):
        if actor['role'] in {'Salesman', 'Sales Officer'}:
            field = 'salesman_id' if actor['role'] == 'Salesman' else 'sales_officer_id'
            return (f'({alias}.requester_id=%s or exists(select 1 from public.sales_field_jobs j where j.id={alias}.field_job_id and j.{field}=%s))', (actor['id'], actor['id']))
        return 'true', ()

    def can_read(self, actor, row):
        clause, params = self.scope(actor)
        require(self.one(f'select 1 from public.gate_passes p where p.id=%s and {clause}', (row['id'], *params)), 'This pass is outside your assigned work.', 403)

    def list(self, actor):
        clause, params = self.scope(actor)
        return self.all(f'''select p.*, e.name as requester_name, t.name as type_name,
          coalesce((select sum(i.quantity) from public.gate_pass_items i where i.pass_id=p.id),0) as quantity,
          coalesce((select sum(i.moved_quantity) from public.gate_pass_items i where i.pass_id=p.id),0) as moved_quantity,
          coalesce((select sum(i.moved_quantity-i.returned_quantity-i.written_off_quantity) from public.gate_pass_items i where i.pass_id=p.id),0) as outstanding_quantity
          from public.gate_passes p join public.employees e on e.id=p.requester_id
          join public.gate_pass_types t on t.code=p.type_code where {clause} order by p.created_at desc limit 1000''', params)


def new_id(prefix):
    return prefix + '-' + uuid4().hex
