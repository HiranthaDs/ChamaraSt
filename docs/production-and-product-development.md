# Production Jobs and New Part Proposals

## Existing system inspection

The application uses React 19 / Vite and FastAPI / Pydantic, with psycopg and Supabase PostgreSQL (no ORM). Manufacturing lives in the canonical `erp_state` snapshot, mirrored into existing production orders, products, materials, finished goods, sales orders, movements and costing tables. Gate Pass and shipment data already use normalized tables. The UI uses the existing forest-green, lime and mint theme, sidebar, employee selector and department portals.

The new modules reuse those entities. `production_job_management` is metadata keyed by an existing production order; it is not a second order or stock ledger. Tasks, dependencies, blockers, engineering versions, reviews, cost estimates, prototype links, documents and events are new normalized records. Every write runs in a database transaction, locks canonical state before feature records, and uses the existing audit and notification infrastructure.

Existing roles cover all responsibilities; no new employees or roles are seeded. Production Planner coordinates development, Supervisor reviews technical feasibility and prototypes, Inventory/Procurement/Warehouse reviews materials, Finance Officer reviews costs, Quality Inspector records tests, and Factory Manager gives final approval. Operators see their own assigned jobs and proposals. Cost data in the new endpoints is restricted to Finance Officer and Factory Manager.

## Install and run

From `orbit-erp`, install the existing requirements and apply the additive migration:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\backend\.venv\Scripts\python.exe -m backend.migrate --apply
.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

In a separate terminal, from `orbit-erp`:

```powershell
npm install
npm run dev
```

No additional keys or dependencies are required. Keep `DATABASE_URL`, `APP_ENV`, and `FRONTEND_ORIGINS` in `backend/.env`; frontend `VITE_API_URL` points to the API. On Render, deploy the backend and migration before the frontend. Include the actual frontend HTTPS origin in `FRONTEND_ORIGINS`. Do not commit `.env`.

The migration does not seed demo business records or rewrite prior migrations. It adds foreign keys, indexes, RLS, append-only history, and a guarded snapshot save function. Old clients attempting to overwrite records created by development receive a conflict and must refresh.

## Production workflow

1. Sign into Manufacturing with the existing demo credentials, choosing an active HR employee with the correct role. Open **Production Jobs**.
2. Production Planner creates an order using the existing Production page, then opens it in Production Jobs to set supervisor, start/due dates, priority and optional matching customer sales order.
3. Add tasks/subtasks, existing HR employees, an independent reviewer, checklist and dependencies. A task cannot start before its prerequisites complete unless an independent planner/supervisor approves a recorded exception.
4. Inventory Officer or Production Planner reserves the actual BOM through Production. In Production Jobs, submit the job to Pending Approval. A separate Supervisor or Factory Manager releases it to Ready for Production.
5. The assigned Manufacturing Operator starts each stage from the existing Production controls. HR attendance, valid approved labor profile, equipment availability, release approval and blockers are checked on the server. Material consumption and financial postings happen once in the existing records.
6. Operator records work and hours; an independent Supervisor approves each stage. Quality Inspector records final inspection. Rework returns the order to Assembly, preserving inspection and review history.
7. Packaging approval creates finished goods in QA-HOLD. Warehouse Manager puts each serial into a sellable warehouse bin. Only then does manufacturing progress reach 100%.
8. Warehouse Manager records reconciliation. Stock jobs can close when all tasks are complete/cancelled and blockers resolved. Customer jobs also require confirmed outward Gate Pass movement; shipment and delivery remain separate linked records.

Drag/drop opens a stage confirmation; keyboard and mobile users can use **Change stage**. Both call the same guarded endpoint. Tasks never consume stock or automatically mark manufacturing stages complete. Rejected and rework quantities display **Not recorded** when the existing source has no unit count; they are not invented.

Board/list views support search, status, priority/date sorting and personal assignments. The timeline uses planned job dates; rescheduling shifts unfinished task dates by the same interval. Overlapping employee task assignments are warnings, not automatic performance judgments. Analytics show actual workflow counts and bottlenecks, not GPS-derived productivity or invented efficiency percentages. Manager configuration can change display labels, column ordering and positive stage weights while retaining controlled workflow semantics.

## Product development workflow

1. Open **New Part Proposals** and create a proposal. Enter automotive fitment, dimensions, market evidence, manufacturing requirements, quality criteria, materials/BOM, business justification and a development coordinator.
2. Upload PDF, PNG, JPEG, STEP or ASCII DXF documents (5 MB maximum each). Documents use private database storage, validated content and authorized forced downloads. They are not publicly hosted or rendered as executable content.
3. Submit the proposal, then advance through Under Review and Feasibility Study. A specification change creates a new immutable revision and resets the proposal to Ideas. Approval history remains associated with its original revision.
4. Resolve feasibility changes and enter Design & Costing. Supervisor/Planner reviews technical feasibility, Inventory/Procurement/Warehouse reviews materials, and Finance records comparable per-unit LKR cost options, selling price and margin. The server stores integer minor currency units. Offcut credit cannot exceed material plus waste cost. Estimates do not create accounting postings.
5. Obtain current-revision Technical, Materials and Cost approval, then enter Prototype Development. A planner creates a real prototype manufacturing order with an operator, supervisor and machine. A development-only product specification supplies its BOM; ordinary production cannot use it.
6. Complete the actual prototype order through Production Jobs and manufacturing, including quality and warehouse receipt. Enter Prototype Testing; Quality Inspector records a passing/failing test. Multiple orders and tests preserve prototype iterations. Changes to the design require a new version and fresh reviews.
7. Independent Prototype and Quality reviews allow submission for final approval. Factory Manager approves launch. Proposal authors and revision authors cannot approve their own work.
8. Factory Manager converts the approved revision, choosing an approved estimate and a new SKU or explicitly linking an existing equivalent product. Duplicate SKU/name detection and repeat-request handling prevent duplicate products. The existing product master receives the approved BOM, manufacturing route, quality criteria and cost settings. Conversion does not start unrestricted production or add inventory.

Engineering revisions retain original documents/reviews/prototype links. Released manufacturing orders retain their material reservations and captured specifications; product conversion cannot silently change them. This installation uses its existing seven-stage manufacturing route. Adding a different machine route requires extending the manufacturing execution workflow, rather than changing proposal text alone.

## API and code structure

`backend/app/features/production_jobs/` and `product_development/` each contain models, repository, service and router layers. Shared workflow policy, documents, audit and transactional helpers are reused. The UI is `src/manufacturing/WorkflowWorkspace.jsx` with an API adapter and responsive stylesheet.

API roots are `/api/production-jobs` and `/api/product-proposals`. FastAPI `/docs` lists request schemas. Production endpoints cover metadata/configuration, list/detail, analytics/timeline data, plan/status, task/dependency/exception handling, blockers, reconciliation, attachments/comments and authorized manufacturing actions. Proposal endpoints cover creation/revision, status, review, cost estimates, prototype orders/tests, conversion and attachments/comments. Optimistic version fields reject stale metadata writes; prototype requests additionally use a client-generated idempotency key.

## Identity boundary

The pre-existing login remains `didula` / `11111`, as requested. It is a demo login, not verified production authentication. New endpoints require matching active HR employee and role headers, enforce ownership and review separation, and disable demo identities when `APP_ENV` is not `development` or `test`, consistent with the Gate Pass module. These headers are still client-asserted in demo mode. Production authentication must replace this adapter before treating employee attribution as verified identity.

The older whole-workspace HR/Finance API also remains a legacy demo interface; the new module does not make that entire API production-secure. Managed job changes and engineering product changes are blocked through that snapshot path and must use their workflow services. Existing unrelated ERP functions remain available.

## Validation

```powershell
.\backend\.venv\Scripts\python.exe -m unittest backend.tests.test_production_development backend.tests.test_gate_passes backend.tests.test_sales_tracking
.\backend\.venv\Scripts\python.exe -m backend.tests.production_development_database_check
npm run test:manufacturing
npm run build
```

The database integration check runs against the configured database in a rollback-only transaction. It previews the migration if pending, creates temporary fixture records, tests role scoping, approvals, dependencies, stock/finance consistency, full manufacture and prototype launch, and rolls back every change. It never creates demo records in production.
