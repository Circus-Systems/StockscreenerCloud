"""API v1 Blueprint — Auth, Portfolio, Watchlist, User Management."""

import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps

import jwt
from flask import Blueprint, g, jsonify, request

from screener import auth, models
from screener.data_service import StockDataService

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

_service = None


@api_v1.errorhandler(Exception)
def handle_error(e):
    """Catch-all for unhandled errors in v1 endpoints."""
    if isinstance(e, RuntimeError) and "DATABASE_URL" in str(e):
        return jsonify({"error": "Database not configured. Set DATABASE_URL environment variable."}), 503
    return jsonify({"error": str(e)}), 500


def _get_service() -> StockDataService:
    global _service
    if _service is None:
        _service = StockDataService(
            edgar_email=os.environ.get("EDGAR_EMAIL", "andrew@sailingcircus.com")
        )
    return _service


# ---------------------------------------------------------------------------
# JWT Auth
# ---------------------------------------------------------------------------

def require_auth(f):
    """Decorator: require valid JWT bearer token. Sets g.user_id and g.user_role."""
    @wraps(f)
    def decorated(*args, **kwargs):
        secret = os.environ.get("JWT_SECRET")
        if not secret:
            # Auth disabled — allow all requests (local dev without JWT_SECRET)
            g.user_id = None
            g.user_role = "admin"
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header[7:]
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        g.user_id = payload.get("user_id")
        g.user_role = payload.get("role", "readonly")
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator: require admin role (must be used after require_auth)."""
    @wraps(f)
    @require_auth
    def decorated(*args, **kwargs):
        if g.user_role != "admin":
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated


def _issue_token(user: dict) -> str:
    """Generate a JWT token for a user."""
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET not configured")
    return jwt.encode(
        {
            "user_id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc).replace(
                year=datetime.now(timezone.utc).year + 1
            ),
        },
        secret,
        algorithm="HS256",
    )


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@api_v1.route("/auth/login", methods=["POST"])
def auth_login():
    """Login with email/password. Returns JWT token + user info."""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = auth.authenticate(email, password)
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    token = _issue_token(user)
    return jsonify({
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "role": user["role"],
            "name": user["name"],
        },
    })


@api_v1.route("/auth/me", methods=["GET"])
@require_auth
def auth_me():
    """Get current user info."""
    if g.user_id is None:
        return jsonify({"id": None, "email": None, "role": "admin", "name": "Local Dev"})
    user = auth.get_user(g.user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "name": user["name"],
    })


# ---------------------------------------------------------------------------
# User Management (admin only)
# ---------------------------------------------------------------------------

@api_v1.route("/users", methods=["GET"])
@require_admin
def list_users():
    """List all users."""
    return jsonify(auth.get_all_users())


@api_v1.route("/users", methods=["POST"])
@require_admin
def create_user():
    """Create a new user. Body: { email, password, role?, name? }"""
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    role = data.get("role", "readonly")
    if role not in ("admin", "readonly"):
        return jsonify({"error": "role must be 'admin' or 'readonly'"}), 400

    try:
        user = auth.create_user(email, password, role, data.get("name"))
    except Exception as e:
        if "unique" in str(e).lower():
            return jsonify({"error": "Email already exists"}), 409
        raise

    return jsonify(user), 201


@api_v1.route("/users/<int:user_id>", methods=["PUT"])
@require_admin
def update_user(user_id):
    """Update a user. Body: { email?, password?, role?, name? }"""
    data = request.get_json(silent=True) or {}
    user = auth.update_user(user_id, **data)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


@api_v1.route("/users/<int:user_id>", methods=["DELETE"])
@require_admin
def delete_user(user_id):
    """Delete a user."""
    # Prevent self-deletion
    if g.user_id == user_id:
        return jsonify({"error": "Cannot delete your own account"}), 400
    if auth.delete_user(user_id):
        return jsonify({"message": "User deleted"})
    return jsonify({"error": "User not found"}), 404


# ---------------------------------------------------------------------------
# Portfolio (scoped to authenticated user)
# ---------------------------------------------------------------------------

@api_v1.route("/portfolio", methods=["GET"])
@require_auth
def list_portfolio():
    """List all positions with current prices and P&L."""
    positions = models.get_all_positions(user_id=g.user_id)
    service = _get_service()

    # Group by stock for efficient quote fetching
    stocks_seen = {}
    for p in positions:
        yf = p["yf_ticker"]
        if yf not in stocks_seen:
            try:
                quote = service.get_quote(yf)
                stocks_seen[yf] = quote.get("price")
            except Exception:
                stocks_seen[yf] = None

    results = []
    for p in positions:
        current_price = stocks_seen.get(p["yf_ticker"])
        cost_basis = float(p["shares"]) * float(p["purchase_price"])
        market_value = float(p["shares"]) * current_price if current_price else None
        pnl = market_value - cost_basis if market_value is not None else None
        pnl_pct = (pnl / cost_basis * 100) if pnl is not None and cost_basis else None

        results.append({
            "id": p["id"],
            "ticker": p["ticker"],
            "exchange": p["exchange"],
            "stockName": p["stock_name"],
            "shares": float(p["shares"]),
            "purchasePrice": float(p["purchase_price"]),
            "purchaseDate": str(p["purchase_date"]),
            "currency": p["currency"],
            "notes": p["notes"],
            "currentPrice": current_price,
            "costBasis": round(cost_basis, 2),
            "marketValue": round(market_value, 2) if market_value else None,
            "pnl": round(pnl, 2) if pnl is not None else None,
            "pnlPct": round(pnl_pct, 2) if pnl_pct is not None else None,
        })

    return jsonify(results)


@api_v1.route("/portfolio", methods=["POST"])
@require_auth
def add_portfolio_position():
    """Add a position. Body: { ticker, exchange?, shares, purchasePrice, purchaseDate, currency?, notes? }"""
    data = request.get_json(silent=True) or {}

    ticker = data.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400

    exchange = data.get("exchange", "NASDAQ").strip().upper()
    if exchange not in ("NASDAQ", "NYSE", "ASX"):
        return jsonify({"error": "exchange must be NASDAQ, NYSE, or ASX"}), 400

    try:
        shares = Decimal(str(data["shares"]))
        purchase_price = Decimal(str(data["purchasePrice"]))
    except (KeyError, InvalidOperation, TypeError):
        return jsonify({"error": "shares and purchasePrice are required numbers"}), 400

    purchase_date = data.get("purchaseDate")
    if not purchase_date:
        return jsonify({"error": "purchaseDate is required (YYYY-MM-DD)"}), 400

    # Get or create the stock record
    stock = models.get_or_create_stock(ticker, exchange)

    # Enrich stock info if name is missing
    if not stock.get("name"):
        try:
            service = _get_service()
            info = service.get_info(stock["yf_ticker"])
            models.update_stock(
                stock["id"],
                name=info.get("shortName") or info.get("longName"),
                sector=info.get("sector"),
                industry=info.get("industry"),
            )
        except Exception:
            pass

    # Check for SEC filings availability (US exchanges)
    if exchange in ("NASDAQ", "NYSE") and not stock.get("has_sec_filings"):
        try:
            service = _get_service()
            edgar = service.edgar
            edgar.lookup_company(ticker)
            models.update_stock(stock["id"], has_sec_filings=True)
        except Exception:
            models.update_stock(stock["id"], has_sec_filings=False)

    position = models.add_position(
        stock_id=stock["id"],
        shares=shares,
        purchase_price=purchase_price,
        purchase_date=purchase_date,
        user_id=g.user_id,
        currency=data.get("currency", "USD"),
        notes=data.get("notes"),
    )

    return jsonify({
        "id": position["id"],
        "stockId": stock["id"],
        "ticker": ticker,
        "exchange": exchange,
        "message": "Position added",
    }), 201


@api_v1.route("/portfolio/<int:position_id>", methods=["PUT"])
@require_auth
def update_portfolio_position(position_id):
    """Update a position. Body: { shares?, purchasePrice?, purchaseDate?, currency?, notes? }"""
    data = request.get_json(silent=True) or {}
    existing = models.get_position(position_id, user_id=g.user_id)
    if not existing:
        return jsonify({"error": "Position not found"}), 404

    updates = {}
    if "shares" in data:
        updates["shares"] = Decimal(str(data["shares"]))
    if "purchasePrice" in data:
        updates["purchase_price"] = Decimal(str(data["purchasePrice"]))
    if "purchaseDate" in data:
        updates["purchase_date"] = data["purchaseDate"]
    if "currency" in data:
        updates["currency"] = data["currency"]
    if "notes" in data:
        updates["notes"] = data["notes"]

    position = models.update_position(position_id, user_id=g.user_id, **updates)
    return jsonify({"id": position["id"], "message": "Position updated"})


@api_v1.route("/portfolio/<int:position_id>", methods=["DELETE"])
@require_auth
def delete_portfolio_position(position_id):
    """Delete a position."""
    if models.delete_position(position_id, user_id=g.user_id):
        return jsonify({"message": "Position deleted"})
    return jsonify({"error": "Position not found"}), 404


@api_v1.route("/portfolio/summary", methods=["GET"])
@require_auth
def portfolio_summary():
    """Aggregate portfolio: total value, cost basis, P&L."""
    positions = models.get_all_positions(user_id=g.user_id)
    service = _get_service()

    quotes = {}
    for p in positions:
        yf = p["yf_ticker"]
        if yf not in quotes:
            try:
                quotes[yf] = service.get_quote(yf).get("price")
            except Exception:
                quotes[yf] = None

    total_cost = 0.0
    total_value = 0.0
    has_value = False

    for p in positions:
        cost = float(p["shares"]) * float(p["purchase_price"])
        total_cost += cost
        price = quotes.get(p["yf_ticker"])
        if price is not None:
            total_value += float(p["shares"]) * price
            has_value = True

    pnl = total_value - total_cost if has_value else None
    pnl_pct = (pnl / total_cost * 100) if pnl is not None and total_cost else None

    return jsonify({
        "totalCostBasis": round(total_cost, 2),
        "totalMarketValue": round(total_value, 2) if has_value else None,
        "totalPnl": round(pnl, 2) if pnl is not None else None,
        "totalPnlPct": round(pnl_pct, 2) if pnl_pct is not None else None,
        "positionCount": len(positions),
    })


# ---------------------------------------------------------------------------
# Watchlist (scoped to authenticated user)
# ---------------------------------------------------------------------------

@api_v1.route("/watchlist", methods=["GET"])
@require_auth
def list_watchlist():
    """List watchlist with current prices."""
    items = models.get_watchlist(user_id=g.user_id)
    service = _get_service()

    results = []
    for w in items:
        current_price = None
        try:
            quote = service.get_quote(w["yf_ticker"])
            current_price = quote.get("price")
        except Exception:
            pass

        results.append({
            "id": w["id"],
            "stockId": w["stock_id"],
            "ticker": w["ticker"],
            "exchange": w["exchange"],
            "stockName": w["stock_name"],
            "notes": w["notes"],
            "addedAt": w["added_at"].isoformat() if w["added_at"] else None,
            "currentPrice": current_price,
        })

    return jsonify(results)


@api_v1.route("/watchlist", methods=["POST"])
@require_auth
def add_to_watchlist():
    """Add to watchlist. Body: { ticker, exchange?, notes? }"""
    data = request.get_json(silent=True) or {}

    ticker = data.get("ticker", "").strip().upper()
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400

    exchange = data.get("exchange", "NASDAQ").strip().upper()

    stock = models.get_or_create_stock(ticker, exchange)

    # Enrich stock info
    if not stock.get("name"):
        try:
            service = _get_service()
            info = service.get_info(stock["yf_ticker"])
            models.update_stock(
                stock["id"],
                name=info.get("shortName") or info.get("longName"),
                sector=info.get("sector"),
                industry=info.get("industry"),
            )
        except Exception:
            pass

    entry = models.add_to_watchlist(stock["id"], data.get("notes"), user_id=g.user_id)
    return jsonify({
        "id": entry["id"],
        "stockId": stock["id"],
        "ticker": ticker,
        "exchange": exchange,
        "message": "Added to watchlist",
    }), 201


@api_v1.route("/watchlist/<int:watchlist_id>", methods=["DELETE"])
@require_auth
def remove_from_watchlist(watchlist_id):
    """Remove from watchlist."""
    if models.remove_from_watchlist(watchlist_id, user_id=g.user_id):
        return jsonify({"message": "Removed from watchlist"})
    return jsonify({"error": "Watchlist entry not found"}), 404


# ---------------------------------------------------------------------------
# Settings (admin only)
# ---------------------------------------------------------------------------

@api_v1.route("/settings", methods=["GET"])
@require_admin
def get_settings():
    return jsonify(models.get_all_settings())


@api_v1.route("/settings", methods=["PUT"])
@require_admin
def update_settings():
    data = request.get_json(silent=True) or {}
    for key, value in data.items():
        models.set_setting(key, str(value))
    return jsonify(models.get_all_settings())
