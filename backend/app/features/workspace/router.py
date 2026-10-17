from fastapi import APIRouter, HTTPException
from backend.app.core.errors import BackendNotConfigured, DatabaseUnavailable
from backend.app.features.workspace.models import StateWrite
from backend.app.features.workspace.service import WorkspaceService

router = APIRouter(prefix="/api", tags=["Workspace"])
service = WorkspaceService()

@router.get("/state")
def get_state():
    return {"state": service.get_state()}

@router.put("/state")
def put_state(payload: StateWrite):
    try:
        return service.save_state(payload.state)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
