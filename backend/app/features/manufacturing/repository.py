from backend.app.shared.service import StateCollectionService

MANUFACTURING_RESOURCES = {
    "materials": "materials", "sheets": "sheets", "cuts": "cuts", "parts": "parts",
    "products": "products", "jobs": "jobs", "machines": "machines", "labor": "labor",
    "purchases": "purchases", "maintenance": "maintenance", "goods": "goods",
    "bins": "bins", "shops": "shops", "orders": "orders", "movements": "movements",
    "costs": "costs", "alerts": "alerts", "audit": "audit", "saved-views": "savedViews",
}

class ManufacturingRepository:
    def records(self, resource: str) -> StateCollectionService:
        return StateCollectionService(MANUFACTURING_RESOURCES[resource], "manufacturing")
