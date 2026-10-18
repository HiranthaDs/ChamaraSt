-- Append-only record of row changes across the shared ERP schema. GPS point rows
-- and private file contents are intentionally excluded from this broad audit log.
create table if not exists public.erp_audit_events (
  event_id bigint generated always as identity primary key,
  occurred_at timestamptz not null default now(),
  actor_id text,
  actor_role text,
  actor_source text not null default 'system',
  table_name text not null,
  action text not null check (action in ('INSERT','UPDATE','DELETE')),
  record_id text,
  before_data jsonb,
  after_data jsonb,
  transaction_id bigint not null default txid_current()
);

create table if not exists public.erp_notifications (
  id text primary key,
  recipient_employee_id text not null,
  recipient_role text,
  title text not null,
  message text not null,
  entity_type text,
  entity_id text,
  created_by_employee_id text,
  created_by_role text,
  created_at timestamptz not null default now(),
  read_at timestamptz,
  acknowledged_at timestamptz,
  acknowledgement_note text,
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_erp_audit_entity_time
  on public.erp_audit_events(table_name, record_id, occurred_at desc);
create index if not exists idx_erp_audit_actor_time
  on public.erp_audit_events(actor_id, occurred_at desc);
create index if not exists idx_erp_notifications_recipient
  on public.erp_notifications(recipient_employee_id, created_at desc);

alter table public.erp_audit_events enable row level security;
alter table public.erp_notifications enable row level security;
revoke all on public.erp_audit_events, public.erp_notifications from anon, authenticated;
grant select, insert, update on public.erp_notifications to service_role;
grant select on public.erp_audit_events to service_role;
grant usage, select on sequence public.erp_audit_events_event_id_seq to service_role;

create or replace function public.prevent_erp_audit_mutation()
returns trigger language plpgsql as $$
begin
  raise exception 'ERP audit events are append-only';
end $$;

drop trigger if exists erp_audit_events_immutable on public.erp_audit_events;
create trigger erp_audit_events_immutable
before update or delete on public.erp_audit_events
for each row execute function public.prevent_erp_audit_mutation();

create or replace function public.capture_erp_row_change()
returns trigger language plpgsql security definer set search_path=public as $$
declare old_row jsonb; new_row jsonb; row_id text;
begin
  if tg_op = 'UPDATE' and (to_jsonb(new) - 'updated_at') = (to_jsonb(old) - 'updated_at') then
    return new;
  end if;
  if tg_op <> 'INSERT' then old_row := to_jsonb(old) - 'content' - 'token_hash'; end if;
  if tg_op <> 'DELETE' then new_row := to_jsonb(new) - 'content' - 'token_hash'; end if;
  row_id := coalesce(new_row->>'id', old_row->>'id');
  insert into public.erp_audit_events(actor_id, actor_role, actor_source, table_name,
      action, record_id, before_data, after_data)
  values(nullif(current_setting('orbit.actor_id', true), ''),
      nullif(current_setting('orbit.actor_role', true), ''),
      coalesce(nullif(current_setting('orbit.actor_source', true), ''), 'system'),
      tg_table_name, tg_op, row_id, old_row, new_row);
  if tg_op = 'DELETE' then return old; end if;
  return new;
end $$;

-- Log changes to canonical business records. High-volume location coordinates and
-- attachment bytes are excluded; their purpose-built event tables remain authoritative.
do $$
declare t text;
begin
  foreach t in array array[
    'employees','attendance_records','leave_requests','payroll_runs','invoices','expenses',
    'production_orders','sales_orders','manufacturing_materials','physical_sheets',
    'cutting_plans','cut_parts','products','machines','labor_profiles','purchase_requests',
    'maintenance_tickets','finished_goods','warehouse_bins','sales_shops','stock_movements',
    'manufacturing_cost_events','manufacturing_audit_events','sales_field_jobs',
    'sales_tracking_sessions','sales_tracking_events','sales_job_visits',
    'gate_passes','gate_pass_items','gate_pass_approvals','gate_pass_verifications',
    'gate_pass_movements','gate_pass_returns','gate_pass_audit_logs','gate_pass_scan_logs'
  ] loop
    if to_regclass('public.' || t) is not null then
      execute format('drop trigger if exists erp_row_change_audit on public.%I', t);
      execute format('create trigger erp_row_change_audit after insert or update or delete on public.%I for each row execute function public.capture_erp_row_change()', t);
    end if;
  end loop;
end $$;

revoke all on function public.capture_erp_row_change() from public, anon, authenticated;
revoke all on function public.prevent_erp_audit_mutation() from public, anon, authenticated;
