# Gate passes and security

The module uses the existing React/Vite frontend, FastAPI backend, HR employees and PostgreSQL connection. The additive migration creates twelve gate tables, ten pass types and a Main gate checkpoint. It also links gate handoff events to field-sales jobs without starting GPS.

## Run

From `orbit-erp`, start the API:

```powershell
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
npm.cmd run dev
```

Use the existing `backend/.env`: `DATABASE_URL`, `APP_ENV=development`, `FRONTEND_ORIGINS`, `API_HOST` and `API_PORT`. The frontend uses `VITE_API_URL`. No new external keys are required. Real credentials remain in your existing environment files.

The migration was applied to the configured Supabase database during implementation. On another database, apply the base `backend/schema.sql` first, then run:

```powershell
.\backend\.venv\Scripts\python.exe -m backend.migrate --apply
```

The migration runner applies the sales dependency first and records checksums. It never recreates or seeds employee accounts.

## Workflow

1. In HR, assign real active employees the necessary roles. Gate Security Officer, Security Supervisor and Transport Officer are now available job titles. Existing Warehouse Manager, Inventory Officer, Supervisor and Factory Manager roles are reused.
2. Sign into Manufacturing and open **Gate passes**, or sign into **Gate & Security**. Field sales has **My gate passes**. All retain `didula` / `11111` with employee selection.
3. Create a draft, choose existing item records, business references, checkpoint, vehicle and validity times. Finished-goods outward requires exact serials from a packed sales order. Sales roles must link their assigned field job.
4. Attach supporting files or enter a document reference, then submit. A different Warehouse Manager or Inventory Officer completes the warehouse checks.
5. The configured approvers approve in sequence. Requesters and warehouse verifiers cannot approve their own request. High-value requests also require Factory Manager approval.
6. Requester or warehouse marks the pass ready. Generate its QR. The security officer scans it or enters the printed pass number, checks the checkpoint and direction, and starts inspection.
7. The inspecting officer generates a fresh confirmation QR/token, completes all physical checks and enters actual movement quantities. Confirming consumes the token. Partial movement leaves remaining quantities ready for another inspection.
8. For returns, create a Returnable inward pass and choose the original outward pass. Outstanding item references fill automatically. The same verification/approval/inspection process records receipt and updates the original obligation. Warehouse inventory acceptance remains a separate process.

Print the pass through the browser's **Print / Save PDF**. Uploaded PDF/PNG/JPEG files are limited to 5 MB each and downloaded through the role-checked API. Return write-offs require an independent Factory Manager and a reason.

## Security and implementation boundaries

- This is a development implementation with the ERP's existing client-selected employee identities. The gate API deliberately refuses these identities outside `development` / `test`. Production requires integration with genuine server-verified ERP authentication; the other existing ERP APIs also need that work.
- QR tokens are unpredictable, stored as SHA-256 hashes, revoked on replacement/cancellation/exception and consumed on confirmation. Transactions and row/advisory locks serialize gate updates. Failed scan attempts are persisted; scan rate limiting is database-backed.
- Gate records are separate from legacy whole-workspace autosaves. No gate action posts inventory. Outward material availability is deliberately conservative: earlier gate movements remain committed until a linked return. There is no automated stock-ledger reconciliation yet, so repeated bulk dispatches may require a later inventory integration.
- Existing manufacturing dispatch can still operate independently of gate authorization. This module records/validates physical gate movement; it does not yet enforce a gate prerequisite in every legacy dispatch API.
- Policies configure approval roles, high-value thresholds, document/invoice requirements and partial movement. Destination/risk rules, custom pass-type creation, delegated approvals, escalation schedules and external notifications are not implemented.
- Audit activity is available in the gate module; it is not pushed into the legacy snapshot notification bell. Reports currently show the latest 1,000 passes, with filters and a 100-event activity view; pagination, full CSV reporting and scheduled overdue alerts remain extensions.
- Camera scanning uses the browser BarcodeDetector API where supported, with explicit permission and a manual/USB scanner fallback. A cross-browser scanner library is not included. Test on the actual gate device; production cameras require HTTPS or localhost.
- Attachments are private database-backed downloads with content signature checks, not antivirus scanning. Identity document references should contain only the information your organization needs.
- Branch receipt and partial returns share the linked movement engine. Business-specific branch inventory acceptance, scrap valuation and subcontract reconciliation remain in their existing/ future ERP workflows.

## Verification

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend/tests -p test_*.py
.\backend\.venv\Scripts\python.exe -m backend.tests.gate_database_check
npm.cmd run test:manufacturing
npm.cmd run build
```

The database check uses temporary employees and an asset, exercises outward approval, QR inspection, confirmation, replay rejection and linked return, and rolls back all fixtures. Sequence numbers can have gaps after rolled-back tests, which is normal. Browser/device-camera and concurrent load testing are separate checks.
