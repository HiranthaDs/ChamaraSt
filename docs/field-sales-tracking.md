# Field sales tracking

Orbit's Field sales workspace uses the existing React/Vite application and the feature-based FastAPI/PostgreSQL backend. Salespeople are existing `employees` records whose HR `role` is `Salesman` or `Sales Officer`; no duplicate employee/login table is added. Manufacturing customer shops are read from the canonical ERP state.

## Install the schema and start the app

1. In Supabase Dashboard, open **SQL Editor** and apply `backend/schema.sql` if this project schema has not been created yet.
2. Apply `backend/migrations/20261017_sales_tracking.sql`. It creates field jobs, work-session metadata, accepted GPS points, detected stationary stops, shop visits, audit events, and policy settings. The SQL file enables RLS and grants the backend `service_role` database role access. It does not create or seed employees, sales officers, or shops.
3. In the HR employee directory, add/confirm Sales Officer and Salesman job titles. On the Sales workspace, the Sales Officer can assign an unassigned Salesman to their team. This updates the existing employee's `supervisorId`; the backend only lets that officer create jobs for employees assigned to them.
4. Ensure `backend/.env` contains the existing Supabase transaction-pooler `DATABASE_URL` and frontend origin. `VITE_API_URL` and optional `VITE_OSM_TILE_URL` belong in the frontend root `.env` (see root `.env.example`); restart Vite after editing.
5. Start the backend from the repository root with `backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000`, then start the frontend with `npm run dev`.
6. Open Field sales, sign in with the existing demo credentials `didula` / `11111`, and choose an active Sales Officer or Salesman employee. Assign a job from the officer view. The salesman must open their assigned job, accept the explicit start notice, and grant browser location permission.

## Behavior and limitations

- Location is requested only after **START JOB**, for an assigned active job. The page asks for a fresh initial fix before it creates a session; it then uses `navigator.geolocation.watchPosition()` with high accuracy requested. Accuracy and update timing depend on the device/browser and are never guaranteed.
- **END JOB** stops the browser watch and closes the server session. A browser crash, OS suspension, locked device, or lost network can pause fixes. The UI reports stale/interrupted state; it does not invent locations or connect missing points. Offline points received while the page remains active are queued in IndexedDB (best-effort, local to that browser). The backend accepts a limited delayed window and validates session ownership, increasing timestamps/sequences, coordinate ranges, and implausible movement.
- Raw accepted points retain reported accuracy. Distance and displayed route omit low-quality points; gaps are not interpolated. Stop detection is a server-side stationary-radius estimate, not proof of customer presence. A GPS-assisted shop check-in is not proof that an employee entered a building or met a customer.
- The officer map refreshes live data over a WebSocket with reconnect and falls back to periodic requests; map tiles use OpenStreetMap. The public OSM tile server has a usage policy and is for modest development use only. Set `VITE_OSM_TILE_URL` to a compliant self-hosted/approved tile endpoint for production. The module does not make per-point public Nominatim requests or paid routing calls.
- Battery level and effective network type are shown only when the browser exposes them. Cellular signal strength in dBm is not available to standard web pages.
- **Authentication is still demo-only.** API role headers identify an HR employee but can be forged by any client. CORS is not authentication. Do not expose this API or collect real employee locations until the ERP's real server-verified identity/session system and authorization middleware replace the demo headers, and authenticated WebSocket identity is added. Database RLS alone does not enforce per-employee access when the API connects as the database service role.
- Retention settings are stored in `sales_tracking_settings`; a scheduled purge/archive task and production audit/alert delivery must be configured before deploying. Current behavior does not guarantee background collection, route replay controls, map panning, reverse geocoding, OSRM navigation, or delivery/finance workflows that do not yet exist in this ERP.

Run backend unit checks with `backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests` and build the UI with `npm run build`.
# Sales Officer salesman detail and mobile GPS

The Sales Officer dashboard opens a shift detail panel by selecting a salesman. It shows HR contact details (phone, email, territory, region), latest GPS, a route map fitted to the selected day's route, detected stop arrival/departure/duration, visits, tracking gaps, GPS quality, observed moving/stopped time, and browser-reported mobile platform, battery and connection details where the browser provides them. The panel refreshes every 10 seconds. Phone numbers are only shown when recorded in HR.

From **HR → Employees**, add the Salesman's phone, territory and region/team. Assign the salesman to the Sales Officer with the HR **Reports to** field, then assign a field job with territory, date, times and shops. When the salesman opens their Salesman portal on a phone and presses **Start job**, the mobile browser prompts for location and starts recording the assigned work session. Screen wake lock is requested when supported; the salesman should leave the page open. Location permission and HTTPS are required on phones. GPS pauses can happen when a browser or operating system suspends the page; the UI reports gaps instead of drawing a route through missing data.

For a local phone preview, run the API and Vite as below in two terminals. Keep the Vite API proxy enabled. In a third terminal, expose the Vite development server through an HTTPS tunnel such as ngrok (`ngrok http 5173`), then open the returned **HTTPS** address on the phone. HTTPS is required because mobile browsers deny web location access to ordinary LAN HTTP addresses. The tunnel forwards API and WebSocket requests through Vite to `127.0.0.1:8000`. This demo login and development tunnel are for local review; do not publish the demo system as a production service.

```powershell
# API terminal, from orbit-erp
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# Frontend terminal
npm.cmd run dev

# Third terminal (install ngrok separately if it is not available)
ngrok http 5173
```

The Vite proxy supports `/api` and its WebSocket endpoint. The development server listens on network interfaces so the tunnel can reach it. `VITE_API_URL` can remain set to localhost; the browser automatically uses the current HTTPS origin for the proxied mobile requests.

The device model and battery level depend on browser support and are approximate browser-reported values. Web pages cannot reliably read the mobile phone number, radio signal bars, or exact handset model; contact phone comes from HR. A stop place is matched to an existing ERP shop only when that shop has coordinates within 250 m. Otherwise the dashboard shows the stop coordinates. It does not send private location data to a geocoding provider. Stops require five minutes of sufficiently accurate fixes in the configured radius. Moving time counts intervals with accepted fixes whose measured movement exceeds 0.5 m/s; these are estimates from recorded samples, not continuous odometer readings. Background GPS cannot be guaranteed by a mobile web page.
