from backend.app.features.hr.repository import HRRepository

class HRService:
    def __init__(self, repository: HRRepository | None = None):
        self.repository = repository or HRRepository()
    def resource(self, name: str):
        return self.repository.records(name)
