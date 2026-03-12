"""User authentication and management."""

import bcrypt

from screener import db


def _hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_user(email: str, password: str, role: str = "readonly", name: str = None) -> dict:
    """Create a new user. Returns user dict (without password_hash)."""
    if role not in ("admin", "readonly"):
        raise ValueError("role must be 'admin' or 'readonly'")
    password_hash = _hash_password(password)
    user = db.execute(
        """INSERT INTO users (email, password_hash, role, name)
           VALUES (%s, %s, %s, %s)
           RETURNING id, email, role, name, created_at""",
        (email.lower().strip(), password_hash, role, name),
        returning=True,
    )
    return user


def authenticate(email: str, password: str) -> dict | None:
    """Verify credentials. Returns user dict (without password_hash) or None."""
    row = db.fetch_one(
        "SELECT * FROM users WHERE email = %s",
        (email.lower().strip(),),
    )
    if not row or not _check_password(password, row["password_hash"]):
        return None
    # Return user without password_hash
    return {k: v for k, v in row.items() if k != "password_hash"}


def get_user(user_id: int) -> dict | None:
    """Get user by ID (without password_hash)."""
    row = db.fetch_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if not row:
        return None
    return {k: v for k, v in row.items() if k != "password_hash"}


def get_all_users() -> list[dict]:
    """Get all users (without password_hash)."""
    rows = db.fetch_all("SELECT id, email, role, name, created_at, updated_at FROM users ORDER BY id")
    return rows


def update_user(user_id: int, **fields) -> dict | None:
    """Update user fields. Supports: email, password, role, name."""
    updates = {}
    params = {"id": user_id}

    if "email" in fields:
        updates["email"] = "%(email)s"
        params["email"] = fields["email"].lower().strip()
    if "role" in fields:
        if fields["role"] not in ("admin", "readonly"):
            raise ValueError("role must be 'admin' or 'readonly'")
        updates["role"] = "%(role)s"
        params["role"] = fields["role"]
    if "name" in fields:
        updates["name"] = "%(name)s"
        params["name"] = fields["name"]
    if "password" in fields:
        updates["password_hash"] = "%(password_hash)s"
        params["password_hash"] = _hash_password(fields["password"])

    if not updates:
        return get_user(user_id)

    set_clause = ", ".join(f"{k} = {v}" for k, v in updates.items())
    row = db.execute(
        f"UPDATE users SET {set_clause}, updated_at = NOW() WHERE id = %(id)s "
        f"RETURNING id, email, role, name, created_at, updated_at",
        params,
        returning=True,
    )
    return row


def delete_user(user_id: int) -> bool:
    """Delete a user."""
    with db.get_cursor() as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        return cur.rowcount > 0


def user_count() -> int:
    """Count total users."""
    row = db.fetch_one("SELECT COUNT(*) as cnt FROM users")
    return row["cnt"] if row else 0
