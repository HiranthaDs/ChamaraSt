-- Existing cutting_plans.payload holds the authoritative layout; no duplicate plan store.
create table public.cutting_plan_versions (
 cutting_plan_id text not null references public.cutting_plans(id),
 version_number integer not null check(version_number>0),
 production_order_id text references public.production_orders(id),
 proposal_id text references public.product_proposals(id),
 changed_by text not null references public.employees(id),
 event text not null, snapshot jsonb not null,
 created_at timestamptz not null default clock_timestamp(),
 primary key(cutting_plan_id,version_number),
 check(production_order_id is null or proposal_id is null)
);
create index cutting_versions_job on public.cutting_plan_versions(production_order_id);
create index cutting_versions_proposal on public.cutting_plan_versions(proposal_id);
alter table public.cutting_plan_versions enable row level security;
revoke all on public.cutting_plan_versions from public,anon,authenticated;
grant select,insert on public.cutting_plan_versions to service_role;

-- Snapshot clients cannot forge managed approvals or mutate issued stock / postings.
alter function public.save_erp_state(jsonb) rename to save_erp_state_before_cutting;
create function public.save_erp_state(next_state jsonb) returns jsonb
language plpgsql security definer set search_path=public as $$
declare current_state jsonb; old_row jsonb; new_row jsonb; collection text;
begin
 select state into current_state from public.erp_state where id='main' for update;
 if coalesce(current_setting('orbit.workflow_write',true),'') <> 'yes' then
  for new_row in select value from jsonb_array_elements(next_state->'manufacturing'->'cuts') where value->>'engine'='mixed-v1' loop
   if not exists(select 1 from public.cutting_plans where id=new_row->>'id' and payload=new_row) then
    raise exception 'Managed cutting plans require the cutting workflow API' using errcode='42501';
   end if;
  end loop;
  foreach collection in array array['cuts','sheets','parts','movements','costs'] loop
   for old_row in select value from jsonb_array_elements(current_state->'manufacturing'->collection)
    where value->>'engine'='mixed-v1'
       or value->>'reservedFor' in (select id from public.cutting_plans where payload->>'engine'='mixed-v1')
       or value->>'cuttingPlanId' in (select id from public.cutting_plans where payload->>'engine'='mixed-v1')
       or value->>'cutId' in (select id from public.cutting_plans where payload->>'engine'='mixed-v1')
       or value->>'reference' in (select id from public.cutting_plans where payload->>'engine'='mixed-v1') loop
    select value into new_row from jsonb_array_elements(next_state->'manufacturing'->collection) where value->>'id'=old_row->>'id';
    if new_row is distinct from old_row then
     raise exception 'Managed cutting stock and postings require the cutting workflow API' using errcode='42501';
    end if;
   end loop;
  end loop;
 end if;
 return public.save_erp_state_before_cutting(next_state);
end $$;
revoke all on function public.save_erp_state_before_cutting(jsonb) from public,anon,authenticated;
revoke all on function public.save_erp_state(jsonb) from public,anon,authenticated;
grant execute on function public.save_erp_state(jsonb) to service_role;
