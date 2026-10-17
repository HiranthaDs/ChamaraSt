from backend.app.features.manufacturing.repository import ManufacturingRepository

class ManufacturingService:
    def __init__(self, repository: ManufacturingRepository | None = None):
        self.repository = repository or ManufacturingRepository()
    def resource(self, name: str):
        return self.repository.records(name)
