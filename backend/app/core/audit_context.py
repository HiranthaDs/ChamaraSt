from contextvars import ContextVar

# Populated from the current ERP request. These are demo/client-selected identities
# until the application is connected to verified server-side authentication.
request_actor: ContextVar[dict[str, str]] = ContextVar("request_actor", default={})

