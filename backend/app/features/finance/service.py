from backend.app.features.finance.repository import FinanceRepository

class FinanceService:
    def __init__(self, repository: FinanceRepository | None = None):
        self.repository = repository or FinanceRepository()
    def resource(self, name: str):
        return self.repository.records(name)
