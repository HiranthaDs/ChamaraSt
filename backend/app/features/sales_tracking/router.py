from __future__ import annotations

import asyncio
from datetime import date
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb

from backend.app.db.postgres import get_connection
from backend.app.features.sales_tracking.models import JobCreate, JobUpdate, LocationPoint, PointBatch, DeviceHeartbeat, VisitCreate, VisitUpdate, ShipmentDeliveryInput
from backend.app.features.sales_tracking.service import validate_point_order, distance_m

router = APIRouter(prefix="/api/sales-tracking", tags=["Sales tracking"])


def actor_context(x_demo_role: str = Header(...), x_demo_employee_id: str = Header(...)) -> dict:
    if x_demo_role not in {"Salesman", "Sales Officer"}:
        raise HTTPException(403, "Salesman or Sales Officer role is required.")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select payload from public.employees where id=%s", (x_demo_employee_id,))
        row = cur.fetchone()
    if not row or row["payload"].get("status") != "Active" or row["payload"].get("role") != x_demo_role:
        raise HTTPException(403, "The selected employee must be an active HR employee with this role.")
    return {"id": x_demo_employee_id, "role": x_demo_role, "payload": row["payload"]}


def require_role(actor: dict, role: str) -> None:
    if actor["role"] != role:
        raise HTTPException(403, f"{role} role required.")


def is_assigned_to_officer(cur, salesman_id: str, officer_id: str) -> bool:
    cur.execute("""select 1 from public.employees e where e.id=%s and
      (e.payload->>'supervisorId'=%s or e.payload->>'supervisor_id'=%s)
      union select 1 from public.sales_field_jobs j where j.salesman_id=%s and j.sales_officer_id=%s limit 1""",
      (salesman_id, officer_id, officer_id, salesman_id, officer_id))
    return cur.fetchone() is not None


@router.get("/jobs")
def list_jobs(actor: dict = Depends(actor_context)):
    with get_connection() as conn, conn.cursor() as cur:
        if actor["role"] == "Salesman":
            cur.execute("select * from public.sales_field_jobs where salesman_id=%s order by work_date desc, created_at desc", (actor["id"],))
        else:
            cur.execute("select * from public.sales_field_jobs where sales_officer_id=%s order by work_date desc, created_at desc", (actor["id"],))
        return cur.fetchall()


@router.get("/sessions/active")
def active_session(actor: dict = Depends(actor_context)):
    require_role(actor, "Salesman")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select * from public.sales_tracking_sessions where employee_id=%s and status='active' order by started_at desc limit 1", (actor["id"],))
        return cur.fetchone()


@router.post("/jobs", status_code=201)
def create_job(body: JobCreate, actor: dict = Depends(actor_context)):
    require_role(actor, "Sales Officer")
    job_id = f"FJ-{uuid4().hex[:10].upper()}"
    with get_connection() as conn, conn.cursor() as cur:
        if not is_assigned_to_officer(cur, body.salesman_id, actor["id"]):
            raise HTTPException(403, "Assign jobs only to a salesman in your authorized team.")
        cur.execute("select 1 from public.employees where id=%s and payload->>'role'='Salesman' and payload->>'status'='Active'", (body.salesman_id,))
        if not cur.fetchone():
            raise HTTPException(422, "Select an active Salesman from the HR employee directory.")
        cur.execute("select state->'manufacturing'->'shops' as shops from public.erp_state where id='main'")
        state_row = cur.fetchone()
        known_shops = {str(shop.get("id")) for shop in (state_row["shops"] if state_row and state_row["shops"] else [])}
        if not set(body.shop_ids).issubset(known_shops):
            raise HTTPException(422, "One or more selected shops are not in the existing ERP shop directory.")
        cur.execute("""insert into public.sales_field_jobs
          (id,salesman_id,sales_officer_id,work_date,starts_at,ends_at,territory,instructions,shop_ids,status)
          values (%s,%s,%s,%s,%s,%s,%s,%s,%s,'assigned') returning *""",
          (job_id, body.salesman_id, actor["id"], body.work_date, body.starts_at, body.ends_at,
           body.territory, body.instructions, body.shop_ids))
        return cur.fetchone()


@router.put("/jobs/{job_id}")
def update_job(job_id: str, body: JobUpdate, actor: dict = Depends(actor_context)):
    require_role(actor, "Sales Officer")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("update public.sales_field_jobs set status=%s,updated_at=now() where id=%s and sales_officer_id=%s and status='assigned' returning *",
                    (body.status, job_id, actor["id"]))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Assignable job not found.")
        return row


@router.get("/shops")
def list_shops(actor: dict = Depends(actor_context)):
    # Reuse manufacturing's existing shop records from the canonical ERP state.
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select state->'manufacturing'->'shops' as shops from public.erp_state where id='main'")
        row = cur.fetchone()
        shops = row["shops"] if row and row["shops"] else []
        if actor["role"] == "Salesman":
            cur.execute("select distinct unnest(shop_ids) as shop_id from public.sales_field_jobs where salesman_id=%s and status in ('assigned','active','completed')", (actor["id"],))
            assigned_ids = {item["shop_id"] for item in cur.fetchall()}
            return [shop for shop in shops if str(shop.get("id")) in assigned_ids]
        return shops


@router.post("/jobs/{job_id}/start", status_code=201)
def start_job(job_id: str, initial: LocationPoint, actor: dict = Depends(actor_context)):
    require_role(actor, "Salesman")
    validate_point_order(None, initial.model_dump())
    if (datetime.now(timezone.utc)-initial.client_timestamp.astimezone(timezone.utc)).total_seconds() > 120:
        raise HTTPException(422, "The initial location fix is stale. Request a fresh browser location and try again.")
    session_id = str(uuid4())
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select * from public.sales_field_jobs where id=%s and salesman_id=%s for update", (job_id, actor["id"]))
        job = cur.fetchone()
        if not job or job["status"] != "assigned":
            raise HTTPException(409, "This assigned job is unavailable or already started.")
        cur.execute("select 1 from public.sales_tracking_sessions where employee_id=%s and status='active'", (actor["id"],))
        if cur.fetchone():
            raise HTTPException(409, "End the existing tracking session before starting another job.")
        cur.execute("insert into public.sales_tracking_sessions(id,job_id,employee_id,status,started_at,last_location_at,device_info) values(%s,%s,%s,'active',%s,%s,%s) returning *",
                    (session_id, job_id, actor["id"], initial.client_timestamp, initial.client_timestamp, Jsonb(initial.device_info)))
        session = cur.fetchone()
        point = initial.model_dump()
        cur.execute("""insert into public.sales_location_points
          (session_id,latitude,longitude,accuracy_m,speed_mps,heading_deg,altitude_m,client_timestamp,sequence_number,quality_flag)
          values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
          (session_id, point["latitude"], point["longitude"], point["accuracy_m"], point["speed_mps"], point["heading_deg"], point["altitude_m"], point["client_timestamp"], point["sequence_number"], "good" if point["accuracy_m"] <= 100 else "weak_accuracy"))
        cur.execute("update public.sales_field_jobs set status='active',updated_at=now() where id=%s", (job_id,))
        cur.execute("insert into public.sales_tracking_events(session_id,event_type,details) values(%s,'session_started',%s)", (session_id, Jsonb({"notice": "Employee explicitly started GPS work session"})))
        cur.execute("""update public.shipment_tracking set tracking_session_id=%s,tracking_status='LIVE',updated_at=now()
          where field_job_id=%s and assigned_employee_id=%s and shipment_status in ('DISPATCHED','IN_TRANSIT')
          and tracking_session_id is null""",(session_id,job_id,actor["id"]))
        return session


@router.post("/sessions/{session_id}/points", status_code=201)
def add_points(session_id: str, body: PointBatch, actor: dict = Depends(actor_context)):
    require_role(actor, "Salesman")
    accepted = []
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select * from public.sales_tracking_sessions where id=%s and employee_id=%s and status='active' for update", (session_id, actor["id"]))
        session = cur.fetchone()
        if not session:
            raise HTTPException(409, "Active tracking session not found.")
        cur.execute("select sequence_number,latitude,longitude,client_timestamp from public.sales_location_points where session_id=%s order by sequence_number desc limit 1", (session_id,))
        previous = cur.fetchone()
        for model in body.points:
            point = model.model_dump()
            if point["client_timestamp"] < session["started_at"]:
                raise HTTPException(422, "Location timestamp predates this tracking session.")
            cur.execute("select 1 from public.sales_location_points where session_id=%s and sequence_number=%s", (session_id, point["sequence_number"]))
            if cur.fetchone():
                continue
            validate_point_order(previous, point)
            cur.execute("""insert into public.sales_location_points
              (session_id,latitude,longitude,accuracy_m,speed_mps,heading_deg,altitude_m,client_timestamp,sequence_number,quality_flag)
              values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id,server_timestamp""",
              (session_id, point["latitude"], point["longitude"], point["accuracy_m"], point["speed_mps"],
               point["heading_deg"], point["altitude_m"], point["client_timestamp"], point["sequence_number"],
               "good" if point["accuracy_m"] <= 100 else "weak_accuracy"))
            saved = cur.fetchone()
            accepted.append({**point, **saved})
            if previous and (point["client_timestamp"]-previous["client_timestamp"]).total_seconds() > 120:
                cur.execute("insert into public.sales_tracking_events(session_id,event_type,details) values(%s,'tracking_gap',%s)",
                  (session_id, Jsonb({"gap_seconds": int((point["client_timestamp"]-previous["client_timestamp"]).total_seconds()), "notice": "No browser GPS fix was received during this interval"})))
            previous = point
            cur.execute("select stale_after_seconds,max_accuracy_m,stop_radius_m,stop_duration_seconds from public.sales_tracking_settings where id='current'")
            tracking_settings = cur.fetchone() or {"stop_radius_m": 50, "stop_duration_seconds": 300}
            if point["accuracy_m"] <= tracking_settings["max_accuracy_m"]:
                radius = tracking_settings["stop_radius_m"]
                cur.execute("select * from public.sales_detected_stops where session_id=%s and ended_at is null order by started_at desc limit 1", (session_id,))
                open_stop = cur.fetchone()
                if open_stop and distance_m(open_stop, point) > radius:
                    cur.execute("update public.sales_detected_stops set ended_at=%s,duration_seconds=greatest(0,extract(epoch from (%s-started_at))::integer) where id=%s",
                      (point["client_timestamp"], point["client_timestamp"], open_stop["id"]))
                    open_stop = None
                if open_stop:
                    cur.execute("update public.sales_detected_stops set duration_seconds=greatest(0,extract(epoch from (%s-started_at))::integer) where id=%s",
                      (point["client_timestamp"], open_stop["id"]))
                else:
                    cur.execute("""select latitude,longitude,client_timestamp from public.sales_location_points
                      where session_id=%s and accuracy_m<=%s and client_timestamp >= %s - (%s * interval '1 second')
                      order by client_timestamp asc""", (session_id, tracking_settings["max_accuracy_m"], point["client_timestamp"], tracking_settings["stop_duration_seconds"]))
                    recent = cur.fetchall()
                    if len(recent) >= 3 and (point["client_timestamp"]-recent[0]["client_timestamp"]).total_seconds() >= tracking_settings["stop_duration_seconds"] and all(distance_m(recent[0], p) <= radius for p in recent):
                        cur.execute("insert into public.sales_detected_stops(session_id,started_at,latitude,longitude,radius_m,duration_seconds) values(%s,%s,%s,%s,%s,0)",
                          (session_id, recent[0]["client_timestamp"], recent[0]["latitude"], recent[0]["longitude"], radius))
        if not accepted:
            return {"accepted": [], "count": 0}
        last = accepted[-1]
        cur.execute("update public.sales_tracking_sessions set last_location_at=%s,last_heartbeat_at=now(),updated_at=now() where id=%s",
                    (last["client_timestamp"], session_id))
    return {"accepted": accepted, "count": len(accepted)}


@router.post("/sessions/{session_id}/heartbeat")
def heartbeat(session_id: str, body: DeviceHeartbeat | None = None, actor: dict = Depends(actor_context)):
    require_role(actor, "Salesman")
    with get_connection() as conn, conn.cursor() as cur:
        device = body.device_info if body else {}
        cur.execute("update public.sales_tracking_sessions set last_heartbeat_at=now(),device_info=case when %s='{}'::jsonb then device_info else %s end,updated_at=now() where id=%s and employee_id=%s and status='active' returning id,last_location_at,last_heartbeat_at,device_info",
                    (Jsonb(device), Jsonb(device), session_id, actor["id"]))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Active session not found.")
        return row


@router.post("/sessions/{session_id}/end")
def end_session(session_id: str, actor: dict = Depends(actor_context)):
    require_role(actor, "Salesman")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("update public.sales_tracking_sessions set status='ended',ended_at=now(),updated_at=now() where id=%s and employee_id=%s and status='active' returning *",
                    (session_id, actor["id"]))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Active tracking session not found.")
        cur.execute("update public.sales_field_jobs set status='completed',updated_at=now() where id=%s", (row["job_id"],))
        cur.execute("update public.sales_detected_stops set ended_at=now(),duration_seconds=greatest(0,extract(epoch from (now()-started_at))::integer) where session_id=%s and ended_at is null", (session_id,))
        cur.execute("update public.sales_job_visits set checked_out_at=now(),updated_at=now() where job_id=%s and employee_id=%s and checked_out_at is null", (row["job_id"], actor["id"]))
        cur.execute("insert into public.sales_tracking_events(session_id,event_type,details) values(%s,'session_ended',%s)", (session_id, Jsonb({"notice": "Employee explicitly ended GPS work session"})))
        return row


@router.get("/jobs/{job_id}/route")
def job_route(job_id: str, actor: dict = Depends(actor_context)):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select * from public.sales_field_jobs where id=%s", (job_id,))
        job = cur.fetchone()
        if not job:
            raise HTTPException(404, "Job not found.")
        if actor["role"] == "Salesman" and job["salesman_id"] != actor["id"]:
            raise HTTPException(403, "You may view only your own jobs.")
        if actor["role"] == "Sales Officer" and job["sales_officer_id"] != actor["id"]:
            raise HTTPException(403, "This job is outside your assigned team.")
        cur.execute("""select p.* from public.sales_location_points p join public.sales_tracking_sessions s on s.id=p.session_id
          where s.job_id=%s order by p.client_timestamp asc""", (job_id,))
        return {"job": job, "points": cur.fetchall()}


def _shipment_scope(actor: dict) -> tuple[str, tuple]:
    if actor["role"] == "Salesman":
        return "st.assigned_employee_id=%s", (actor["id"],)
    return "st.field_job_id in (select id from public.sales_field_jobs where sales_officer_id=%s)", (actor["id"],)


@router.get("/shipments")
def shipments(actor: dict = Depends(actor_context)):
    scope, params = _shipment_scope(actor)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"""select st.*,gp.number as gate_pass_number,gp.status as gate_pass_status,
            e.payload->>'name' as assigned_employee_name,j.sales_officer_id,j.territory,
            s.status as session_status,s.last_location_at,s.last_heartbeat_at,s.device_info,
            (select row_to_json(p) from (select latitude,longitude,accuracy_m,speed_mps,heading_deg,client_timestamp,server_timestamp
              from public.sales_location_points where session_id=st.tracking_session_id order by sequence_number desc limit 1) p) as last_point,
            (select row_to_json(stp) from (select latitude,longitude,started_at,ended_at,duration_seconds
              from public.sales_detected_stops where session_id=st.tracking_session_id order by started_at desc limit 1) stp) as latest_stop
          from public.shipment_tracking st join public.gate_passes gp on gp.id=st.gate_pass_id
          join public.employees e on e.id=st.assigned_employee_id
          left join public.sales_field_jobs j on j.id=st.field_job_id
          left join public.sales_tracking_sessions s on s.id=st.tracking_session_id
          where {scope} order by st.dispatched_at desc""", params)
        rows=cur.fetchall()
        cur.execute("select stale_after_seconds from public.sales_tracking_settings where id='current'")
        tracking_settings=cur.fetchone()
        stale_after_seconds=tracking_settings['stale_after_seconds'] if tracking_settings else 120
        for row in rows:
            if row["shipment_status"] in {"DELIVERED","CLOSED","DELIVERY_FAILED","RETURNING"}:
                row["tracking_status"]="ENDED" if row["session_status"] != "active" else "LIVE"
            elif row["session_status"] == "active":
                last = row["last_location_at"]
                age = (datetime.now(timezone.utc)-last).total_seconds() if last else 10**9
                row["tracking_status"] = "LIVE" if age <= stale_after_seconds else "STALE"
            elif row["session_status"] == "ended":
                row["tracking_status"]="INTERRUPTED"
            else:
                row["tracking_status"]="AWAITING_LOCATION"
        return rows


@router.get("/shipments/{shipment_id}")
def shipment_detail(shipment_id: str, actor: dict = Depends(actor_context)):
    scope, params = _shipment_scope(actor)
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(f"""select st.*,gp.number as gate_pass_number,gp.status as gate_pass_status,
            gp.origin,gp.expected_at,gp.vehicle_number,gp.destination as pass_destination,
            e.payload->>'name' as assigned_employee_name,e.payload->>'phone' as assigned_employee_phone,
            s.status as session_status,s.last_location_at,s.last_heartbeat_at,s.device_info
          from public.shipment_tracking st join public.gate_passes gp on gp.id=st.gate_pass_id
          join public.employees e on e.id=st.assigned_employee_id
          left join public.sales_tracking_sessions s on s.id=st.tracking_session_id
          where st.id=%s and {scope}""", (shipment_id,*params))
        row=cur.fetchone()
        if not row:
            raise HTTPException(404,"Shipment is not in your authorized work scope.")
        if row["tracking_session_id"]:
            cur.execute("select * from public.sales_location_points where session_id=%s order by client_timestamp",(row["tracking_session_id"],))
            points=cur.fetchall()
            cur.execute("select * from public.sales_detected_stops where session_id=%s order by started_at",(row["tracking_session_id"],))
            stops=cur.fetchall()
            cur.execute("select * from public.sales_tracking_events where session_id=%s or (job_id=%s and event_type='shipment_dispatched') order by created_at",(row["tracking_session_id"],row["field_job_id"]))
            events=cur.fetchall()
        else:
            points=[];stops=[];events=[]
        distance=0.0
        for previous,current in zip(points,points[1:]):
            seconds=(current["client_timestamp"]-previous["client_timestamp"]).total_seconds()
            if seconds>0 and seconds<=120 and previous["accuracy_m"]<=100 and current["accuracy_m"]<=100:
                distance+=distance_m(previous,current)
        cur.execute("select i.id,i.kind,i.reference_id,i.description,i.unit,i.quantity,i.moved_quantity from public.gate_pass_items i where i.pass_id=%s order by i.id",(row["gate_pass_id"],))
        items=cur.fetchall()
        cur.execute("select * from public.shipment_delivery_confirmations where shipment_id=%s order by confirmed_at desc limit 1",(shipment_id,))
        delivery=cur.fetchone()
        cur.execute("select quantities from public.shipment_delivery_confirmations where shipment_id=%s",(shipment_id,))
        cumulative_delivered={item['id']:Decimal(0) for item in items}
        for record in cur.fetchall():
            for item_id,quantity in record['quantities'].items():
                if item_id in cumulative_delivered:cumulative_delivered[item_id]+=Decimal(quantity)
        last=points[-1] if points else None
        age=(datetime.now(timezone.utc)-last["client_timestamp"].astimezone(timezone.utc)).total_seconds() if last else None
        cur.execute("select stale_after_seconds from public.sales_tracking_settings where id='current'")
        tracking_settings=cur.fetchone()
        stale_after_seconds=tracking_settings['stale_after_seconds'] if tracking_settings else 120
        tracking="AWAITING_LOCATION" if row["session_status"] is None else "INTERRUPTED" if row["session_status"]!="active" else "LIVE" if age is not None and age<=stale_after_seconds else "STALE"
        if row["shipment_status"] in {"DELIVERED","CLOSED"}: tracking="ENDED"
        return {**row,"tracking_status":tracking,"points":points,"stops":stops,"events":events,"items":items,
            "delivery":delivery,"cumulative_delivered":{key:str(value) for key,value in cumulative_delivered.items()},"recorded_distance_m":round(distance,1),"last_point":last,
            "tracking_gap":age is None or age>120,"last_fix_age_seconds":None if age is None else max(0,int(age))}


@router.post("/shipments/{shipment_id}/delivery",status_code=201)
def confirm_shipment_delivery(shipment_id: str, body: ShipmentDeliveryInput, actor: dict = Depends(actor_context)):
    require_role(actor,"Salesman")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""select st.*,gp.status as pass_status from public.shipment_tracking st
          join public.gate_passes gp on gp.id=st.gate_pass_id
          where st.id=%s and st.assigned_employee_id=%s for update of st""",(shipment_id,actor["id"]))
        shipment=cur.fetchone()
        if not shipment:
            raise HTTPException(404,"Shipment is not assigned to this employee.")
        if shipment["shipment_status"] in {"DELIVERED","CLOSED","DELIVERY_FAILED","RETURNING"}:
            raise HTTPException(409,"This shipment has already been resolved.")
        if shipment["pass_status"]!="COMPLETED":
            raise HTTPException(409,"The linked Gate Pass movement is not complete.")
        cur.execute("select id,moved_quantity from public.gate_pass_items where pass_id=%s",(shipment["gate_pass_id"],))
        items={row["id"]:row["moved_quantity"] for row in cur.fetchall()}
        if set(body.quantities)-set(items):
            raise HTTPException(422,"Delivery includes an item outside the linked Gate Pass.")
        quantities={key:Decimal(value) for key,value in body.quantities.items()}
        if any(value<0 or value>items[key] for key,value in quantities.items()):
            raise HTTPException(422,"Delivered quantity must be between zero and its gate-exit quantity.")
        cur.execute("select status,quantities from public.shipment_delivery_confirmations where shipment_id=%s order by confirmed_at",(shipment_id,))
        prior=cur.fetchall()
        cumulative={key:Decimal(0) for key in items}
        for record in prior:
            for key,value in record["quantities"].items():
                if key in cumulative:cumulative[key]+=Decimal(value)
        totals={key:cumulative[key]+quantities.get(key,Decimal(0)) for key in items}
        if any(totals[key]>items[key] for key in items):
            raise HTTPException(409,"This confirmation would exceed quantities authorized at gate exit.")
        delivered_total=sum(totals.values())
        expected_total=sum(items.values())
        if body.status=="DELIVERED" and (expected_total<=0 or delivered_total!=expected_total or any(totals[key]!=items[key] for key in items)):
            raise HTTPException(422,"A full delivery must reconcile every item to its gate-exit quantity. Use partial delivery until all quantities are confirmed.")
        if body.status=="PARTIALLY_DELIVERED" and not (0<delivered_total<expected_total):
            raise HTTPException(422,"A partial delivery must record some, but not all, authorized quantities.")
        if body.status in {"DELIVERY_FAILED","RETURNING"} and any(quantities.values()):
            raise HTTPException(422,"Failed or returning deliveries cannot claim received quantities.")
        if body.status in {"DELIVERED","PARTIALLY_DELIVERED"} and not body.recipient_name.strip():
            raise HTTPException(422,"Record the recipient's name for delivery confirmation.")
        confirmation_id="POD-"+uuid4().hex
        cur.execute("""insert into public.shipment_delivery_confirmations
          (id,shipment_id,confirmed_by,recipient_name,status,quantities,remarks)
          values(%s,%s,%s,%s,%s,%s,%s) returning *""",
          (confirmation_id,shipment_id,actor["id"],body.recipient_name.strip(),body.status,Jsonb({k:str(v) for k,v in quantities.items()}),body.remarks))
        delivery=cur.fetchone()
        terminal=body.status=="DELIVERED"
        cur.execute("update public.shipment_tracking set shipment_status=%s,tracking_status=%s,updated_at=now() where id=%s",
          (body.status,"ENDED" if terminal else "LIVE",shipment_id))
        if terminal and shipment["tracking_session_id"]:
            cur.execute("update public.sales_tracking_sessions set status='ended',ended_at=now(),updated_at=now() where id=%s and status='active' returning job_id",(shipment["tracking_session_id"],))
            ended=cur.fetchone()
            if ended:
                cur.execute("insert into public.sales_tracking_events(session_id,event_type,details) values(%s,'shipment_delivery_recorded',%s)",(shipment["tracking_session_id"],Jsonb({"shipment_id":shipment_id,"delivery_id":confirmation_id,"status":body.status})))
        return delivery


@router.get("/visits")
def list_visits(actor: dict = Depends(actor_context)):
    with get_connection() as conn, conn.cursor() as cur:
        if actor["role"] == "Salesman":
            cur.execute("select * from public.sales_job_visits where employee_id=%s order by checked_in_at desc", (actor["id"],))
        else:
            cur.execute("select * from public.sales_job_visits where sales_officer_id=%s order by checked_in_at desc", (actor["id"],))
        return cur.fetchall()


@router.post("/jobs/{job_id}/visits", status_code=201)
def check_in(job_id: str, body: VisitCreate, actor: dict = Depends(actor_context)):
    require_role(actor, "Salesman")
    visit_id = str(uuid4())
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("select * from public.sales_field_jobs where id=%s and salesman_id=%s and status='active'", (job_id, actor["id"]))
        job = cur.fetchone()
        if not job or body.shop_id not in job["shop_ids"]:
            raise HTTPException(403, "Check in only to a shop assigned to your active job.")
        cur.execute("select 1 from public.sales_job_visits where job_id=%s and shop_id=%s and checked_out_at is null", (job_id, body.shop_id))
        if cur.fetchone():
            raise HTTPException(409, "This shop already has an open visit for the active job.")
        if body.sales_order_id:
            cur.execute("""select 1 from public.erp_state, jsonb_array_elements(state->'manufacturing'->'orders') order_row
              where erp_state.id='main' and order_row->>'id'=%s and order_row->>'shopId'=%s limit 1""", (body.sales_order_id, body.shop_id))
            if not cur.fetchone():
                raise HTTPException(422, "The sales order must exist in the ERP and belong to this visited shop.")
        cur.execute("insert into public.sales_job_visits(id,job_id,employee_id,sales_officer_id,shop_id,outcome,notes,latitude,longitude,sales_order_id) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning *",
          (visit_id, job_id, actor["id"], job["sales_officer_id"], body.shop_id, body.outcome, body.notes, body.latitude, body.longitude, body.sales_order_id))
        return cur.fetchone()


@router.put("/visits/{visit_id}")
def update_visit(visit_id: str, body: VisitUpdate, actor: dict = Depends(actor_context)):
    require_role(actor, "Salesman")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("update public.sales_job_visits set outcome=%s,notes=%s,sales_order_id=%s,checked_out_at=now(),updated_at=now() where id=%s and employee_id=%s and checked_out_at is null returning *",
          (body.outcome, body.notes, body.sales_order_id, visit_id, actor["id"]))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Open visit not found.")
        return row


@router.get("/officer/overview")
def officer_overview(actor: dict = Depends(actor_context)):
    require_role(actor, "Sales Officer")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""select e.id as salesman_id,e.payload->>'name' as name,
          coalesce(e.payload->>'phone',e.payload->>'phoneNumber',e.payload->>'mobile',e.payload->>'telephone','') as phone,
          e.payload->>'email' as email,e.payload->>'department' as department,
          j.id as job_id,j.territory,j.status as job_status,j.work_date,j.starts_at,j.ends_at,j.shop_ids,j.instructions,
          s.id as session_id,s.status as tracking_status,s.last_location_at,s.started_at,
          s.last_heartbeat_at,s.device_info,s.ended_at,
          (select row_to_json(p) from (select latitude,longitude,accuracy_m,client_timestamp,sequence_number
             from public.sales_location_points where session_id=s.id order by sequence_number desc limit 1) p) as last_point,
          (select count(*) from public.sales_job_visits v where v.job_id=j.id) as visits_completed
          from public.employees e
          left join lateral (select * from public.sales_field_jobs fj where fj.salesman_id=e.id and fj.sales_officer_id=%s
            order by (fj.status='active') desc,fj.work_date desc,fj.created_at desc limit 1) j on true
          left join lateral (select * from public.sales_tracking_sessions x where x.job_id=j.id order by x.started_at desc limit 1) s on true
          where e.payload->>'role'='Salesman' and e.payload->>'status'='Active'
            and (e.payload->>'supervisorId'=%s or e.payload->>'supervisor_id'=%s or exists
              (select 1 from public.sales_field_jobs authorized where authorized.salesman_id=e.id and authorized.sales_officer_id=%s))
          order by e.payload->>'name'""", (actor["id"], actor["id"], actor["id"], actor["id"]))
        rows = cur.fetchall()
        cur.execute("select stale_after_seconds from public.sales_tracking_settings where id='current'")
        stale_settings = cur.fetchone()
        stale_after_seconds = stale_settings["stale_after_seconds"] if stale_settings else 120
        for row in rows:
            row["stale_after_seconds"] = stale_after_seconds
            if row["session_id"]:
                cur.execute("""select coalesce(sum(6371000*2*asin(sqrt(least(1,
                  sin(radians(latitude-lag_lat)/2)^2 + cos(radians(lag_lat))*cos(radians(latitude))*sin(radians(longitude-lag_lon)/2)^2)))),0) as meters
                  from (select latitude,longitude,accuracy_m,client_timestamp,
                    lag(latitude) over(order by client_timestamp) as lag_lat,
                    lag(longitude) over(order by client_timestamp) as lag_lon,
                    lag(accuracy_m) over(order by client_timestamp) as lag_accuracy,
                    extract(epoch from (client_timestamp-lag(client_timestamp) over(order by client_timestamp))) as gap_seconds
                    from public.sales_location_points where session_id=%s) p
                  where lag_lat is not null and accuracy_m<=100 and lag_accuracy<=100 and gap_seconds<=120""", (row["session_id"],))
                row["recorded_distance_m"] = cur.fetchone()["meters"]
                cur.execute("select count(*) as count from public.sales_detected_stops where session_id=%s", (row["session_id"],))
                row["detected_stops"] = cur.fetchone()["count"]
                cur.execute("select count(*) as count from public.sales_job_visits where job_id=%s and checked_out_at is not null", (row["job_id"],))
                row["visits_completed"] = cur.fetchone()["count"]
                cur.execute("select count(*) as count from public.sales_job_visits where job_id=%s", (row["job_id"],))
                row["visits_total"] = cur.fetchone()["count"]
            else:
                row["recorded_distance_m"] = 0
                row["detected_stops"] = 0
                row["visits_total"] = 0
        return rows


@router.get("/officer/salesmen/{salesman_id}/dashboard")
def salesman_dashboard(salesman_id: str, work_date: date = date.today(), actor: dict = Depends(actor_context)):
    """Detailed shift view. Sales Officers can read only employees in their own team."""
    require_role(actor, "Sales Officer")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""select e.id,e.payload from public.employees e
          where e.id=%s and e.payload->>'role'='Salesman' and e.payload->>'status'='Active'
          and (e.payload->>'supervisorId'=%s or e.payload->>'supervisor_id'=%s or exists
            (select 1 from public.sales_field_jobs a where a.salesman_id=e.id and a.sales_officer_id=%s))""",
            (salesman_id, actor["id"], actor["id"], actor["id"]))
        employee = cur.fetchone()
        if not employee:
            raise HTTPException(404, "Salesman is not in your authorized team.")
        cur.execute("""select j.*, s.id as session_id,s.status as tracking_status,s.started_at,s.ended_at,
            s.last_location_at,s.last_heartbeat_at,s.device_info
          from public.sales_field_jobs j left join lateral (
            select * from public.sales_tracking_sessions x where x.job_id=j.id order by x.started_at desc limit 1
          ) s on true where j.salesman_id=%s and j.sales_officer_id=%s and j.work_date=%s
          order by j.created_at desc""", (salesman_id, actor["id"], work_date))
        jobs = cur.fetchall()
        job_ids = [j["id"] for j in jobs]
        sessions = []
        for job in jobs:
            session = {k:job[k] for k in ("session_id","tracking_status","started_at","ended_at","last_location_at","last_heartbeat_at","device_info")}
            if session["session_id"]:
                cur.execute("""select * from public.sales_location_points where session_id=%s order by client_timestamp""", (session["session_id"],))
                points = cur.fetchall()
                cur.execute("""select * from public.sales_detected_stops where session_id=%s order by started_at""", (session["session_id"],))
                stops = cur.fetchall()
                cur.execute("""select * from public.sales_tracking_events where session_id=%s order by created_at""", (session["session_id"],))
                events = cur.fetchall()
                moving_seconds = 0
                for a,b in zip(points,points[1:]):
                    seconds=(b["client_timestamp"]-a["client_timestamp"]).total_seconds()
                    if 0 < seconds <= 120 and a["accuracy_m"] <= 100 and b["accuracy_m"] <= 100:
                        metres=distance_m(a,b)
                        if metres/seconds>.5: moving_seconds += seconds
                session.update(points=points,stops=stops,events=events,
                    observed_moving_seconds=int(moving_seconds),
                    observed_stopped_seconds=sum(int(x["duration_seconds"] or 0) for x in stops),
                    observed_distance_m=sum(distance_m(a,b) for a,b in zip(points,points[1:])
                        if a["accuracy_m"]<=100 and b["accuracy_m"]<=100 and
                        0<(b["client_timestamp"]-a["client_timestamp"]).total_seconds()<=120))
            else:
                session.update(points=[],stops=[],events=[],observed_moving_seconds=0,observed_stopped_seconds=0,observed_distance_m=0)
            session["job"] = {k:job[k] for k in ("id","work_date","starts_at","ends_at","territory","instructions","shop_ids","status")}
            sessions.append(session)
        cur.execute("""select v.*,s.payload as shop from public.sales_job_visits v
          left join public.erp_state es on es.id='main'
          left join lateral jsonb_array_elements(coalesce(es.state->'manufacturing'->'shops','[]'::jsonb)) s(payload)
            on s.payload->>'id'=v.shop_id
          where v.employee_id=%s and v.sales_officer_id=%s and v.job_id=any(%s)
          order by v.checked_in_at""", (salesman_id, actor["id"], job_ids))
        visits = cur.fetchall() if job_ids else []
        points=[p for s in sessions for p in s["points"]]
        stops=[stop for s in sessions for stop in s["stops"]]
        shop_records=conn.execute("select state->'manufacturing'->'shops' as shops from public.erp_state where id='main'").fetchone()
        shop_list=(shop_records["shops"] or []) if shop_records else []
        for stop in stops:
            nearby=[]
            for shop in shop_list:
                # Only existing ERP shop coordinates may provide a place label.
                lat=shop.get("latitude",shop.get("lat"));lon=shop.get("longitude",shop.get("lng",shop.get("lon")))
                if lat is None or lon is None: continue
                d=distance_m({"latitude":stop["latitude"],"longitude":stop["longitude"]},{"latitude":float(lat),"longitude":float(lon)})
                if d<=250: nearby.append((d,shop.get("name","Customer")))
            stop["place_name"]=min(nearby)[1] if nearby else "Unlabelled stop"
            stop["place_distance_m"]=round(min(nearby)[0]) if nearby else None
        return {"employee":{"id":employee["id"],"name":employee["payload"].get("name"),
              "phone":employee["payload"].get("phone") or employee["payload"].get("phoneNumber") or employee["payload"].get("mobile") or employee["payload"].get("telephone"),
              "email":employee["payload"].get("email"),"department":employee["payload"].get("department"),
              "role":employee["payload"].get("role"),"territory":jobs[0]["territory"] if jobs else None,
              "region":employee["payload"].get("region"),"team":employee["payload"].get("team")},
            "work_date":work_date,"jobs":jobs,"sessions":sessions,"visits":visits,
            "points":points,"stops":stops,
            "summary":{"distance_m":sum(s["observed_distance_m"] for s in sessions),
              "moving_seconds":sum(s["observed_moving_seconds"] for s in sessions),
              "stopped_seconds":sum(s["observed_stopped_seconds"] for s in sessions),
              "stops":len(stops),"visits":len(visits),
              "visits_completed":sum(bool(v["checked_out_at"]) for v in visits),
              "first_started_at":next((s["started_at"] for s in sessions if s.get("started_at")),None),
              "last_heartbeat_at":max((s["last_heartbeat_at"] for s in sessions if s.get("last_heartbeat_at")),default=None)}}


@router.websocket("/ws")
async def officer_live(websocket: WebSocket):
    # Demo identity is intentionally not a production authentication mechanism.
    role = websocket.query_params.get("role")
    employee_id = websocket.query_params.get("employee_id")
    await websocket.accept()
    try:
        if role != "Sales Officer" or not employee_id:
            await websocket.close(code=4403)
            return
        while True:
            try:
                data = officer_overview(actor_context(role, employee_id))
                await websocket.send_json(jsonable_encoder({"type": "overview", "items": data}))
            except Exception:
                await websocket.send_json({"type": "error", "message": "Live update unavailable; retrying."})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return

