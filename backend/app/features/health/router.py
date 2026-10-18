from fastapi import APIRouter
from backend.app.core.config import settings
from backend.app.db.postgres import get_connection

router = APIRouter(tags=["Health"])

@router.get("/api/health")
def health():
    if not settings.database_configured:
        return {"ok": False, "database": "not_configured"}
    try:
        with get_connection() as connection, connection.cursor() as cursor:
            cursor.execute("select id from public.erp_state where id = %s", ("main",))
        return {"ok": True, "database": "connected"}
    except Exception:
        return {"ok": False, "database": "unavailable"}
