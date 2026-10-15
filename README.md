# Orbit — HR & Finance ERP frontend

A responsive React application built with Vite, plain CSS, and Lucide icons. No backend is required.

## Run locally

```sh
npm install
npm run dev
```

Open the local URL printed by Vite (normally http://127.0.0.1:5173).

```sh
npm run build
npm run preview
```

The production build is generated in `dist/` and can be served by a static host.

## Features

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

The dataset uses an explicit October 15, 2026 demo snapshot. Amounts are USD. Earlier cash flow chart months are illustrative demo history; October is computed from current records. Data is saved in localStorage under `orbit-erp-v1`. Clear this key to restore the initial demo on the next load.

Run `npm run test:smoke` after building to verify workflows in headless Edge on Windows. On other systems, set `BROWSER_PATH` to an installed Chromium browser executable. The test uses an isolated browser context and saves screenshots to the ignored `qa/` directory.

Attendance updates are independent of leave approval. Leave duration counts calendar days. Payroll snapshots include employees whose status is not Inactive, with base salaries only and no tax, statutory deductions, or proration. Payroll can be generated once per demo month. Payments update local records; they do not move money or send emails. Financial summaries group receipts and reimbursements by payment date (seeded payments use the invoice/expense date). Other reports group claims by expense date and leave by start date. These are demo operational reports, not accounting statements. This frontend has no authentication, shared persistence, bank integrations, or full general ledger.

The interface uses Google Fonts with local sans-serif fallbacks. All other visual assets are included or rendered locally.

## Source

- `src/App.jsx`: pages, shared components, forms, workflows, local state.
- `src/data.js`: seeded records, formatters, CSV helpers.
- `src/styles.css`: responsive visual system.

To connect a backend, replace the localStorage load/save and state updates with API calls. Apply authentication, authorization, server-side validation, and jurisdiction-specific payroll/accounting rules on that backend.
