# Connected manufacturing workflow

## Entry point

Choose **Manufacturing → Workflow desk**. Factory Managers and Production Planners land here by default. Existing department permissions still apply.

The desk has four views:

- **My next actions**: the next action for the selected role; operators see their assigned work.
- **All production**: active batches, purpose, quantity, owner, blockers and next handoff.
- **Shop fulfilment**: available finished stock, linked production, uncovered shortage and fulfilment actions.
- **Setup checklist**: employee, product, material, machine and warehouse prerequisites.

## Manufacture for stock

1. Complete product approval, BOM and quality criteria in New Part Proposals.
2. Receive the physical materials. Complete and independently verify cutting when components must be produced.
3. In Workflow desk, choose **Plan production**.
4. Choose **Make for warehouse stock**, product and quantity.
5. Review material requirements and shortages.
6. Choose the operator, machine, start, required-by date and work instructions.
7. Review and choose **Create production order**.
8. Return to Workflow desk → All production. Resolve material shortages and reserve the BOM.
9. Open Job record & documents → Change stage → Pending Approval.
10. A different Supervisor or Factory Manager approves Ready for Production.
11. The assigned operator starts and completes each operation; the independent supervisor reviews evidence. Quality inspection remains a separate decision.
12. Complete packaging approval. Warehouse Manager puts the released serials into sellable bins.
13. Reconcile and close the stock batch in its job record. A shop order is not required for this path.

## Manufacture for a shop request

1. Sales Officer or Warehouse Manager creates a shop request.
2. Open Workflow desk → Shop fulfilment.
3. If sufficient QC-released stock exists, Warehouse Manager allocates it directly.
4. Otherwise a planner chooses **Produce shortage**. Existing linked production and linked finished units awaiting putaway reduce the amount still to plan.
5. Complete the same production and independent approval sequence described above.
6. Warehouse Manager puts away the finished goods, allocates, picks and packs the shop order.
7. Complete applicable outward gate authorization and physical security checks before physical dispatch.
8. Dispatch, record actual recipient/proof of delivery, then Finance creates the invoice. Record payment in Finance when actually received.

Availability is shared until allocation. Creation rechecks the shortage under the canonical state lock. A request ID prevents retrying a save from creating a second batch. The planner does not reserve finished stock or automatically approve physical work.

## Shortage purchasing

Planned batches show BOM shortages and existing pending/approved purchase quantities. **Request shortage** prefills the uncovered quantity and links the request to the batch. Existing purchase approval and receiving controls still apply. Open purchase quantities are shared supply, not dedicated allocations.

## Beginner mode

Choose a task: stock planning, shop shortage planning, production execution, material receipt/cutting, product definition, sales/delivery, gate authorization or machine setup. Each guide highlights controls and explains the next action. Role changes remain explicit. The full reference course remains available.

The guide is instructional: it does not type sample values, make approvals, or mark actual work done. It advances when the user chooses Next step.

## Proposal drafts

**Save browser draft** in the proposal/revision form retains unfinished fields locally. The BOM is cached as it is edited. Drafts are separated by employee and revision; successful submission clears the draft. They are not shared between browsers or saved in the database until the proposal is submitted.

## Implementation and remaining scope

This update adds the connected desk, production wizard, purpose/order links, shortage planning, direct production-record actions, proposal browser drafts and task guides. It fixes the production status payload to omit proposal-only `fast_track` and keeps canonical dates/order links synchronized when plans change.

The wider comparison backlog is not implemented by this update: partial quantities moving independently through operations, quotations/conversion, supplier directory editing, commissions/payroll, bulk attendance, a complete product wizard/duplication, and a consolidated document library. Existing job document upload remains available.

Frontend production compilation and backend Python syntax checks were completed. No live database lifecycle or physical-operation simulation was run for this update. Restart the backend to load the new POST /api/production-jobs endpoint. Existing workflow database tables are used; no new migration was introduced.
