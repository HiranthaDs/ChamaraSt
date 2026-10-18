from typing import Any
from backend.app.core.errors import DatabaseUnavailable
from backend.app.db.postgres import get_connection

class WorkspaceStateRepository:
    """Canonical snapshot; the SQL save RPC also updates each feature table atomically."""
    def get(self) -> dict[str, Any] | None:
        try:
            with get_connection() as connection, connection.cursor() as cursor:
                cursor.execute("select state, revision, updated_at from public.erp_state where id = %s", ("main",))
                return cursor.fetchone()
        except DatabaseUnavailable:
            raise
        except Exception as exc:
            raise DatabaseUnavailable("Could not read ERP data. Apply backend/schema.sql and verify Supabase settings.") from exc

    def save(self, state: dict[str, Any]) -> dict[str, Any]:
        try:
            import json

            with get_connection() as connection, connection.cursor() as cursor:
                cursor.execute("select public.save_erp_state(%s::jsonb) as saved", (json.dumps(state),))
                row = cursor.fetchone()
                if not row or not isinstance(row["saved"], dict):
                    raise ValueError("save_erp_state returned no database row")
                return row["saved"]
        except DatabaseUnavailable as exc:
            from fastapi import HTTPException
            sqlstate = getattr(exc.__cause__, 'sqlstate', None)
            if sqlstate == '40001':
                raise HTTPException(409, 'Production or product records changed in another workflow. Refresh before saving.') from exc
            if sqlstate == '42501':
                raise HTTPException(409, 'Managed production orders and engineering products must be changed through their workflow controls. Refresh this workspace.') from exc
            raise
        except Exception as exc:
            raise DatabaseUnavailable("Could not save ERP data. Apply backend/schema.sql and verify DATABASE_URL.") from exc
