"""PostgreSQL database connection and query helpers."""

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras

_pool = None


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


def get_connection():
    """Get a new database connection."""
    return psycopg2.connect(get_database_url())


@contextmanager
def get_cursor(commit=True):
    """Context manager yielding a RealDictCursor. Auto-commits on success."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
            if commit:
                conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Run the initial migration if tables don't exist."""
    migration = Path(__file__).parent / "migrations" / "001_initial.sql"
    if not migration.exists():
        return
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(migration.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


def execute(sql: str, params: tuple | dict = None, returning: bool = False):
    """Execute a single query. Returns the first row if returning=True."""
    with get_cursor() as cur:
        cur.execute(sql, params)
        if returning:
            return dict(cur.fetchone()) if cur.description else None
        return None


def fetch_one(sql: str, params: tuple | dict = None) -> dict | None:
    """Fetch a single row as a dict."""
    with get_cursor(commit=False) as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_all(sql: str, params: tuple | dict = None) -> list[dict]:
    """Fetch all rows as a list of dicts."""
    with get_cursor(commit=False) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
