"""Package for Monica cockpit persistence helpers."""


def ensure_schema(conn):
    from token_optimiser.db.cockpit_schema import ensure_schema as _ensure_schema

    return _ensure_schema(conn)
