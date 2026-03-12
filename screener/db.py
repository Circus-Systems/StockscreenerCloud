"""PostgreSQL database connection and query helpers."""

import logging
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

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
    """Run pending migrations and seed admin user if needed."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Create migrations tracking table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS _migrations (
                    filename VARCHAR(200) PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            conn.commit()

            # Get already-applied migrations
            cur.execute("SELECT filename FROM _migrations ORDER BY filename")
            applied = {row[0] for row in cur.fetchall()}

            # Find and run pending migrations
            migrations_dir = Path(__file__).parent / "migrations"
            if migrations_dir.exists():
                migration_files = sorted(migrations_dir.glob("*.sql"))
                for mf in migration_files:
                    if mf.name not in applied:
                        logger.info("Applying migration: %s", mf.name)
                        cur.execute(mf.read_text(encoding="utf-8"))
                        cur.execute(
                            "INSERT INTO _migrations (filename) VALUES (%s)",
                            (mf.name,),
                        )
                        conn.commit()
                        logger.info("Migration applied: %s", mf.name)

        # Seed admin user if configured and no users exist
        _seed_admin(conn)

    finally:
        conn.close()


def _seed_admin(conn):
    """Create initial admin user from env vars if no users exist."""
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        return

    with conn.cursor() as cur:
        # Check if users table exists and is empty
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'users'
            )
        """)
        if not cur.fetchone()[0]:
            return

        cur.execute("SELECT COUNT(*) FROM users")
        count = cur.fetchone()[0]
        if count > 0:
            return

        # Create admin user
        import bcrypt
        password_hash = bcrypt.hashpw(
            admin_password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
        cur.execute(
            """INSERT INTO users (email, password_hash, role, name)
               VALUES (%s, %s, 'admin', 'Admin')""",
            (admin_email.lower().strip(), password_hash),
        )
        conn.commit()
        logger.info("Seeded admin user: %s", admin_email)


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
