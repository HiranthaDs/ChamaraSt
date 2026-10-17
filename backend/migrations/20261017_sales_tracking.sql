-- Field-sales GPS tracking. Run after backend/schema.sql in Supabase SQL Editor.
-- Uses the existing public.employees IDs; does not create duplicate employees.
create table if not exists public.sales_field_jobs (
  id text primary key,
  salesman_id text not null references public.employees(id),
  sales_officer_id text not null references public.employees(id),
  work_date date not null,
  starts_at text not null,
  ends_at text not null,
  territory text not null,
  instructions text not null default '',
  shop_ids text[] not null default '{}',
  status text not null default 'assigned' check (status in ('assigned','active','completed','cancelled')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_sales_field_jobs_salesman on public.sales_field_jobs(salesman_id,work_date desc);
create index if not exists idx_sales_field_jobs_officer on public.sales_field_jobs(sales_officer_id,work_date desc);
create index if not exists idx_sales_field_jobs_status on public.sales_field_jobs(status,work_date);

create table if not exists public.sales_tracking_sessions (
  id text primary key,
  job_id text not null references public.sales_field_jobs(id),
  employee_id text not null references public.employees(id),
  status text not null check (status in ('active','paused','ended','interrupted')),
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  last_location_at timestamptz,
  last_heartbeat_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(id,job_id)
);
create unique index if not exists idx_sales_one_active_session_per_employee
  on public.sales_tracking_sessions(employee_id) where status='active';
create index if not exists idx_sales_tracking_session_job on public.sales_tracking_sessions(job_id,started_at desc);

create table if not exists public.sales_location_points (
  id bigserial primary key,
  session_id text not null references public.sales_tracking_sessions(id) on delete cascade,
  latitude double precision not null check (latitude between -90 and 90),
  longitude double precision not null check (longitude between -180 and 180),
  accuracy_m real not null check (accuracy_m > 0),
  speed_mps real,
  heading_deg real,
  altitude_m real,
  client_timestamp timestamptz not null,
  server_timestamp timestamptz not null default now(),
  sequence_number bigint not null check (sequence_number >= 0),
  quality_flag text not null default 'good',
  unique(session_id,sequence_number)
);
create index if not exists idx_sales_location_session_time on public.sales_location_points(session_id,client_timestamp);
create index if not exists idx_sales_location_received on public.sales_location_points(server_timestamp);

create table if not exists public.sales_detected_stops (
  id bigserial primary key,
  session_id text not null references public.sales_tracking_sessions(id) on delete cascade,
  started_at timestamptz not null,
  ended_at timestamptz,
  latitude double precision not null,
  longitude double precision not null,
  radius_m real not null,
  duration_seconds integer not null default 0,
  created_at timestamptz not null default now(),
  unique(session_id,started_at)
);
create index if not exists idx_sales_detected_stops_session on public.sales_detected_stops(session_id,started_at);

create table if not exists public.sales_job_visits (
  id text primary key,
  job_id text not null references public.sales_field_jobs(id),
  employee_id text not null references public.employees(id),
  sales_officer_id text not null references public.employees(id),
  shop_id text not null,
  outcome text not null default 'In progress',
  notes text not null default '',
  latitude double precision,
  longitude double precision,
  sales_order_id text,
  checked_in_at timestamptz not null default now(),
  checked_out_at timestamptz,
  updated_at timestamptz not null default now()
);
create index if not exists idx_sales_job_visits_employee on public.sales_job_visits(employee_id,checked_in_at desc);
create index if not exists idx_sales_job_visits_officer on public.sales_job_visits(sales_officer_id,checked_in_at desc);
create index if not exists idx_sales_job_visits_job on public.sales_job_visits(job_id,checked_in_at);
create unique index if not exists idx_sales_one_open_visit_per_shop on public.sales_job_visits(job_id,shop_id) where checked_out_at is null;

create table if not exists public.sales_tracking_events (
  id bigserial primary key,
  session_id text not null references public.sales_tracking_sessions(id) on delete cascade,
  event_type text not null,
  details jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_sales_tracking_events_session on public.sales_tracking_events(session_id,created_at);

create table if not exists public.sales_tracking_settings (
  id text primary key default 'current' check (id='current'),
  stale_after_seconds integer not null default 120 check (stale_after_seconds between 30 and 3600),
  max_accuracy_m integer not null default 100 check (max_accuracy_m between 10 and 5000),
  stop_radius_m integer not null default 50 check (stop_radius_m between 10 and 500),
  stop_duration_seconds integer not null default 300 check (stop_duration_seconds between 60 and 3600),
  retention_days integer not null default 90 check (retention_days between 1 and 3650),
  updated_at timestamptz not null default now()
);
insert into public.sales_tracking_settings(id) values('current') on conflict(id) do nothing;

alter table public.sales_field_jobs enable row level security;
alter table public.sales_tracking_sessions enable row level security;
alter table public.sales_location_points enable row level security;
alter table public.sales_detected_stops enable row level security;
alter table public.sales_job_visits enable row level security;
alter table public.sales_tracking_events enable row level security;
alter table public.sales_tracking_settings enable row level security;
grant select,insert,update,delete on public.sales_field_jobs, public.sales_tracking_sessions,
  public.sales_location_points, public.sales_detected_stops, public.sales_job_visits,
  public.sales_tracking_events, public.sales_tracking_settings to service_role;
grant usage,select on sequence public.sales_location_points_id_seq,
  public.sales_detected_stops_id_seq, public.sales_tracking_events_id_seq to service_role;
