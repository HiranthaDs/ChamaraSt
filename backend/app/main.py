from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.core.audit_context import request_actor

from backend.app.core.config import settings
from backend.app.core.errors import BackendNotConfigured, DatabaseUnavailable, ResourceNotFound
from backend.app.features.finance.router import router as finance_router
from backend.app.features.health.router import router as health_router
from backend.app.features.hr.router import router as hr_router
from backend.app.features.manufacturing.router import router as manufacturing_router
from backend.app.features.manufacturing.cutting_router import router as cutting_router
from backend.app.features.sales_tracking.router import router as sales_tracking_router
from backend.app.features.gate_passes.router import router as gate_passes_router
from backend.app.features.workspace.router import router as workspace_router
from backend.app.features.traceability.router import router as traceability_router
from backend.app.features.production_jobs.router import router as production_jobs_router
from backend.app.features.product_development.router import router as product_development_router

app = FastAPI(title="Orbit ERP API", version="1.0.0", description="Feature-based HR, Finance, Manufacturing, and field-sales API")
app.add_middleware(CORSMiddleware, allow_origins=list(settings.frontend_origins),
                   allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|[a-zA-Z0-9-]+\.ngrok-free\.app)(:\d+)?$",
                   allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                   allow_headers=["Content-Type", "X-Demo-Role", "X-Demo-Employee-Id"])

@app.middleware("http")
async def bind_audit_actor(request: Request, call_next):
    actor = {
        "id": request.headers.get("X-Demo-Employee-Id", ""),
        "role": request.headers.get("X-Demo-Role", ""),
    }
    token = request_actor.set(actor if actor["id"] or actor["role"] else {})
    try:
        return await call_next(request)
    finally:
        request_actor.reset(token)

@app.exception_handler(BackendNotConfigured)
async def backend_not_configured(_: Request, exc: BackendNotConfigured):
    return JSONResponse(status_code=503, content={"detail": str(exc)})

@app.exception_handler(DatabaseUnavailable)
async def database_unavailable(_: Request, exc: DatabaseUnavailable):
    return JSONResponse(status_code=503, content={"detail": str(exc)})

@app.exception_handler(ResourceNotFound)
async def resource_not_found(_: Request, exc: ResourceNotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(ValueError)
async def value_error(_: Request, exc: ValueError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})

app.include_router(health_router)
app.include_router(workspace_router)
app.include_router(hr_router)
app.include_router(finance_router)
app.include_router(cutting_router)
app.include_router(manufacturing_router)
app.include_router(sales_tracking_router)
app.include_router(gate_passes_router)
app.include_router(traceability_router)
app.include_router(production_jobs_router)
app.include_router(product_development_router)
