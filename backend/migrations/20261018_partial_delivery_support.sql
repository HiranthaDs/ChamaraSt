-- Allow multiple attributable delivery confirmations for one shipment. The API
-- accumulates quantities under a row lock and only marks full delivery when every
-- gate-exit item quantity reconciles.
alter table public.shipment_delivery_confirmations
  drop constraint if exists shipment_delivery_confirmations_shipment_id_key;
create index if not exists idx_shipment_delivery_latest
  on public.shipment_delivery_confirmations(shipment_id,confirmed_at desc);
