from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from backend.app.core.config import settings
from backend.app.core.errors import BackendNotConfigured
from backend.app.core.audit_context import request_actor


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Open a short-lived connection; Supabase's transaction pooler manages reuse."""
    if not settings.database_configured:
        raise BackendNotConfigured("Set DATABASE_URL in backend/.env to your Supabase transaction pooler URL.")
    try:
        with psycopg.connect(
            settings.database_url,
            connect_timeout=10,
            row_factory=dict_row,
            prepare_threshold=None,
        ) as connection:
            actor = request_actor.get()
            if actor:
                connection.execute(
                    "select set_config('orbit.actor_id', %s, true), "
                    "set_config('orbit.actor_role', %s, true), "
                    "set_config('orbit.actor_source', %s, true)",
                    (actor.get("id", ""), actor.get("role", ""), "demo-client"),
                )
            yield connection
    except BackendNotConfigured:
        raise
    except psycopg.Error as exc:
        from backend.app.core.errors import DatabaseUnavailable

        raise DatabaseUnavailable("Could not connect to the Supabase Postgres database.") from exc
