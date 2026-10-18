from typing import Any
from backend.app.core.errors import ResourceNotFound
from backend.app.shared.repository import WorkspaceStateRepository

class WorkspaceStateService:
    def __init__(self, repository: WorkspaceStateRepository | None = None):
        self.repository = repository or WorkspaceStateRepository()
    def get_state(self) -> dict[str, Any] | None:
        row = self.repository.get()
        return row.get("state") if row else None
    def save_state(self, state: dict[str, Any]) -> dict[str, Any]:
        required = {"employees", "leaves", "invoices", "expenses", "attendance", "settings", "activity"}
        missing = required.difference(state)
        if missing:
            raise ValueError(f"ERP state is missing sections: {', '.join(sorted(missing))}")
        if not isinstance(state.get("manufacturing"), dict):
            raise ValueError("ERP state must include a manufacturing object")
        return self.repository.save(state)

class StateCollectionService:
    OBJECT_MAPS = {"attendance", "labor", "alerts", "savedViews"}
    SINGLETONS = {"payroll", "settings", "preferences"}
    def __init__(self, collection: str, feature: str | None = None, repository: WorkspaceStateRepository | None = None):
        self.collection, self.feature = collection, feature
        self.repository = repository or WorkspaceStateRepository()
    def _load_root(self) -> dict[str, Any]:
        row = self.repository.get()
        if not row or not isinstance(row.get("state"), dict):
            # Allow the REST CRUD endpoints to be used before the frontend has
            # posted its initial demo snapshot. The first write persists this shape.
            return {
                "employees": [], "leaves": [], "invoices": [], "expenses": [],
                "attendance": {}, "payroll": None, "settings": {}, "activity": [],
                "manufacturing": {
                    "version": 1, "actor": {}, "preferences": {}, "demoStep": None,
                    "materials": [], "sheets": [], "cuts": [], "parts": [],
                    "products": [], "jobs": [], "machines": [], "labor": {},
                    "purchases": [], "maintenance": [], "goods": [], "bins": [],
                    "shops": [], "orders": [], "movements": [], "costs": [],
                    "alerts": {}, "audit": [], "savedViews": {},
                },
            }
        return row["state"]
    def _scope(self, root: dict[str, Any]) -> dict[str, Any]:
        return root.setdefault("manufacturing", {}) if self.feature == "manufacturing" else root
    def _records(self, scoped: dict[str, Any]) -> list[dict[str, Any]]:
        value = scoped.get(self.collection)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [{"id": key, **item} if isinstance(item, dict) else {"id": key, "value": item} for key, item in value.items()]
        return [{"id": "current", **value}] if self.collection in self.SINGLETONS and isinstance(value, dict) else []
    def list(self) -> list[dict[str, Any]]:
        return self._records(self._scope(self._load_root()))
    def get(self, record_id: str) -> dict[str, Any]:
        record = next((item for item in self.list() if str(item.get("id")) == record_id), None)
        if record is None:
            raise ResourceNotFound(f"{self.collection} record '{record_id}' was not found.")
        return record
    def create(self, record: dict[str, Any]) -> dict[str, Any]:
        root = self._load_root()
        scoped = self._scope(root)
        if self.collection in self.SINGLETONS:
            if scoped.get(self.collection) is not None:
                raise ValueError(f"{self.collection} already has a current record.")
            scoped[self.collection] = {k: v for k, v in record.items() if k != "id"}
        else:
            current = scoped.setdefault(self.collection, {} if self.collection in self.OBJECT_MAPS else [])
            if any(str(item.get("id")) == record["id"] for item in self._records(scoped)):
                raise ValueError(f"{self.collection} record '{record['id']}' already exists.")
            if isinstance(current, dict):
                current[record["id"]] = {k: v for k, v in record.items() if k != "id"}
            else:
                current.append(record)
        self.repository.save(root)
        return record
    def update(self, record_id: str, record: dict[str, Any]) -> dict[str, Any]:
        root = self._load_root()
        scoped = self._scope(root)
        current = scoped.get(self.collection)
        if self.collection in self.SINGLETONS:
            if current is None:
                raise ResourceNotFound(f"{self.collection} is empty.")
            scoped[self.collection] = {k: v for k, v in record.items() if k != "id"}
        elif isinstance(current, dict):
            if record_id not in current:
                raise ResourceNotFound(f"{self.collection} record '{record_id}' was not found.")
            current[record_id] = {k: v for k, v in record.items() if k != "id"}
        else:
            current = current if isinstance(current, list) else []
            index = next((i for i, item in enumerate(current) if str(item.get("id")) == record_id), None)
            if index is None:
                raise ResourceNotFound(f"{self.collection} record '{record_id}' was not found.")
            current[index] = {**record, "id": record_id}
            scoped[self.collection] = current
        self.repository.save(root)
        return {**record, "id": record_id}
    def delete(self, record_id: str) -> None:
        root = self._load_root()
        scoped = self._scope(root)
        current = scoped.get(self.collection)
        if self.collection in self.SINGLETONS:
            if current is None:
                raise ResourceNotFound(f"{self.collection} is empty.")
            scoped[self.collection] = None
        elif isinstance(current, dict):
            if record_id not in current:
                raise ResourceNotFound(f"{self.collection} record '{record_id}' was not found.")
            del current[record_id]
        else:
            current = current if isinstance(current, list) else []
            filtered = [item for item in current if str(item.get("id")) != record_id]
            if len(filtered) == len(current):
                raise ResourceNotFound(f"{self.collection} record '{record_id}' was not found.")
            scoped[self.collection] = filtered
        self.repository.save(root)
