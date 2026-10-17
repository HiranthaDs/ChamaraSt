-- Additive module; run after schema.sql and 20261017_sales_tracking.sql.
-- A gate handoff can occur before a salesman explicitly starts GPS tracking.
alter table public.sales_tracking_events alter column session_id drop not null;
alter table public.sales_tracking_events add column if not exists job_id text references public.sales_field_jobs(id);
alter table public.sales_tracking_events add column if not exists employee_id text references public.employees(id);
create table if not exists public.gate_pass_types (
 code text primary key, name text not null, direction text not null check(direction in ('inward','outward')),
 return_required boolean not null default false, enabled boolean not null default true,
 require_document boolean not null default true, require_invoice boolean not null default false,
 approval_roles jsonb not null default '["Supervisor"]', high_value_threshold numeric not null default 1000000,
 allow_partial boolean not null default true
);
insert into public.gate_pass_types(code,name,direction,return_required) values
 ('material_inward','Material inward','inward',false),
 ('finished_goods_outward','Finished goods outward','outward',false),
 ('returnable_outward','Returnable outward','outward',true),
 ('returnable_inward','Returnable inward','inward',false),
 ('nonreturnable_outward','Non-returnable outward','outward',false),
 ('supplier_return','Supplier return','outward',false),
 ('branch_transfer','Branch transfer dispatch','outward',false),
 ('branch_receipt','Branch transfer receipt','inward',false),
 ('subcontract_outward','Subcontract outward','outward',true),
 ('customer_return','Customer return inward','inward',false)
 on conflict(code) do nothing;
update public.gate_pass_types set approval_roles='["Supervisor","Factory Manager"]'
 where code='nonreturnable_outward' and approval_roles='["Supervisor"]';
create table if not exists public.gate_checkpoints (
 id text primary key, name text not null, direction text not null default 'both' check(direction in ('both','inward','outward')),
 active boolean not null default true
);
insert into public.gate_checkpoints(id,name) values ('MAIN','Main gate') on conflict do nothing;
create sequence if not exists public.gate_pass_number_seq;
create table if not exists public.gate_passes (
 id text primary key, number text not null unique,
 type_code text not null references public.gate_pass_types(code),
 direction text not null check(direction in ('inward','outward')), return_required boolean not null,
 status text not null default 'DRAFT' check(status in ('DRAFT','PENDING_WAREHOUSE_VERIFICATION','PENDING_APPROVAL','APPROVED','READY_AT_GATE','UNDER_GATE_INSPECTION','COMPLETED','REJECTED','CANCELLED','EXPIRED')),
 requester_id text not null references public.employees(id), requester_department text not null,
 purpose text not null, origin text not null, destination text not null,
 expected_at timestamptz not null, valid_until timestamptz not null, return_due_at timestamptz,
 checkpoint_id text not null references public.gate_checkpoints(id),
 vehicle_number text not null, driver_name text not null, driver_identity text not null default '',
 sales_order_id text references public.sales_orders(id), purchase_id text references public.purchase_requests(id),
 production_order_id text references public.production_orders(id), invoice_id text references public.invoices(id),
 field_job_id text references public.sales_field_jobs(id), parent_pass_id text references public.gate_passes(id),
 document_reference text not null default '', declared_value numeric not null default 0 check(declared_value>=0),
 approval_roles jsonb not null default '[]', allow_partial boolean not null default true,
 verified_by text references public.employees(id), inspected_by text references public.employees(id),
 token_hash text unique, token_generation integer not null default 0, exception_open boolean not null default false,
 version integer not null default 1, created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
 check(valid_until>expected_at), check(not return_required or return_due_at is not null)
);
create table if not exists public.gate_pass_items (
 id text primary key, pass_id text not null references public.gate_passes(id),
 kind text not null check(kind in ('material','product','good','sheet','asset')),
 reference_id text not null, description text not null, unit text not null,
 material_id text references public.manufacturing_materials(id), product_id text references public.products(id),
 good_id text references public.finished_goods(id), sheet_id text references public.physical_sheets(id), asset_id text references public.machines(id),
 quantity numeric(18,3) not null check(quantity>0), moved_quantity numeric(18,3) not null default 0,
 returned_quantity numeric(18,3) not null default 0, written_off_quantity numeric(18,3) not null default 0,
 condition text not null, original_item_id text references public.gate_pass_items(id),
 unique(pass_id,kind,reference_id), check(moved_quantity>=0 and moved_quantity<=quantity),
 check(returned_quantity>=0 and written_off_quantity>=0 and returned_quantity+written_off_quantity<=moved_quantity),
 check(num_nonnulls(material_id,product_id,good_id,sheet_id,asset_id)=1)
);
create table if not exists public.gate_pass_approvals (
 id bigserial primary key, pass_id text not null references public.gate_passes(id),
 step integer not null, actor_id text not null references public.employees(id), role text not null,
 decision text not null check(decision in ('APPROVED','REJECTED')), reason text not null default '', created_at timestamptz not null default now(),
 unique(pass_id,step), unique(pass_id,actor_id)
);
create table if not exists public.gate_pass_verifications (
 id bigserial primary key, pass_id text not null references public.gate_passes(id), actor_id text not null references public.employees(id),
 checks jsonb not null, note text not null, created_at timestamptz not null default now()
);
create table if not exists public.gate_pass_movements (
 id text primary key, pass_id text not null references public.gate_passes(id), actor_id text not null references public.employees(id),
 checkpoint_id text not null references public.gate_checkpoints(id), direction text not null, generation integer not null,
 checks jsonb not null, quantities jsonb not null, created_at timestamptz not null default now(),
 unique(pass_id,generation)
);
create table if not exists public.gate_pass_returns (
 id bigserial primary key, original_item_id text not null references public.gate_pass_items(id),
 inward_pass_id text references public.gate_passes(id), movement_id text references public.gate_pass_movements(id),
 quantity numeric(18,3) not null check(quantity>0), condition text not null, written_off boolean not null default false,
 actor_id text not null references public.employees(id), reason text not null default '', created_at timestamptz not null default now()
);
create table if not exists public.gate_pass_audit_logs (
 id bigserial primary key, pass_id text references public.gate_passes(id), actor_id text not null references public.employees(id),
 action text not null, from_status text, to_status text, details jsonb not null default '{}', created_at timestamptz not null default now()
);
create table if not exists public.gate_pass_scan_logs (
 id bigserial primary key, pass_id text references public.gate_passes(id), actor_id text not null references public.employees(id),
 checkpoint_id text not null, direction text not null, accepted boolean not null, reason text not null, created_at timestamptz not null default now()
);
create table if not exists public.gate_pass_attachments (
 id text primary key, pass_id text not null references public.gate_passes(id), filename text not null, mime_type text not null,
 content bytea not null, uploaded_by text not null references public.employees(id), created_at timestamptz not null default now(),
 check(octet_length(content)<=5242880)
);
create index if not exists gate_pass_status_date on public.gate_passes(status,expected_at);
create index if not exists gate_pass_requester on public.gate_passes(requester_id,created_at desc);
create index if not exists gate_pass_sales_job on public.gate_passes(field_job_id);
create index if not exists gate_pass_parent on public.gate_passes(parent_pass_id);
create index if not exists gate_pass_item_pass on public.gate_pass_items(pass_id);
create index if not exists gate_pass_item_reference on public.gate_pass_items(kind,reference_id);
create index if not exists gate_pass_audit_pass on public.gate_pass_audit_logs(pass_id,created_at);
create index if not exists gate_scan_rate on public.gate_pass_scan_logs(actor_id,created_at);
create index if not exists gate_movement_pass on public.gate_pass_movements(pass_id,created_at);
do $$ declare t text; begin
 foreach t in array array['gate_pass_types','gate_checkpoints','gate_passes','gate_pass_items','gate_pass_approvals',
 'gate_pass_verifications','gate_pass_movements','gate_pass_returns','gate_pass_audit_logs','gate_pass_scan_logs','gate_pass_attachments'] loop
 execute format('alter table public.%I enable row level security',t);
 execute format('revoke all on table public.%I from anon, authenticated',t);
 end loop;
end $$;
