"""JSON file cache with staleness checks for per-stock data."""

import json
import time
from pathlib import Path

BASE_DIR = Path("data")


def cache_path(ticker: str, filename: str) -> Path:
    return BASE_DIR / ticker.upper() / filename


def read_cache(ticker: str, filename: str, max_age_seconds: int) -> dict | list | None:
    path = cache_path(ticker, filename)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            fetched_at = data.get("_fetched_at", 0)
            if time.time() - fetched_at > max_age_seconds:
                return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def write_cache(ticker: str, filename: str, data: dict | list) -> Path:
    path = cache_path(ticker, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, dict):
        data["_fetched_at"] = time.time()
    elif isinstance(data, list):
        data = {"_fetched_at": time.time(), "data": data}
    path.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")
    return path


def is_cached(ticker: str, filename: str, max_age_seconds: int) -> bool:
    return read_cache(ticker, filename, max_age_seconds) is not None
