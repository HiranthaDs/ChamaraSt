from uuid import uuid4
from psycopg import sql
from psycopg.types.json import Jsonb
from .policy import require

def ident(prefix):
    return prefix+'-'+uuid4().hex[:12].upper()

class WorkflowRepository:
    def __init__(self, db):
        self.db = db
        self._state = None
        self._config = None
    def one(self, query, args=()):
        return self.db.execute(query,args).fetchone()
    def all(self, query, args=()):
        return self.db.execute(query,args).fetchall()
    def insert(self, table, values):
        query = sql.SQL('insert into public.{} ({}) values ({}) returning *').format(
            sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier,values)),
            sql.SQL(',').join(sql.Placeholder() for _ in values))
        return self.one(query,tuple(Jsonb(v) if isinstance(v,(dict,list)) else v for v in values.values()))
    def update(self, table, key, value, fields):
        query = sql.SQL('update public.{} set {} where {}=%s returning *').format(
            sql.Identifier(table),sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in fields),sql.Identifier(key))
        return self.one(query,tuple(Jsonb(v) if isinstance(v,(dict,list)) else v for v in fields.values())+(value,))
    def lock(self):
        # Lock canonical state before workflow rows, matching the legacy save lock order.
        row = self.one("select state from public.erp_state where id='main' for update")
        require(row,'Initialize the ERP database first.',503)
        self._state = row['state']
        return self._state
    def state(self):
        if self._state is not None:
            return self._state
        row = self.one("select state from public.erp_state where id='main'")
        require(row,'Initialize the ERP database first.',503)
        self._state = row['state']
        return self._state
    def save_state(self, state):
        state['workflowRevision'] = int(state.get('workflowRevision',0))+1
        self.db.execute("select set_config('orbit.workflow_write','yes',true)")
        self.db.execute('select public.save_erp_state(%s)',(Jsonb(state),))
        self._state = state
    def employee(self, employee_id):
        row = self.one('select payload from public.employees where id=%s',(employee_id,))
        require(row and row['payload'].get('status')=='Active','Choose an active HR employee.',422)
        return row['payload']
    def activity(self, actor, action, job=None, proposal=None, task=None, details=None):
        return self.insert('production_workflow_activity',dict(id=ident('WA'),production_order_id=job,proposal_id=proposal,
            task_id=task,actor_id=actor['id'],action=action,details=details or {}))
    def notify(self, actor, recipient, title, entity, entity_id):
        if not recipient or recipient==actor['id']:
            return
        employee = self.employee(recipient)
        self.insert('erp_notifications',dict(id=ident('NOTE'),recipient_employee_id=recipient,recipient_role=employee['role'],
            title=title,message=title,entity_type=entity,entity_id=entity_id,created_by_employee_id=actor['id'],created_by_role=actor['role'],metadata={}))
    def config(self):
        if self._config is not None:
            return self._config
        row = self.one("select config from public.production_workflow_config where id='main'")
        self._config = row['config'] if row else {}
        return self._config
