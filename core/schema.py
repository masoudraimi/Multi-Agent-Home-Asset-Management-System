"""Schema bootstrap — delegates to the active database provider."""


def ensure_schema() -> None:
    from db import get_provider
    get_provider().ensure_schema()
