-- Shipment monitoring links existing gate passes and field GPS sessions. This module
-- does not create or post a second inventory movement.
create table if not exists public.shipment_tracking (
  id text primary key,
  gate_pass_id text not null unique references public.gate_passes(id),
  sales_order_id text references public.sales_orders(id),
  field_job_id text references public.sales_field_jobs(id),
  tracking_session_id text references public.sales_tracking_sessions(id),
  assigned_employee_id text not null references public.employees(id),
  destination text not null,
  destination_latitude double precision,
  destination_longitude double precision,
  geofence_radius_m integer not null default 100 check(geofence_radius_m between 25 and 1000),
  vehicle_number text not null default '',
  dispatched_at timestamptz not null default now(),
  shipment_status text not null default 'DISPATCHED' check(shipment_status in ('DISPATCHED','IN_TRANSIT','ARRIVAL_DETECTED','DELIVERY_VERIFICATION','DELIVERED','PARTIALLY_DELIVERED','DELIVERY_FAILED','RETURNING','CLOSED')),
  tracking_status text not null default 'AWAITING_LOCATION' check(tracking_status in ('NOT_STARTED','AWAITING_LOCATION','LIVE','STALE','INTERRUPTED','ENDED')),
  last_arrival_event_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_shipment_tracking_employee on public.shipment_tracking(assigned_employee_id,dispatched_at desc);
create index if not exists idx_shipment_tracking_job on public.shipment_tracking(field_job_id,dispatched_at desc);
create index if not exists idx_shipment_tracking_status on public.shipment_tracking(shipment_status,tracking_status);

create table if not exists public.shipment_delivery_confirmations (
  id text primary key,
  shipment_id text not null references public.shipment_tracking(id),
  confirmed_by text not null references public.employees(id),
  recipient_name text not null default '',
  status text not null check(status in ('DELIVERED','PARTIALLY_DELIVERED','DELIVERY_FAILED','RETURNING')),
  quantities jsonb not null default '{}'::jsonb,
  remarks text not null default '',
  confirmed_at timestamptz not null default now(),
  unique(shipment_id)
);
create index if not exists idx_shipment_delivery_actor on public.shipment_delivery_confirmations(confirmed_by,confirmed_at desc);

alter table public.shipment_tracking enable row level security;
alter table public.shipment_delivery_confirmations enable row level security;
revoke all on public.shipment_tracking, public.shipment_delivery_confirmations from anon, authenticated;
grant select,insert,update on public.shipment_tracking, public.shipment_delivery_confirmations to service_role;

drop trigger if exists erp_row_change_audit on public.shipment_tracking;
create trigger erp_row_change_audit after insert or update or delete on public.shipment_tracking
for each row execute function public.capture_erp_row_change();
drop trigger if exists erp_row_change_audit on public.shipment_delivery_confirmations;
create trigger erp_row_change_audit after insert or update or delete on public.shipment_delivery_confirmations
for each row execute function public.capture_erp_row_change();
