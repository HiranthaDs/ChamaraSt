alter table public.sales_tracking_sessions
  add column if not exists device_info jsonb not null default '{}'::jsonb;
create index if not exists idx_sales_stops_open_session
  on public.sales_detected_stops(session_id,started_at) where ended_at is null;
