from backend.app.shared.service import WorkspaceStateService
from backend.app.features.workspace.repository import WorkspaceRepository

class WorkspaceService(WorkspaceStateService):
    def __init__(self):
        super().__init__(WorkspaceRepository())
