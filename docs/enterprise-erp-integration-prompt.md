# Enterprise ERP process integration prompt

Use this prompt when implementing the next integrated ERP development phase in this repository.

---

You are the senior ERP architect and full-stack engineer for the existing Orbit ERP repository. Implement the end-to-end manufacturing, warehouse, sales, delivery, gate security, HR, and finance workflow in the existing React + Vite frontend and feature-based FastAPI + PostgreSQL/Supabase backend. Inspect the current code and schema before changing anything. Preserve working modules, employee records, role names, routes, existing IDs, currencies, and data. Do not replace the current application with a demo or a separate stack.

## Business outcome

Every customer order must be traceable from demand through production, inventory, dispatch, delivery, invoice, receipt, cost recognition, and margin. A material or finished-goods quantity must never appear, disappear, be reserved twice, ship twice, or be financially posted twice without an explicit, attributable correction. A role must not be able to claim that an assigned, approved, rejected, issued, or checked step was hidden from them: the system must record the responsible person, timestamp, decision, reason, linked evidence, notification delivery, and acknowledgement where the process requires acknowledgement. Recording delivery or acknowledgement is evidence of a system event, not proof that a person understood it.

## Existing architecture and constraints

- Frontend: React + Vite, existing `src/App.jsx`, manufacturing, sales, and gate modules, existing design system and hash navigation.
- Backend: Python FastAPI, feature-based modules under `backend/app/features`, psycopg, Supabase PostgreSQL, additive SQL migrations under `backend/migrations`.
- `public.erp_state` and `save_erp_state` currently mirror much of the legacy frontend state. Feature APIs also exist. Treat this as a migration boundary: do not let competing snapshot writes silently overwrite newer normalized records. Add version checks / optimistic concurrency or migrate each workflow to authoritative feature tables before claiming concurrent-safe operation.
- Sales GPS is collected only in an explicitly started field session. Preserve the existing notice, purpose limitation, stale-fix handling, and role-based team scope. Do not copy raw GPS coordinates into general audit/event records.
- Gate pass policy and audit tables already exist. Preserve their checks, QR replay protections, role separation, return logic, and transaction locks. Close the documented gap whereby a legacy manufacturing dispatch can proceed without the required gate authorization.
- Existing demo login and client-selected demo roles are not production authentication. Keep them only for development; never call them secure authentication or use them as production authorization.
- Never print, commit, or copy `.env` secrets. Use environment variable placeholders and migrations. Do not change existing employee/password data or seed fake employee accounts.

## Canonical business records and linkage

Use stable identifiers and explicit foreign/reference keys across these records. Define and document ownership of every status and quantity.

1. Customer/shop order: customer, lines, product/revision, quantity, currency, price/tax terms, requested delivery, sales owner, approval, and status.
2. Production order/batch: source order line(s), BOM/product revision, planned and actual quantities, materials/lots, work stages, operators, supervisor sign-offs, quality inspections, rejects/rework, and released quantity.
3. Inventory lot and movement ledger: source receipt or production batch, parent lot, child/split lots, item, location/bin, quantity/unit, reservation, movement reason, source reference, actor, and timestamp. Transfers and splits must preserve lineage and conserve quantity; adjustments require a reason and approval.
4. Fulfilment allocation and shipment: order line, reserved lot(s), picked/packed quantity, destination type (shop route or direct client), salesman/job or carrier, dispatch evidence, and delivery confirmation. Partial shipments must have separate linked shipment records and must not exceed the remaining ordered quantity.
5. Gate pass: linked shipment/order/lot references, exact quantities/serials, vehicle/driver, pass type and direction, requested-by, approver chain, warehouse verification, issued QR/token lifecycle, notified recipients, gate scans, physical checks, actual moved quantities, discrepancies, return obligations, and linked inward return. Gate confirmation and inventory posting must be atomic or safely idempotent through a transactional outbox.
6. Finance: chart of accounts, journal header/lines, source reference, currency, exchange rate and source, accounting date, posting period, debit/credit, tax, customer invoice, supplier bill, receipt/payment, COGS, payroll and expense references, reversal link, and approval. Posted journals are immutable; corrections use reversals and replacement entries.
7. Workforce: employee and role references, attendance, leave, assigned operation/field job, accountable approval, and payroll run. Separate operational visibility from confidential HR and salary information.
8. Audit/event ledger: append-only actor, role, source, action, object and ID, before/after change summary, UTC timestamp, correlation/causation IDs, reason, and related evidence. Store only necessary data. Exclude credentials, tokens, attachment bytes, and raw GPS coordinates.

Create a readable trace view that follows one order or batch across all these records. Every screen must show the current owner, current state, next action, due time, blockers, and history. Use consistent status names and only allow valid state transitions through backend commands. Do not allow frontend-only changes to bypass policy.

## Required workflow and controls

- Demand to production: sales order approval creates or updates demand; planner creates a production order; material availability is checked and reserved once; shortages create linked procurement requests; receipts are inspected and posted to stock.
- Production: authorized operators record each stage; required handoffs identify the next owner; supervisors verify output; quality can hold/reject/rework/release. Failed or uninspected goods cannot enter sellable stock. Stage completion and QC release preserve distinct actors where separation of duties applies.
- Warehouse: only released quantity can be received into finished-goods stock. Split/allocate lots to a shop route and/or direct client shipment with parent-child lineage. Maintain quantity conservation and reservation checks under transaction/row locks.
- Dispatch and gate: require approved allocation and a valid gate pass before physical goods can leave. Record pass issuer, each approval decision/reason, who was notified and when, warehouse verifier, security checker, checkpoint, scan result, actual quantity, and exit time. A pass being issued is not the same as a shipment being dispatched. Failed checks or discrepancies block movement and create an assigned resolution task. Returns link to the original shipment/pass and update inventory only when received and accepted.
- Delivery and sales: salesmen see only their assigned route/orders/shops and record visit, delivery quantities, customer acknowledgement, returns, and exceptions. Sales officer sees only their assigned team and the operational data needed to supervise it. GPS collection remains opt-in per active job and is not used as proof of customer contact.
- HR: work assignments and approvals reference active employees and their role. Attendance, leave, and payroll records are attributable. Payroll input, approval, and payment are separate controlled steps. Restrict salary/personal data to authorized HR/payroll users and authorized finance staff only as needed.
- Finance: sales invoice is created from fulfilled order/shipment quantities, not from an unfulfilled plan. Receipts apply to invoices; supplier bills apply to received purchases; inventory valuation and manufacturing costs feed cost of goods sold only once. Payroll and expenses post through approved sources. Every posting is balanced per currency and accounting period.
- Reconciliation: provide exception reports for order vs production, production vs stock, allocation vs dispatch, gate pass vs actual movement, dispatch vs delivery, invoice vs fulfilled quantity, invoice vs receipts, supplier bills vs received goods, inventory subledger vs control account, payroll register vs payroll journal, and journal debits vs credits. Show unmatched values, source references, owner, age, and resolution evidence. Never silently auto-plug a difference into a suspense account.
- Communication: create in-app notifications for assigned work, approvals, rejection, gate pass issuance, security verification, exceptions, due dates, and completion. Persist recipient, delivery/creation time, read time, explicit acknowledgement time, and acknowledgement note. Escalate overdue/unacknowledged actions by configurable policy. A notification failure must be visible and retryable.

## Financial posting rules

Implement a configurable, reviewed chart of accounts and double-entry journal service. Never hard-code a tax rate, accounting policy, exchange rate, depreciation policy, inventory valuation method, or LKR/USD conversion. Read approved company settings and keep source currency, functional currency, rate, and rate date explicit. Use decimal/numeric arithmetic, never binary floating point, and define rounding rules.

At minimum, validate that total debits equal total credits for every posted journal in each currency/functional-currency representation, period is open, all accounts exist and are postable, source is uniquely posted, and actor is authorized. Example posting patterns are configuration decisions to confirm with the business/accountant: receipt of purchased inventory (inventory/receiving clearing), supplier bill (clearing/AP), customer invoice (AR/revenue/tax payable), customer receipt (cash/AR), and shipment cost recognition (COGS/inventory). Manufacturing WIP, labor/overhead absorption, scrap, landed cost, returns, discounts, payroll liabilities, and foreign exchange must be explicitly designed and approved before posting. Use idempotency keys and a transactional outbox for cross-module posting; retrying a command cannot duplicate stock or journal lines.

## Role-specific access and accountability

Reuse existing roles where possible: Factory Manager, Production Planner, Cutting Operator, Manufacturing Operator, Supervisor, Quality Inspector, Inventory Officer, Warehouse Manager, Procurement Officer, Sales Officer, Salesman, Finance Officer, HR Manager, Gate Security Officer, Security Supervisor, and Transport Officer. Define a least-privilege permission matrix for read, create, update, submit, approve, post, reverse, and acknowledge. Enforce it on the backend, not by hiding buttons. Segregate requester/approver and preparer/poster where required. Auditors receive read-only trace and reconciliation access with sensitive HR fields masked unless specifically authorized.

## Engineering requirements

- Inspect existing schemas, service conventions, frontend components, and tests first. Add feature-based models, repository, service, router, migration, and UI using repository conventions.
- Use database transactions, optimistic version checks, unique idempotency keys, row locks for stock/journal posting, and transactional outbox patterns for cross-feature effects.
- Maintain append-only audit history. Corrections must be compensating events, not edits/deletes to posted ledger or audit rows. Distinguish attempted, failed, pending, approved, posted, reversed, and completed states.
- Make database writes authoritative. Do not present stale localStorage data as saved database data. Show sync/error state to users and prevent conflicting snapshot saves from overwriting newer records.
- Build useful accessible screens: order/batch trace page, role work queues, approval/notification inbox, gate-pass and shipment links, finance posting/reconciliation view, and audit history. Fit the existing app design.
- Add meaningful unit/integration tests for permitted and denied transitions, quantity conservation, duplicate/replayed commands, concurrent reservations, double-entry balance, currency separation, audit immutability, acknowledgement, notification retry, and cross-module references. Include migration instructions and a local end-to-end walkthrough.
- Do not claim “error-free,” “tamper-proof,” “knowledge proven,” or production-secure. State remaining assumptions and have finance/accounting policies reviewed by the organization’s accountant.

## Acceptance criteria

1. From an order ID, an authorized user can trace production, material consumption, lot splits, reservations, shipment, gate pass and every approver/checker, delivery, invoice, receipts, journal postings, and realized margin.
2. Every state-changing action and attempted gate check has an actor identity (or is explicitly labeled unknown/system), server timestamp, reason where required, and linked source. Audit history cannot be edited through application APIs.
3. An unapproved, held, rejected, unallocated, or over-quantity batch cannot be dispatched. A failed gate scan never counts as exit. Valid movement changes inventory exactly once.
4. Every split, transfer, receipt, shipment, and return conserves quantities or records an approved, explained adjustment.
5. Every posted journal balances, is tied to a source, and cannot be duplicated by retry. Reconciliation reports surface any subledger/control-account difference without hiding it.
6. The right role receives a persistent notification for each required handoff and can acknowledge it. Missing acknowledgement is visible and escalated; the system does not infer that a person understood a message.
7. Role tests prove users cannot see or change another team’s restricted data or confidential payroll information.
8. Existing manufacturing, sales tracking, gate pass, HR, and finance behavior remains covered by tests and is not silently deleted or overwritten.

Implement in small reviewable phases. Begin with the data model, migration, role/transition matrix, and traceability API; then integrate manufacturing/stock, dispatch/gate, sales/delivery, and finance posting/reconciliation. Keep each phase runnable and report exactly what is implemented, migrated, tested, and still pending.

---

## Current foundation added

`backend/migrations/20261017_enterprise_traceability.sql` adds an append-only database change ledger for canonical ERP rows and a persistent notification/acknowledgement table. It has been applied to the configured Supabase database with the migration runner. The API binds the existing demo request identity to database session context so triggers can attribute changes where those headers are supplied. These identities are client-selected and are not suitable for production authorization. Audit access and notification create/list/acknowledge endpoints are registered under `/api/traceability`.

The shipment slice now reuses confirmed outward Gate Pass movements and existing field-sales GPS sessions, and supports shipment route viewing plus quantity-reconciled delivery confirmations. See `docs/live-shipment-tracking.md` for the actual workflow and limitations. Automatic notifications for every business handoff, destination geofencing, realtime shipment push, the full order-to-cash workflow, double-entry posting, complete role matrix, independent receiving verification, and reconciliation screens remain unimplemented. The current notification API records in-app messages and acknowledgements; it does not prove a person read or understood them. Do not describe the broader workflow as complete until the acceptance criteria above are implemented and verified.
