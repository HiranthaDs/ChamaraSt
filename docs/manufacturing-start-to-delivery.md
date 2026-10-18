# Manufacturing: start to delivery

This guide follows one job from incoming raw material through a confirmed customer delivery. It describes the current **Materials & inventory**, **Cutting Studio**, **Production**, **Approvals & quality**, **Warehouse**, **Sales & distribution**, and **Finance** screens.

The role selector in the Manufacturing header changes the acting employee. Use an active HR employee with the required role. Where a second person reviews work, switch to a different employee before approving. The demo stores operational records, but it does not control a physical saw, machine, vehicle, or bank transfer.

## 1. Receive raw material

1. Choose **Inventory Officer** and open **Materials & inventory → Stock register → Receive material**.
2. Enter the number of sheets in the batch, material type, grade, thickness, length, width, price per sheet, supplier, and rack location. Use millimetres for dimensions and the correct grade for the supplier certificate.
3. Select **Register physical sheets**. The app creates a unique serial for every sheet and records the receipt batch and stock movement.
4. The register groups matching sheets into one row and shows the quantity and total value. Open the group to inspect serials. A cut plan must select an individual available serial, so serial-level traceability remains intact.
5. Open **Consumables** to review pieces and liquids such as fasteners, primer, and paint. Liquids are stored in millilitres and displayed in litres. If stock is short, use the procurement process in step 6.

Check material, grade, thickness, dimensions, cost, batch, and location before planning a cut. Incorrect identity or dimensions will make the cut plan and later genealogy unreliable.

## 2. Define the cut parts

1. Open **Cutting Studio → Studio** and add or edit a sheet entry.
2. In **Inventory sheet**, select an available stock serial or verified reusable offcut. The app fills its dimensions, material, grade, thickness, and cost. The quantity is the available count for that selected source; the plan still reserves specific inventory serials.
3. Under **Parts**, add a part and enter its name, shape, quantity, material, grade, and thickness. Shapes are rectangle, square, circle, triangle, and polygon.
4. Enter width and height for rectangular parts, side length for squares, diameter for circles, or ordered `[[x,y], ...]` vertices for triangles and polygons. Coordinates are in millimetres.
5. Set the allowed rotation angles. Enable grain restriction when the material direction matters. Add margin, kerf, clamp, or keep-out constraints under the plan constraints. Link a part to an approved product when its design geometry is already in the product catalogue.

The optimizer validates the part geometry and checks that requested parts can fit. Invalid geometry, incompatible material/grade/thickness, or a part count that cannot fit must be fixed before the plan can be released.

## 3. Compare and save the plan

1. Review the preview and compare **Fast optimization**, **Maximum material utilization**, and **Offcut first**.
2. Check placed and missing part counts, sheet count, utilization, scrap area, reusable offcuts, estimated material cost, and estimated loss. A plan with unplaced parts is incomplete and cannot be released.
3. Select a layout. Drag parts only if needed, use rotate/undo/restore, and make sure nothing crosses the sheet boundary or violates the constraints.
4. Choose **Save draft**. Saving a preview does not consume inventory or create parts. Reopen a saved plan to inspect its version history or export its saved layout.

## 4. Submit and independently approve the cut

1. As **Cutting Operator**, open the saved draft and choose **Submit**. Submission reserves the source sheet so another plan cannot take it.
2. Switch to a different **Supervisor** and open **Approvals & quality → Approval inbox**.
3. Review the submitted layout, part count, utilization, estimated loss, and source sheet. Choose **Approve plan** to release execution, or **Request revision** and state what must change. Returning a plan releases its reserved sheet; revise and resubmit it.

The plan author must not approve their own submitted plan.

## 5. Execute and verify actual cutting

1. After approval, the Cutting Operator opens the plan and chooses **Start**. The status becomes Cutting.
2. Once the physical work is complete, choose **Complete**. Enter the accepted plate count and an evidence note describing the actual cut. If actual results differ from the approved plan, stop and record the discrepancy through the revision/review process; do not claim planned quantities as actual.
3. Choose **Verify**. Measure each remnant in the shop and select only offcuts whose dimensions and geometry are confirmed reusable. Leave the rest unselected so they are recorded as scrap.
4. Confirm verification. The app posts the actual sheet use once, creates cut-component stock and verified offcut serials, and records material cost events. The original sheet remains in history as used; the offcuts appear in the offcut library.

## 6. Check the BOM and resolve shortages

1. In **Materials & inventory → Product catalog**, open the target product and inspect its BOM. It lists the required material and quantity per finished unit.
2. Use the BOM/demand preview for the intended order quantity. Check available stock after reservations, not just on-hand stock. A planned order cannot reserve a BOM with a shortage.
3. For a shortage, create a purchase request from **Procurement** or the material reorder control. Enter quantity in base units (for example, millilitres for paint).
4. A different authorized employee (Supervisor or Finance Officer) approves the request. The requester cannot approve their own request.
5. As Inventory Officer, receive only an approved purchase. Check the received quantity and record before continuing. The purchase receipt increases inventory and posts its receipt movement once.

If a BOM is wrong, have an authorized Supervisor revise it before reserving material. Already reserved production orders keep their captured BOM revision.

## 7. Create the production order and reserve materials

1. As **Production Planner**, open **Production → Work orders → Production order**.
2. Select the product, quantity, active HR operator, available machine, start date, due date, priority, and work instructions. Review the material-demand preview.
3. Save the order. It enters Planned. Open it and choose **Reserve materials** as Production Planner or Inventory Officer. The system checks availability and records the BOM revision and product snapshot. A successful reservation changes the order to Ready.
4. If the reservation fails, resolve the listed material shortage first. Do not reduce the requested quantity without the planner’s approval.

## 8. Run production with stage approvals

The configured route is **Bending → Welding → Grinding → Painting → Assembly → Quality inspection → Packaging**.

1. The assigned Manufacturing Operator opens the Ready order and chooses **Start stage**. The app checks the assignment, attendance, machine status, reservation, and other workflow conditions. Starting posts reserved material consumption once.
2. Perform the displayed stage in the factory. Record actual hours and specific work notes/evidence, then choose **Complete stage**.
3. A different Supervisor opens **Approvals & quality**, reviews the stage, operator, hours, evidence, and next stage, then approves or returns the work with a reason. The operator cannot approve their own stage.
4. On approval the order advances to the next stage. The operator starts, records, and completes that work; the Supervisor independently reviews it. Repeat through the route.
5. A return or rejection must be resolved before the next handoff. Rework preserves the history; correct the issue, add new evidence, and resubmit for review.

## 9. Perform final quality inspection

When the order reaches **Awaiting QC**, a **Quality Inspector** opens **Approvals & quality → Quality inspections** and inspects the batch checklist: dimensions, surface, and assembly. Record the measured/observed result and notes, then submit the inspection.

A passing result releases serialized finished goods to Warehouse receiving. A failing result sends the order to rework; correct the defect and repeat the applicable production review and final inspection. Do not put failed goods into sellable stock.

## 10. Receive and put away finished goods

1. As **Warehouse Manager**, open **Warehouse → Receiving**.
2. Match each finished serial to its production order and product passport. Confirm its QC result before put-away.
3. Choose a destination bin with capacity and confirm the stock movement. Goods become available only after they are placed in a sellable bin.
4. Use the product passport to check production order, BOM revision, quality release, cost, material references, and journey history.

## 11. Create a shop request and dispatch exact serials

1. Open **Sales & distribution → Shop requests → New shop request**. Choose the shop, product, quantity, and requested delivery date.
2. Advance the request in order. **Allocate stock** reserves exact available product serials; **Confirm picked** records picking; **Confirm packed** records packing; **Dispatch shipment** posts the serials out of inventory and records the cost of goods sold.
3. If insufficient finished goods are available, complete more production and warehouse put-away first. The app must not dispatch unallocated or unavailable serials.

## 12. Confirm delivery and close the loop

1. After dispatch, open the order and choose **Record delivery**.
2. Enter the delivery proof/evidence and confirm. The order becomes **Delivered** only after this confirmation. Inspect **Delivery desk** for destination, assigned demo driver, serial count, status, and recorded evidence.
3. Create the LKR invoice from the dispatched order and use the existing Finance screen to record payment after it is actually received.
4. Finish in **Manufacturing insights**: review stock movements, material/cutting costs, scrap and offcut records, production costs, and serial genealogy. Compare the recorded quantities and evidence with the physical job before closing it.

## What the workflow records

- Raw sheet receipts, batches, individual serials, reservations, consumption, and verified offcuts.
- Cut-plan versions, reviews, execution evidence, accepted quantity, and actual reconciliation.
- Product BOM revision, production reservations and consumption, operator hours, stage notes, independent approvals, and QC outcomes.
- Finished-goods serials, warehouse bins, allocations, picks, packing, dispatch, delivery evidence, and invoice/payment references.

The UI records workflow evidence; it does not prove a physical cut, inspection, delivery, or payment by itself. Machine execution, carrier routing/live tracking, bank transfers, and accounting-grade general-ledger controls are not connected by this guide.
