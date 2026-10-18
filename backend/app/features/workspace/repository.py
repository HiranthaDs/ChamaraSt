from backend.app.shared.repository import WorkspaceStateRepository

class WorkspaceRepository(WorkspaceStateRepository):
    """Workspace persistence boundary; SQL RPC mirrors data into feature tables."""
