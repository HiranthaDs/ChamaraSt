from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from backend.app.db.postgres import get_connection
from .models import Acknowledgement, NotificationCreate

router = APIRouter(prefix="/api/traceability", tags=["Traceability & notifications"])

ROLE_TABLES = {
    "HR Manager": {"employees", "attendance_records", "leave_requests", "payroll_runs"},
    "Finance Officer": {"invoices", "expenses", "production_orders", "sales_orders", "manufacturing_cost_events", "stock_movements", "purchase_requests"},
    "Factory Manager": {"production_orders", "manufacturing_materials", "physical_sheets", "cutting_plans", "cut_parts", "products", "machines", "purchase_requests", "maintenance_tickets", "finished_goods", "warehouse_bins", "stock_movements", "manufacturing_cost_events", "sales_orders", "gate_passes", "gate_pass_items", "gate_pass_approvals", "gate_pass_verifications", "gate_pass_movements", "gate_pass_returns", "gate_pass_audit_logs", "gate_pass_scan_logs"},
    "Warehouse Manager": {"finished_goods", "warehouse_bins", "stock_movements", "sales_orders", "gate_passes", "gate_pass_items", "gate_pass_verifications", "gate_pass_movements", "gate_pass_returns"},
    "Inventory Officer": {"manufacturing_materials", "physical_sheets", "finished_goods", "warehouse_bins", "stock_movements", "gate_passes", "gate_pass_items", "gate_pass_verifications", "gate_pass_movements", "gate_pass_returns"},
    "Security Supervisor": {"gate_passes", "gate_pass_items", "gate_pass_approvals", "gate_pass_verifications", "gate_pass_movements", "gate_pass_returns", "gate_pass_audit_logs", "gate_pass_scan_logs"},
    "Gate Security Officer": {"gate_passes", "gate_pass_items", "gate_pass_movements", "gate_pass_scan_logs"},
    "Sales Officer": {"sales_field_jobs", "sales_tracking_sessions", "sales_tracking_events", "sales_job_visits", "sales_orders", "gate_passes", "gate_pass_items", "gate_pass_movements"},
    "Salesman": {"sales_field_jobs", "sales_tracking_sessions", "sales_tracking_events", "sales_job_visits", "sales_orders", "gate_passes", "gate_pass_items", "gate_pass_movements"},
}
MANAGERS = {"Factory Manager", "Production Planner", "Supervisor", "Warehouse Manager", "Sales Officer", "Finance Officer", "HR Manager", "Security Supervisor", "Transport Officer"}


def actor_context(x_demo_role: str = Header(...), x_demo_employee_id: str = Header(...)) -> dict:
    with get_connection() as db:
        row = db.execute("select payload from public.employees where id=%s", (x_demo_employee_id,)).fetchone()
    if not row or row["payload"].get("status") != "Active" or row["payload"].get("role") != x_demo_role:
        raise HTTPException(403, "Choose an active HR employee with the selected role.")
    return {"id": x_demo_employee_id, "role": x_demo_role}


@router.get("/events")
def list_events(limit: int = Query(default=100, ge=1, le=500), entity_type: str | None = None,
                entity_id: str | None = None, actor: dict = Depends(actor_context)):
    allowed = ROLE_TABLES.get(actor["role"], set())
    if not allowed:
        raise HTTPException(403, "This role has no traceability audit access.")
    clauses = ["table_name = any(%s)"]
    params: list = [list(allowed)]
    # Keep individual contributors scoped to their own actions. Supervisors can inspect
    # the audit history for their function, but payroll and GPS points are never included.
    if actor["role"] not in {"HR Manager", "Finance Officer", "Factory Manager", "Security Supervisor"}:
        clauses.append("actor_id = %s")
        params.append(actor["id"])
    if entity_type:
        clauses.append("table_name = %s")
        params.append(entity_type)
    if entity_id:
        clauses.append("record_id = %s")
        params.append(entity_id)
    params.append(limit)
    query = "select event_id,occurred_at,actor_id,actor_role,actor_source,table_name,action,record_id,before_data,after_data from public.erp_audit_events where " + " and ".join(clauses) + " order by occurred_at desc,event_id desc limit %s"
    with get_connection() as db:
        return db.execute(query, params).fetchall()


@router.get("/notifications")
def list_notifications(actor: dict = Depends(actor_context)):
    with get_connection() as db:
        return db.execute("select * from public.erp_notifications where recipient_employee_id=%s order by created_at desc limit 250", (actor["id"],)).fetchall()


@router.post("/notifications", status_code=201)
def create_notification(body: NotificationCreate, actor: dict = Depends(actor_context)):
    if actor["role"] not in MANAGERS:
        raise HTTPException(403, "A supervisor role is required to assign or notify another employee.")
    with get_connection() as db:
        recipient = db.execute("select payload from public.employees where id=%s", (body.recipient_employee_id,)).fetchone()
        if not recipient or recipient["payload"].get("status") != "Active":
            raise HTTPException(404, "Active recipient employee not found.")
        actual_role = recipient["payload"].get("role")
        if body.recipient_role and body.recipient_role != actual_role:
            raise HTTPException(409, "Recipient role does not match the HR employee record.")
        row = db.execute("""insert into public.erp_notifications
          (id,recipient_employee_id,recipient_role,title,message,entity_type,entity_id,created_by_employee_id,created_by_role,metadata)
          values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *""",
          ("NTF-" + uuid4().hex, body.recipient_employee_id, actual_role, body.title, body.message,
           body.entity_type, body.entity_id, actor["id"], actor["role"], Jsonb(body.metadata))).fetchone()
        return row


@router.post("/notifications/{notification_id}/acknowledge")
def acknowledge(notification_id: str, body: Acknowledgement, actor: dict = Depends(actor_context)):
    with get_connection() as db:
        row = db.execute("""update public.erp_notifications set read_at=coalesce(read_at,now()), acknowledged_at=now(), acknowledgement_note=%s
          where id=%s and recipient_employee_id=%s returning *""", (body.note, notification_id, actor["id"])).fetchone()
        if not row:
            raise HTTPException(404, "Notification not found for this employee.")
        return row
