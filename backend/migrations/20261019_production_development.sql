-- Add workflow metadata to existing orders; never duplicate stock or order truth.
create table public.production_job_management (
 production_order_id text primary key references public.production_orders(id),
 status text not null default 'Backlog' check(status in ('Backlog','Pending Approval','Ready for Production','In Progress','Blocked / On Hold','Quality Inspection','Production Completed','Ready for Dispatch','Dispatched','Closed')),
 supervisor_id text references public.employees(id),
 dispatch_required boolean not null default false,
 sales_order_id text references public.sales_orders(id),
 priority text not null default 'Normal' check(priority in ('Low','Normal','High','Urgent')),
 planned_start date, due_date date, approved_by text references public.employees(id),
 specification jsonb not null default '{}', reconciled_by text references public.employees(id),
 reconciliation_note text, closed_at timestamptz, version integer not null default 1,
 created_at timestamptz not null default clock_timestamp(), updated_at timestamptz not null default clock_timestamp(),
 check(due_date >= planned_start), check(not dispatch_required or sales_order_id is not null)
);
create table public.production_job_tasks (
 id text primary key, production_order_id text not null references public.production_orders(id),
 parent_task_id text references public.production_job_tasks(id), title text not null, description text not null default '',
 assigned_employee_id text references public.employees(id), supervisor_id text references public.employees(id),
 priority text not null default 'Normal', stage text,
 status text not null default 'TODO' check(status in ('TODO','READY','IN_PROGRESS','BLOCKED','PENDING_REVIEW','COMPLETED','CANCELLED')),
 planned_start date, due_date date, estimated_hours numeric not null default 0 check(estimated_hours >= 0),
 actual_hours numeric not null default 0 check(actual_hours >= 0),
 checklist jsonb not null default '[]', approval_required boolean not null default true,
 actual_start timestamptz, completed_at timestamptz, completed_by text references public.employees(id),
 approved_by text references public.employees(id), version integer not null default 1,
 created_at timestamptz not null default clock_timestamp(), updated_at timestamptz not null default clock_timestamp(),
 check(parent_task_id is distinct from id), check(due_date >= planned_start)
);
create table public.production_task_dependencies (
 task_id text not null references public.production_job_tasks(id), depends_on_task_id text not null references public.production_job_tasks(id),
 primary key(task_id,depends_on_task_id), check(task_id <> depends_on_task_id)
);
create table public.production_dependency_exceptions (
 id text primary key, task_id text not null references public.production_job_tasks(id),
 requested_by text not null references public.employees(id), reason text not null,
 approved_by text references public.employees(id), approved_at timestamptz, created_at timestamptz not null default clock_timestamp(),
 check(approved_by is distinct from requested_by)
);
create table public.production_job_blockers (
 id text primary key, production_order_id text not null references public.production_orders(id),
 task_id text references public.production_job_tasks(id), blocker_type text not null, description text not null,
 severity text not null check(severity in ('Low','Medium','High','Critical')),
 reported_by text not null references public.employees(id), assigned_to text not null references public.employees(id),
 expected_resolution date, reported_at timestamptz not null default clock_timestamp(), resolved_at timestamptz, resolution text
);
create table public.product_proposals (
 id text primary key, title text not null, proposed_product_name text not null,
 proposed_by text not null references public.employees(id), reviewer_id text references public.employees(id),
 priority text not null default 'Normal', status text not null default 'Ideas',
 current_version integer not null default 1, version integer not null default 1,
 product_id text references public.products(id), created_at timestamptz not null default clock_timestamp(), updated_at timestamptz not null default clock_timestamp(),
 check(status in ('Ideas','Submitted','Under Review','Feasibility Study','Design & Costing','Prototype Development','Prototype Testing','Awaiting Final Approval','Approved for Production','Launched','Rejected / Archived'))
);
create table public.product_proposal_versions (
 id text primary key, proposal_id text not null references public.product_proposals(id), version_number integer not null,
 specifications jsonb not null, change_summary text not null, effective_date date,
 created_by text not null references public.employees(id), created_at timestamptz not null default clock_timestamp(), unique(proposal_id,version_number)
);
create table public.product_proposal_reviews (
 id text primary key, proposal_id text not null references public.product_proposals(id), version_id text not null references public.product_proposal_versions(id),
 review_stage text not null, reviewer_id text not null references public.employees(id), decision text not null check(decision in ('Approved','Changes requested','Rejected')),
 comments text not null, created_at timestamptz not null default clock_timestamp()
);
create table public.product_proposal_cost_estimates (
 id text primary key, proposal_id text not null references public.product_proposals(id), version_id text not null references public.product_proposal_versions(id),
 name text not null, costs jsonb not null, total_cost bigint not null check(total_cost>=0), estimated_selling_price bigint not null check(estimated_selling_price>=0),
 estimated_by text not null references public.employees(id), created_at timestamptz not null default clock_timestamp()
);
create table public.product_proposal_prototypes (
 id text primary key, proposal_id text not null references public.product_proposals(id), version_id text not null references public.product_proposal_versions(id),
 production_order_id text not null unique references public.production_orders(id), status text not null default 'Planned',
 created_at timestamptz not null default clock_timestamp()
);
create table public.product_prototype_tests (
 id text primary key, prototype_id text not null references public.product_proposal_prototypes(id),
 inspector_id text not null references public.employees(id), result text not null check(result in ('Pass','Fail','Changes required')),
 findings text not null, created_at timestamptz not null default clock_timestamp()
);
create table public.production_workflow_activity (
 id text primary key, production_order_id text references public.production_orders(id), proposal_id text references public.product_proposals(id),
 task_id text references public.production_job_tasks(id), actor_id text not null references public.employees(id),
 action text not null, details jsonb not null default '{}', created_at timestamptz not null default clock_timestamp(),
 check((production_order_id is null) <> (proposal_id is null))
);
create table public.production_workflow_documents (
 id text primary key, production_order_id text references public.production_orders(id), proposal_id text references public.product_proposals(id),
 filename text not null, mime_type text not null, content bytea not null, uploaded_by text not null references public.employees(id),
 created_at timestamptz not null default clock_timestamp(), check(octet_length(content)<=5242880),
 check((production_order_id is null) <> (proposal_id is null))
);
create table public.production_workflow_config (
 id text primary key check(id='main'), config jsonb not null, updated_at timestamptz not null default clock_timestamp()
);
create index production_tasks_order on public.production_job_tasks(production_order_id,status);
create index production_tasks_employee on public.production_job_tasks(assigned_employee_id,due_date);
create index production_blockers_open on public.production_job_blockers(production_order_id) where resolved_at is null;
create index production_activity_order on public.production_workflow_activity(production_order_id,created_at);
create index production_activity_proposal on public.production_workflow_activity(proposal_id,created_at);
create index proposal_review_version on public.product_proposal_reviews(version_id,review_stage,created_at);
create index proposal_prototype_version on public.product_proposal_prototypes(version_id);

do $$ declare t text; begin
 foreach t in array array['production_job_management','production_job_tasks','production_task_dependencies','production_dependency_exceptions','production_job_blockers','product_proposals','product_proposal_versions','product_proposal_reviews','product_proposal_cost_estimates','product_proposal_prototypes','product_prototype_tests','production_workflow_activity','production_workflow_documents','production_workflow_config'] loop
  execute format('alter table public.%I enable row level security',t);
  execute format('revoke all on public.%I from anon,authenticated',t);
  execute format('grant select,insert,update,delete on public.%I to service_role',t);
  execute format('create trigger workflow_audit after insert or update or delete on public.%I for each row execute function public.capture_erp_row_change()',t);
 end loop;
end $$;

-- Retain historical versions and decisions, including through direct SQL updates.
create function public.reject_workflow_history_change() returns trigger language plpgsql as $$
begin raise exception 'Workflow history is append-only'; end $$;
do $$ declare t text; begin
 foreach t in array array['product_proposal_versions','product_proposal_reviews','product_proposal_cost_estimates','product_prototype_tests','production_workflow_activity'] loop
  execute format('create trigger immutable_history before update or delete on public.%I for each row execute function public.reject_workflow_history_change()',t);
 end loop;
end $$;

-- Reject stale snapshot clients after prototype/product creation rather than losing records.
alter function public.save_erp_state(jsonb) rename to save_erp_state_before_development;
create function public.save_erp_state(next_state jsonb) returns jsonb language plpgsql security definer set search_path=public as $$
declare current_state jsonb; previous_job jsonb; incoming_job jsonb; previous_product jsonb; incoming_product jsonb; previous_good jsonb; incoming_good jsonb;
begin
 select state into current_state from public.erp_state where id='main' for update;
 if coalesce(current_setting('orbit.workflow_write',true),'') <> 'yes'
    and coalesce(current_state->>'workflowRevision','0') <> coalesce(next_state->>'workflowRevision','0') then
  raise exception 'ERP records changed in Product Development. Refresh before saving.' using errcode='40001';
 end if;
 if coalesce(current_setting('orbit.workflow_write',true),'') <> 'yes' then
  for previous_job in select payload from public.production_orders where id in (select production_order_id from public.production_job_management) loop
   select value into incoming_job from jsonb_array_elements(next_state->'manufacturing'->'jobs') where value->>'id'=previous_job->>'id';
   if incoming_job is distinct from previous_job then
    raise exception 'Managed production orders must use the production workflow API' using errcode='42501';
   end if;
  end loop;
  for previous_product in select payload from public.products where payload ? 'proposalId' loop
   select value into incoming_product from jsonb_array_elements(next_state->'manufacturing'->'products') where value->>'id'=previous_product->>'id';
   if incoming_product is distinct from previous_product then
    raise exception 'Engineering products must use approved proposal revisions' using errcode='42501';
   end if;
  end loop;
  for previous_good in select payload from public.finished_goods where payload->>'jobId' in (select production_order_id from public.production_job_management) loop
   select value into incoming_good from jsonb_array_elements(next_state->'manufacturing'->'goods') where value->>'id'=previous_good->>'id';
   if (incoming_good - 'status' - 'orderId' - 'history') is distinct from (previous_good - 'status' - 'orderId' - 'history')
      or (previous_good->>'status'='Receiving' and incoming_good is distinct from previous_good) then
    raise exception 'Managed goods receipt and specifications must use the manufacturing workflow API' using errcode='42501';
   end if;
  end loop;
  for incoming_job in select value from jsonb_array_elements(next_state->'manufacturing'->'jobs') loop
   if not exists(select 1 from public.production_orders where id=incoming_job->>'id') and exists(select 1 from public.products where id=incoming_job->>'productId' and payload->>'status'='Development') then
    raise exception 'Development products require an approved prototype workflow' using errcode='42501';
   end if;
  end loop;
 end if;
 return public.save_erp_state_before_development(next_state);
end $$;
revoke all on function public.save_erp_state_before_development(jsonb) from public,anon,authenticated;
revoke all on function public.save_erp_state(jsonb) from public,anon,authenticated;
grant execute on function public.save_erp_state(jsonb) to service_role;
