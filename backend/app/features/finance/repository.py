from backend.app.shared.service import StateCollectionService

FINANCE_RESOURCES = {"invoices": "invoices", "expenses": "expenses"}

class FinanceRepository:
    def records(self, resource: str) -> StateCollectionService:
        return StateCollectionService(FINANCE_RESOURCES[resource])
