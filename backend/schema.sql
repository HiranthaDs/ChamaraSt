-- Run once in Supabase Dashboard -> SQL Editor. The save function mirrors every
-- frontend collection to its feature table within the same Postgres transaction.
create table if not exists public.erp_state (
  id text primary key check (id = 'main'),
  state jsonb not null check (jsonb_typeof(state) = 'object'),
  revision bigint not null default 1,
  updated_at timestamptz not null default now()
);

-- Queryable HR and Finance columns, with payload retaining the complete UI record.
create table if not exists public.employees (
  id text primary key, payload jsonb not null,
  name text generated always as (payload->>'name') stored,
  email text generated always as (payload->>'email') stored,
  department text generated always as (payload->>'department') stored,
  role text generated always as (payload->>'role') stored,
  status text generated always as (payload->>'status') stored,
  salary numeric generated always as (nullif(payload->>'salary','')::numeric) stored,
  updated_at timestamptz not null default now()
);
create table if not exists public.invoices (
  id text primary key, payload jsonb not null,
  client text generated always as (payload->>'client') stored,
  amount numeric generated always as (nullif(payload->>'amount','')::numeric) stored,
  currency text generated always as (coalesce(payload->>'currency','USD')) stored,
  status text generated always as (payload->>'status') stored,
  updated_at timestamptz not null default now()
);
create table if not exists public.expenses (
  id text primary key, payload jsonb not null,
  employee_id text generated always as (payload->>'employeeId') stored,
  category text generated always as (payload->>'category') stored,
  amount numeric generated always as (nullif(payload->>'amount','')::numeric) stored,
  status text generated always as (payload->>'status') stored,
  updated_at timestamptz not null default now()
);
create table if not exists public.leave_requests (
  id text primary key, payload jsonb not null,
  employee_id text generated always as (payload->>'employeeId') stored,
  start_date text generated always as (payload->>'start') stored,
  end_date text generated always as (payload->>'end') stored,
  status text generated always as (payload->>'status') stored,
  updated_at timestamptz not null default now()
);
create table if not exists public.production_orders (
  id text primary key, payload jsonb not null,
  product_id text generated always as (payload->>'productId') stored,
  quantity numeric generated always as (nullif(payload->>'quantity','')::numeric) stored,
  status text generated always as (payload->>'status') stored,
  updated_at timestamptz not null default now()
);
create table if not exists public.sales_orders (
  id text primary key, payload jsonb not null,
  shop_id text generated always as (payload->>'shopId') stored,
  product_id text generated always as (payload->>'productId') stored,
  quantity integer generated always as (nullif(payload->>'quantity','')::integer) stored,
  status text generated always as (payload->>'status') stored,
  updated_at timestamptz not null default now()
);
create table if not exists public.manufacturing_materials (
  id text primary key, payload jsonb not null,
  name text generated always as (payload->>'name') stored,
  unit text generated always as (payload->>'unit') stored,
  on_hand numeric generated always as (nullif(payload->>'onHand','')::numeric) stored,
  reserved numeric generated always as (nullif(payload->>'reserved','')::numeric) stored,
  updated_at timestamptz not null default now()
);
create table if not exists public.physical_sheets (
  id text primary key, payload jsonb not null,
  material text generated always as (payload->>'material') stored,
  grade text generated always as (payload->>'grade') stored,
  width_mm numeric generated always as (nullif(payload->>'w','')::numeric) stored,
  height_mm numeric generated always as (nullif(payload->>'h','')::numeric) stored,
  status text generated always as (payload->>'status') stored,
  updated_at timestamptz not null default now()
);
-- Separate tables for all remaining feature collections. Each has an indexed
-- record key, status where present, full JSON payload, and last update timestamp.
do $$
declare t text;
begin
  foreach t in array array[
    'attendance_records','payroll_runs','workspace_settings','activity_events',
    'cutting_plans','cut_parts','products','machines','labor_profiles',
    'purchase_requests','maintenance_tickets','finished_goods','warehouse_bins',
    'sales_shops','stock_movements','manufacturing_cost_events','manufacturing_alerts',
    'manufacturing_audit_events','manufacturing_saved_views','manufacturing_preferences'
  ] loop
    execute format('create table if not exists public.%I (
      id text primary key,
      payload jsonb not null,
      status text generated always as (payload->>''status'') stored,
      updated_at timestamptz not null default now()
    )', t);
  end loop;
end $$;

create index if not exists idx_employees_department on public.employees(department);
create index if not exists idx_employees_status on public.employees(status);
create index if not exists idx_invoices_currency_status on public.invoices(currency,status);
create index if not exists idx_leave_employee on public.leave_requests(employee_id);
create index if not exists idx_materials_available on public.manufacturing_materials(on_hand,reserved);
create index if not exists idx_production_status on public.production_orders(status);
create index if not exists idx_sales_status on public.sales_orders(status);

alter table public.erp_state enable row level security;
do $$ declare t text; begin
  foreach t in array array[
    'employees','invoices','expenses','leave_requests','production_orders','sales_orders',
    'manufacturing_materials','physical_sheets','attendance_records','payroll_runs',
    'workspace_settings','activity_events','cutting_plans','cut_parts','products','machines',
    'labor_profiles','purchase_requests','maintenance_tickets','finished_goods','warehouse_bins',
    'sales_shops','stock_movements','manufacturing_cost_events','manufacturing_alerts',
    'manufacturing_audit_events','manufacturing_saved_views','manufacturing_preferences'
  ] loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;

create or replace function public.sync_erp_records(table_name text, rows jsonb)
returns void language plpgsql security definer set search_path = public as $$
begin
  execute format(
    'delete from public.%I target where not exists (select 1 from jsonb_array_elements($1) source(value) where source.value->>''id'' = target.id)',
    table_name
  ) using coalesce(rows, '[]'::jsonb);
  execute format(
    'insert into public.%I (id,payload,updated_at) select source.value->>''id'',source.value,now() from jsonb_array_elements($1) source(value) where source.value->>''id'' is not null on conflict (id) do update set payload=excluded.payload,updated_at=now()',
    table_name
  ) using coalesce(rows, '[]'::jsonb);
end $$;

create or replace function public.json_map_to_rows(source_map jsonb)
returns jsonb language sql immutable as $$
  select coalesce(jsonb_agg(
    case when jsonb_typeof(entry.value)='object'
      then entry.value || jsonb_build_object('id',entry.key)
      else jsonb_build_object('id',entry.key,'value',entry.value)
    end
  ),'[]'::jsonb)
  from jsonb_each(coalesce(source_map,'{}'::jsonb)) entry
$$;

create or replace function public.save_erp_state(next_state jsonb)
returns jsonb language plpgsql security definer set search_path=public as $$
declare m jsonb; saved jsonb;
begin
  if jsonb_typeof(next_state) is distinct from 'object' or jsonb_typeof(next_state->'manufacturing') is distinct from 'object' then
    raise exception 'ERP state must be an object and include manufacturing';
  end if;
  insert into public.erp_state(id,state,revision,updated_at) values('main',next_state,1,now())
  on conflict(id) do update set state=excluded.state,revision=public.erp_state.revision+1,updated_at=now()
  returning to_jsonb(erp_state) into saved;

  perform public.sync_erp_records('employees',coalesce(next_state->'employees','[]'::jsonb));
  perform public.sync_erp_records('attendance_records',public.json_map_to_rows(next_state->'attendance'));
  perform public.sync_erp_records('leave_requests',coalesce(next_state->'leaves','[]'::jsonb));
  perform public.sync_erp_records('payroll_runs',case when jsonb_typeof(next_state->'payroll')='object' then jsonb_build_array(next_state->'payroll'||'{"id":"current"}'::jsonb) else '[]'::jsonb end);
  perform public.sync_erp_records('invoices',coalesce(next_state->'invoices','[]'::jsonb));
  perform public.sync_erp_records('expenses',coalesce(next_state->'expenses','[]'::jsonb));
  perform public.sync_erp_records('workspace_settings',jsonb_build_array(next_state->'settings'||'{"id":"current"}'::jsonb));
  perform public.sync_erp_records('activity_events',coalesce(next_state->'activity','[]'::jsonb));

  m:=next_state->'manufacturing';
  perform public.sync_erp_records('manufacturing_materials',coalesce(m->'materials','[]'::jsonb));
  perform public.sync_erp_records('physical_sheets',coalesce(m->'sheets','[]'::jsonb));
  perform public.sync_erp_records('cutting_plans',coalesce(m->'cuts','[]'::jsonb));
  perform public.sync_erp_records('cut_parts',coalesce(m->'parts','[]'::jsonb));
  perform public.sync_erp_records('products',coalesce(m->'products','[]'::jsonb));
  perform public.sync_erp_records('production_orders',coalesce(m->'jobs','[]'::jsonb));
  perform public.sync_erp_records('machines',coalesce(m->'machines','[]'::jsonb));
  perform public.sync_erp_records('labor_profiles',public.json_map_to_rows(m->'labor'));
  perform public.sync_erp_records('purchase_requests',coalesce(m->'purchases','[]'::jsonb));
  perform public.sync_erp_records('maintenance_tickets',coalesce(m->'maintenance','[]'::jsonb));
  perform public.sync_erp_records('finished_goods',coalesce(m->'goods','[]'::jsonb));
  perform public.sync_erp_records('warehouse_bins',coalesce(m->'bins','[]'::jsonb));
  perform public.sync_erp_records('sales_shops',coalesce(m->'shops','[]'::jsonb));
  perform public.sync_erp_records('sales_orders',coalesce(m->'orders','[]'::jsonb));
  perform public.sync_erp_records('stock_movements',coalesce(m->'movements','[]'::jsonb));
  perform public.sync_erp_records('manufacturing_cost_events',coalesce(m->'costs','[]'::jsonb));
  perform public.sync_erp_records('manufacturing_alerts',public.json_map_to_rows(m->'alerts'));
  perform public.sync_erp_records('manufacturing_audit_events',coalesce(m->'audit','[]'::jsonb));
  perform public.sync_erp_records('manufacturing_saved_views',public.json_map_to_rows(m->'savedViews'));
  perform public.sync_erp_records('manufacturing_preferences',jsonb_build_array(jsonb_build_object(
    'id','current','version',m->'version','actor',m->'actor','preferences',m->'preferences','demoStep',m->'demoStep'
  )));
  return saved;
end $$;

revoke all on table public.erp_state from anon,authenticated;
revoke all on function public.sync_erp_records(text,jsonb) from public,anon,authenticated;
revoke all on function public.json_map_to_rows(jsonb) from public,anon,authenticated;
revoke all on function public.save_erp_state(jsonb) from public,anon,authenticated;
grant select on table public.erp_state to service_role;
grant execute on function public.save_erp_state(jsonb) to service_role;
