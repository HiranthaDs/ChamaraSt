-- Keep operational visit coordinates in their purpose-built table, but exclude them
-- from generalized before/after audit snapshots going forward.
create or replace function public.capture_erp_row_change()
returns trigger language plpgsql security definer set search_path=public as $$
declare old_row jsonb; new_row jsonb; row_id text;
begin
  if tg_op = 'UPDATE' and (to_jsonb(new) - 'updated_at') = (to_jsonb(old) - 'updated_at') then
    return new;
  end if;
  if tg_op <> 'INSERT' then
    old_row := to_jsonb(old) - 'content' - 'token_hash' - 'latitude' - 'longitude';
  end if;
  if tg_op <> 'DELETE' then
    new_row := to_jsonb(new) - 'content' - 'token_hash' - 'latitude' - 'longitude';
  end if;
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

revoke all on function public.capture_erp_row_change() from public, anon, authenticated;
