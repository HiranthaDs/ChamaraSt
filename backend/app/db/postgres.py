from contextlib import contextmanager
import logging
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from backend.app.core.config import settings
from backend.app.core.errors import BackendNotConfigured
from backend.app.core.audit_context import request_actor

logger = logging.getLogger(__name__)


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    """Open a short-lived connection; Supabase's transaction pooler manages reuse."""
    if not settings.database_configured:
        raise BackendNotConfigured("Set DATABASE_URL in backend/.env to your Supabase transaction pooler URL.")
    try:
        connection = psycopg.connect(
            settings.database_url,
            connect_timeout=10,
            row_factory=dict_row,
            prepare_threshold=None,
        )
    except psycopg.Error as exc:
        logger.exception("Could not connect to Supabase Postgres")
        from backend.app.core.errors import DatabaseUnavailable

        raise DatabaseUnavailable("Could not connect to the Supabase Postgres database.") from exc

    try:
        with connection:
            actor = request_actor.get()
            if actor:
                connection.execute(
                    "select set_config('orbit.actor_id', %s, true), "
                    "set_config('orbit.actor_role', %s, true), "
                    "set_config('orbit.actor_source', %s, true)",
                    (actor.get("id", ""), actor.get("role", ""), "demo-client"),
                )
            try:
                yield connection
            except psycopg.Error as exc:
                logger.exception("Supabase Postgres operation failed (SQLSTATE %s)", exc.sqlstate)
                from backend.app.core.errors import DatabaseUnavailable

                raise DatabaseUnavailable(
                    f"Supabase Postgres operation failed ({type(exc).__name__}, SQLSTATE {exc.sqlstate or 'unknown'})."
                ) from exc
    except BackendNotConfigured:
        raise
    except psycopg.Error as exc:
        from backend.app.core.errors import DatabaseUnavailable

        logger.exception("Supabase Postgres transaction failed (SQLSTATE %s)", exc.sqlstate)
        raise DatabaseUnavailable(
            f"Supabase Postgres transaction failed ({type(exc).__name__}, SQLSTATE {exc.sqlstate or 'unknown'})."
        ) from exc
