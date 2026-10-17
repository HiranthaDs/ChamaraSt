# Live shipment tracking

This extension reuses the existing Salesman browser GPS session, field job, gate pass, employee, and OSM map implementation.

## Operational sequence

1. The Sales Officer assigns the Salesman to their HR reporting team and assigns a field job.
2. Create the existing outward Gate Pass and link the Salesman's field job and sales order. Complete warehouse verification and the configured approvals.
3. Gate Security scans, inspects, and confirms the actual outward movement with the one-use confirmation token. The gate transaction creates one `shipment_tracking` record per Gate Pass only when an outward quantity actually moves. It records the responsible Salesman, order, field job, destination snapshot, vehicle, and gate-exit time. Retrying a gate action cannot create a second shipment for that pass.
4. If that job already has an active browser GPS session, the shipment links to it. Otherwise it displays `IN_TRANSIT / AWAITING_LOCATION` until the assigned Salesman starts the job and grants browser location permission. Starting the existing job links the session; no second GPS collector is started.
5. The Salesman and their Sales Officer can open **My active deliveries** / **Shipment monitoring**. Actual accepted GPS points, quality-filtered recorded route distance, detected stops, last-fix age, accuracy, reported speed, gate pass, destination, and items are shown. Data refreshes every ten seconds. No synthetic position is generated.
6. The Salesman records a recipient and actual per-item received quantities. Partial confirmations can be entered more than once. The backend locks the shipment, accumulates quantities, rejects over-delivery, and allows `DELIVERED` only when all Gate Pass movement quantities reconcile. A recorded arrival alone never closes a shipment.

## Database and API

Apply migrations with `python -m backend.migrate --apply` after the base schema. `20261018_shipment_tracking.sql` creates the shipment and delivery confirmation records; the subsequent partial-delivery migration allows multiple confirmed partial drops. The gate service creates shipment records inside the same database transaction as the confirmed physical movement. Audit triggers cover shipment and delivery records.

Sales tracking APIs:

- `GET /api/sales-tracking/shipments`
- `GET /api/sales-tracking/shipments/{shipment_id}`
- `POST /api/sales-tracking/shipments/{shipment_id}/delivery`

Salesmen can access only shipments assigned to their employee ID. Sales Officers can access shipments whose field job belongs to them. Production still requires genuine server-side authentication; current demo identity headers are not production authorization.

## Current limitations

- This creates monitoring records from outward Gate Pass movements that have an assigned Salesman field job. Other company vehicles, warehouse transfers, or drivers without an existing Salesman job are not included yet.
- Destination coordinates are copied from the existing shop record when available. No destination pin picker or geocoding was added. If the shop has no coordinates, the route map shows the actual route but cannot show an exact destination marker or evaluate proximity.
- The dashboard polls every ten seconds; it is not shipment-specific authenticated WebSocket delivery. A true push channel is not yet implemented.
- Actual location history and stop detection reuse the existing field GPS service. Distance only sums accurate adjacent points less than or equal to 120 seconds apart; unobserved gaps are not filled. Speed comes from the latest browser GPS point when supplied.
- Delivery confirmation records recipient name, quantities, and notes, but does not yet support file/photo signatures, independent receiving-officer verification, delivery-document uploads, or inventory receipt reconciliation. This extension does not post inventory or finance entries, so it cannot double-post them.
- Arrival geofencing, road-routing ETA, nearby OSM POIs, and management fleet-wide analytics are not implemented. Do not infer delivery or misconduct from location data.
- The browser must remain able to provide GPS and the work session must remain active. HTTPS is required outside localhost. Browser or OS suspension can interrupt updates; the shipment remains open and reports stale/interrupted tracking.

Validate with the existing location-permission and session flows on a real HTTPS mobile device. Backend unit tests do not prove device GPS availability or browser background behavior.
