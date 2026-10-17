from backend.app.shared.service import StateCollectionService

HR_RESOURCES = {"employees": "employees", "attendance": "attendance", "leaves": "leaves", "payroll": "payroll"}

class HRRepository:
    def records(self, resource: str) -> StateCollectionService:
        return StateCollectionService(HR_RESOURCES[resource])
