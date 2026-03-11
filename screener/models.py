"""Database models — thin wrappers around screener.db for domain operations."""

from datetime import date, datetime
from decimal import Decimal

from screener import db


# ---------------------------------------------------------------------------
# Stocks
# ---------------------------------------------------------------------------

def get_or_create_stock(ticker: str, exchange: str = "NASDAQ", name: str = None) -> dict:
    """Find existing stock or create a new one. Returns stock dict."""
    exchange = exchange.upper()
    yf_ticker = f"{ticker.upper()}.AX" if exchange == "ASX" else ticker.upper()

    row = db.fetch_one(
        "SELECT * FROM stocks WHERE ticker = %s AND exchange = %s",
        (ticker.upper(), exchange),
    )
    if row:
        return row

    return db.execute(
        """INSERT INTO stocks (ticker, exchange, yf_ticker, name)
           VALUES (%s, %s, %s, %s)
           RETURNING *""",
        (ticker.upper(), exchange, yf_ticker, name),
        returning=True,
    )


def update_stock(stock_id: int, **fields) -> dict:
    """Update stock fields. Only updates fields that are passed."""
    allowed = {"name", "sector", "industry", "cik", "has_sec_filings"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_stock(stock_id)
    set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
    updates["id"] = stock_id
    return db.execute(
        f"UPDATE stocks SET {set_clause}, updated_at = NOW() WHERE id = %(id)s RETURNING *",
        updates,
        returning=True,
    )


def get_stock(stock_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM stocks WHERE id = %s", (stock_id,))


def get_stock_by_ticker(ticker: str, exchange: str = "NASDAQ") -> dict | None:
    return db.fetch_one(
        "SELECT * FROM stocks WHERE ticker = %s AND exchange = %s",
        (ticker.upper(), exchange.upper()),
    )


# ---------------------------------------------------------------------------
# Positions (Portfolio)
# ---------------------------------------------------------------------------

def add_position(
    stock_id: int,
    shares: Decimal | float,
    purchase_price: Decimal | float,
    purchase_date: date | str,
    currency: str = "USD",
    notes: str = None,
) -> dict:
    return db.execute(
        """INSERT INTO positions (stock_id, shares, purchase_price, purchase_date, currency, notes)
           VALUES (%s, %s, %s, %s, %s, %s)
           RETURNING *""",
        (stock_id, shares, purchase_price, purchase_date, currency, notes),
        returning=True,
    )


def update_position(position_id: int, **fields) -> dict:
    allowed = {"shares", "purchase_price", "purchase_date", "currency", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return get_position(position_id)
    set_clause = ", ".join(f"{k} = %({k})s" for k in updates)
    updates["id"] = position_id
    return db.execute(
        f"UPDATE positions SET {set_clause}, updated_at = NOW() WHERE id = %(id)s RETURNING *",
        updates,
        returning=True,
    )


def delete_position(position_id: int) -> bool:
    with db.get_cursor() as cur:
        cur.execute("DELETE FROM positions WHERE id = %s", (position_id,))
        return cur.rowcount > 0


def get_position(position_id: int) -> dict | None:
    return db.fetch_one("SELECT * FROM positions WHERE id = %s", (position_id,))


def get_all_positions() -> list[dict]:
    """Get all positions joined with stock info."""
    return db.fetch_all(
        """SELECT p.*, s.ticker, s.exchange, s.yf_ticker, s.name as stock_name
           FROM positions p
           JOIN stocks s ON s.id = p.stock_id
           ORDER BY s.ticker, p.purchase_date"""
    )


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def add_to_watchlist(stock_id: int, notes: str = None) -> dict:
    return db.execute(
        """INSERT INTO watchlist (stock_id, notes)
           VALUES (%s, %s)
           ON CONFLICT (stock_id) DO UPDATE SET notes = EXCLUDED.notes
           RETURNING *""",
        (stock_id, notes),
        returning=True,
    )


def remove_from_watchlist(watchlist_id: int) -> bool:
    with db.get_cursor() as cur:
        cur.execute("DELETE FROM watchlist WHERE id = %s", (watchlist_id,))
        return cur.rowcount > 0


def get_watchlist() -> list[dict]:
    return db.fetch_all(
        """SELECT w.*, s.ticker, s.exchange, s.yf_ticker, s.name as stock_name
           FROM watchlist w
           JOIN stocks s ON s.id = w.stock_id
           ORDER BY s.ticker"""
    )


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_setting(key: str, default: str = None) -> str | None:
    row = db.fetch_one("SELECT value FROM settings WHERE key = %s", (key,))
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    db.execute(
        """INSERT INTO settings (key, value, updated_at)
           VALUES (%s, %s, NOW())
           ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()""",
        (key, value),
    )


def get_all_settings() -> dict:
    rows = db.fetch_all("SELECT key, value FROM settings ORDER BY key")
    return {r["key"]: r["value"] for r in rows}


# ---------------------------------------------------------------------------
# Tracked stocks (portfolio + watchlist combined)
# ---------------------------------------------------------------------------

def get_all_tracked_stock_ids() -> list[int]:
    """Get unique stock IDs across portfolio and watchlist."""
    rows = db.fetch_all(
        """SELECT DISTINCT stock_id FROM (
               SELECT stock_id FROM positions
               UNION
               SELECT stock_id FROM watchlist
           ) t"""
    )
    return [r["stock_id"] for r in rows]
