# Orbit — Manufacturing, HR & Finance ERP frontend

A responsive React application built with Vite, plain CSS, and Lucide icons, with an optional FastAPI and Supabase backend.

## Run locally

```sh
npm install
npm run dev
```

Open the local URL printed by Vite (normally http://127.0.0.1:5173).
Open `http://127.0.0.1:5173/#factory` to start in manufacturing.

```sh
npm run build
npm run preview
```

The production build is generated in `dist/` and can be served by a static host.

## Python backend and Supabase

The FastAPI backend is organized by feature and layer: HR, Finance, Manufacturing, and Workspace each have models, repository, service, and API router modules. Shared persistence code is in `backend/app/shared`; Supabase client configuration is in `backend/app/db`; application settings and errors are in `backend/app/core`. The frontend's existing `GET/PUT /api/state` workflow remains supported. The SQL migration stores that canonical state and mirrors records into queryable feature tables in one database transaction. Authentication is still the demo frontend login (`didula` / `11111`); the API is not authenticated yet.

1. In Supabase, open **SQL Editor** and run [`backend/schema.sql`](backend/schema.sql). This creates the tables and `save_erp_state` function. The migration file does not automatically execute against your hosted project.
2. Copy `backend/.env.example` to `backend/.env`. Set `DATABASE_URL` to the Transaction pooler connection string (port `6543`) from **Project Settings → Database → Connection string**. URL-encode special characters in the password (`@` becomes `%40`). Keep this database password on the server; never put it in the root `.env` or a `VITE_*` variable.
3. Copy the root `.env.example` to `.env` and keep `VITE_API_URL=http://127.0.0.1:8000` for local development.
4. In PowerShell from the repository root, install and start the API:

```powershell
py -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

5. In a second terminal, start the frontend with `npm run dev`. Check `http://127.0.0.1:8000/api/health` for database status and `http://127.0.0.1:8000/docs` for the API. When Supabase is not configured or reachable, the frontend shows a local demo status and continues saving in browser storage.

Feature endpoints include `/api/hr/{employees,attendance,leaves,payroll}`, `/api/finance/{invoices,expenses}`, `/api/manufacturing/{materials,sheets,cuts,parts,products,jobs,machines,labor,purchases,maintenance,goods,bins,shops,orders,movements,costs,alerts,audit,saved-views}`, and the field-sales job/session/visit routes under `/api/sales-tracking`. Each existing collection supports GET, POST, GET by ID, PUT by ID, and DELETE by ID. These routes require an initialized workspace state; the frontend initializes it through `/api/state`.

## Field sales GPS tracking

The Salesman and Sales Officer workspaces reuse HR employee records and manufacturing shop records. Apply [`backend/migrations/20261017_sales_tracking.sql`](backend/migrations/20261017_sales_tracking.sql) after the base schema, then follow the [field sales setup and browser limitations](docs/field-sales-tracking.md). Location collection is work-session-only and browser-dependent. The demo role headers are not authentication; do not expose the new API or collect real employee location until server-verified identity and authorization are connected.

Environment placeholders are in [`.env.example`](.env.example) and [`backend/.env.example`](backend/.env.example). The backend API is documented at `http://127.0.0.1:8000/docs` while it is running.

## Features

- Department chooser with separate Manufacturing, Human resources, and Finance workspaces. Demo sign-in fields are prefilled with username `didula` and password `11111`; the same demo credentials open each workspace. Use **Change department** to return to the chooser.

- Overview with HR/Finance filters, cash flow chart, approval inbox, and recent activity.
- Searchable employee directory with department/status filters, list/grid views, profiles, editing, and activation status.
- Daily attendance management and CSV export.
- Leave requests with date/overlap validation, approval, and rejection.
- October payroll snapshot, review, approval, and demo payment recording.
- Client invoices with draft/finalize/payment states and CSV download.
- Expenses with approval, rejection, and reimbursement recording.
- Operating account balance and transactions derived from recorded payments.
- Monthly financial, employee, expense, and leave reports with CSV exports.
- Workspace preferences, global search, responsive navigation, keyboard-accessible dialogs, and browser persistence.

## Demo behavior

Manufacturing extends the existing application with a factory dashboard, material and offcut registers, BOM calculator, procurement, cutting optimizer, production board, scheduling, machine maintenance, quality approvals, warehouse bins, serial passports and QR labels, shop orders, dispatch, and cost reports. Use **Guided walkthrough** on the factory dashboard to explore the workflow. The demo role selector changes the acting employee; approvals require a different employee where indicated.

Cutting uses a deterministic rectangular guillotine heuristic with rotation, grain, margin, kerf, and offcut rules. Saving a preview does not consume stock. Approved execution and confirmed actuals post stock changes once. Production moves through approval gates and QC before finished goods become available. Dispatched orders create LKR invoices in the existing Finance screen; recorded payments appear in manufacturing cost events. Existing HR records supply attendance and workforce assignments.

Manufacturing amounts are LKR; existing HR/Finance demo data remains USD. Invoice screens offer a currency filter, and existing USD summaries exclude LKR invoices. No exchange-rate conversion is performed.

Scheduling and forecasting are estimates, the copilot uses local deterministic responses, and notifications are in-app only. QR links require matching persisted application data. There is no connected camera scanner, real authentication, bank service, external AI service, or accounting-grade ledger. The Supabase backend stores a canonical JSONB state and mirrors records into per-feature tables; it does not yet support concurrent multi-user editing. Cutting input undo/redo is supported; manual drag editing of nesting layouts is not. Full integration boundaries and remaining backend work are in `docs/manufacturing-integration.md`.

Validation:

```sh
npm run test:manufacturing
npm run build
npm run test:smoke
npm run test:manufacturing:browser
```

The manufacturing tests cover nesting geometry and cost reconciliation, guarded state transitions, production through rework and QC, stock movement idempotency, dispatch and payment integration, desktop workflows, and mobile layouts.

The dataset uses an explicit October 15, 2026 demo snapshot. Earlier cash flow chart months are illustrative demo history; October is computed from current records. Data is saved in localStorage under `orbit-erp-v1`. The selected department is stored for the current browser session only. The hardcoded demo sign-in is a navigation demo, not real authentication or authorization. Clear local storage to restore the initial demo on the next load.

Run `npm run test:smoke` after building to verify workflows in headless Edge on Windows. On other systems, set `BROWSER_PATH` to an installed Chromium browser executable. The test uses an isolated browser context and saves screenshots to the ignored `qa/` directory.

Attendance updates are independent of leave approval. Leave duration counts calendar days. Payroll snapshots include employees whose status is not Inactive, with base salaries only and no tax, statutory deductions, or proration. Payroll can be generated once per demo month. Payments update local records; they do not move money or send emails. Financial summaries group receipts and reimbursements by payment date (seeded payments use the invoice/expense date). Other reports group claims by expense date and leave by start date. These are demo operational reports, not accounting statements. This frontend has no authentication, shared persistence, bank integrations, or full general ledger.

The interface uses Google Fonts with local sans-serif fallbacks. All other visual assets are included or rendered locally.

## Source

- `src/App.jsx`: pages, shared components, forms, workflows, local state.
- `src/data.js`: seeded records, formatters, CSV helpers.
- `src/styles.css`: responsive visual system.

Before production, add authentication, authorization, per-user/company data isolation, server-side domain validation, concurrency control, and jurisdiction-specific payroll/accounting rules.
