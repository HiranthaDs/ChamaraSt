# Manufacturing frontend integration

The existing application is React + Vite + Lucide + plain CSS, with hash navigation and one localStorage document (`orbit-erp-v1`). Finance and HR are implemented in `src/App.jsx`. There are no backend services, database connections, authentication, or chart-of-accounts APIs.

The manufacturing extension preserves those modules, their USD records, branding, and storage key. It adds a versioned `manufacturing` property to the same state, reuses employee IDs, and uses the existing component styles. Manufacturing amounts are explicitly LKR, held as integer minor units; historical USD data is never relabeled or combined with LKR totals. Manufacturing sales invoices join the existing invoice collection with an explicit currency.

Modules: inventory/receiving, offcuts, product BOM, procurement, cutting, production, approval/QC, scheduling, machines/maintenance, warehouse/serial passports, distribution, manufacturing cost reports, local-data assistant, and a guided demo.

All demo mutations use a common pure transition function with validation, role checks, reference IDs, stock movements, and audit events. This offers atomic updates within one browser state only. It is not concurrent, tamper-proof, or authenticated. Previewing or optimizing a cut never consumes stock. Only approved, executed, and confirmed cuts post consumption and create serialized offcuts. Stage completion requires a different employee's approval. Failed QC cannot release sellable stock. Dispatch consumes allocated serials once; invoicing never consumes inventory again.

## Cutting policy

The optimizer compares deterministic rectangular guillotine packings, honoring dimensions, kerf, margins, optional 90-degree rotation, and grain restrictions. Results are feasible heuristic candidates, not claims of a globally optimal solution. Every part and remaining region is disjoint. Reusable remnants meet a configurable minimum side length. Part area, remnant area, kerf, edge trim, and small scrap reconcile to the original sheet area.

Original purchase cost is allocated proportionally by area to parts and reusable offcuts; the residual is unrecoverable loss. Rounding residuals stay in loss, preventing double counting. Cutting time and machine costs are estimates. Confirmed demo quantities assume the executed geometry matches the approved plan; damaged remnants can be quarantined later.

## Backend later

The proposed persistence entities are MaterialLot, PhysicalSheet, CuttingPlan, CutPart, Offcut, ProductRevision, BOMLine, ProductionOrder, StageExecution, Approval, Inspection, SerialProduct, Bin, StockMovement, ShopOrder, PurchaseRequest, and ManufacturingCostEvent. Employee, invoice, attendance, and payroll entities must remain the existing ERP's canonical records.

Replace local transition calls with authenticated commands carrying `commandId`, `expectedVersion`, and actor identity derived from the server session. Apply stock movements and financial outbox events in a database transaction, enforce unique posting references and conditional stock reservations, and publish idempotently into the existing finance service. Enforce separation of duties, approved labor rates, configured taxes, real permissions, audit integrity, backup policies, and encrypted transport/storage on the backend. No frontend role switch provides security.
