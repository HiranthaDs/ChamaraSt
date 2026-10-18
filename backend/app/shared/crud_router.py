from typing import Any, Callable
from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, ValidationError
from backend.app.shared.models import RecordPayload
from backend.app.shared.service import StateCollectionService

def collection_router(prefix: str, tag: str, resources: dict[str, str], feature: str | None = None,
                      service_provider: Callable[[str], Any] | None = None,
                      schemas: dict[str, type[BaseModel]] | None = None) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])
    def service_for(resource: str) -> StateCollectionService:
        if resource not in resources:
            raise HTTPException(status_code=404, detail="Unknown resource for this feature.")
        return service_provider(resource) if service_provider else StateCollectionService(resources[resource], feature)
    def validated(resource: str, payload: dict[str, Any]) -> dict[str, Any]:
        schema = (schemas or {}).get(resource, RecordPayload)
        return schema.model_validate(payload).model_dump()
    @router.get("/{resource}")
    def list_records(resource: str):
        return service_for(resource).list()
    @router.post("/{resource}", status_code=status.HTTP_201_CREATED)
    def create_record(resource: str, payload: dict[str, Any]):
        return service_for(resource).create(validated(resource, payload))
    @router.get("/{resource}/{record_id}")
    def get_record(resource: str, record_id: str):
        return service_for(resource).get(record_id)
    @router.put("/{resource}/{record_id}")
    def update_record(resource: str, record_id: str, payload: dict[str, Any]):
        parsed = validated(resource, payload)
        if parsed["id"] != record_id:
            raise HTTPException(status_code=422, detail="URL id must match the record id.")
        return service_for(resource).update(record_id, parsed)
    @router.delete("/{resource}/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_record(resource: str, record_id: str):
        service_for(resource).delete(record_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return router
