"""Orchestrates all data fetching and caching for stock data."""

import math
from datetime import datetime, timedelta

import yfinance as yf

from screener.cache import read_cache, write_cache
from screener.edgar_client import EdgarScreener, SUPPORTED_FORMS

PERIOD_INTERVAL_MAP = {
    "1d": "5m",
    "5d": "15m",
    "1mo": "1d",
    "3mo": "1d",
    "6mo": "1d",
    "1y": "1d",
    "2y": "1wk",
    "5y": "1wk",
    "10y": "1mo",
    "ytd": "1d",
    "max": "1wk",
}

HOUR = 3600
DAY = 86400
WEEK = 604800


def _safe(val):
    """Convert NaN/inf to None for JSON serialization."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val


def _df_to_table(df) -> dict:
    """Convert a pandas DataFrame (financials-style) to JSON-friendly table."""
    if df is None or df.empty:
        return {"columns": [], "rows": []}
    columns = [str(c.date()) if hasattr(c, 'date') else str(c) for c in df.columns]
    rows = []
    for label, row in df.iterrows():
        rows.append({
            "label": str(label),
            "values": [_safe(v) for v in row.tolist()],
        })
    return {"columns": columns, "rows": rows}


class StockDataService:
    def __init__(self, edgar_email: str = None):
        self.edgar = EdgarScreener(edgar_email) if edgar_email else None

    def get_quote(self, ticker: str) -> dict:
        t = yf.Ticker(ticker)
        fi = t.fast_info
        info = self.get_info(ticker)
        price = fi.last_price
        prev = fi.previous_close
        change = price - prev
        change_pct = (change / prev * 100) if prev else 0
        return {
            "ticker": ticker.upper(),
            "name": info.get("shortName", ticker.upper()),
            "price": round(price, 2),
            "change": round(change, 2),
            "changePct": round(change_pct, 2),
            "open": round(fi.open, 2),
            "prevClose": round(prev, 2),
            "dayHigh": round(fi.day_high, 2),
            "dayLow": round(fi.day_low, 2),
            "volume": fi.last_volume,
            "marketCap": fi.market_cap,
            "fiftyDayAvg": round(fi.fifty_day_average, 2),
            "twoHundredDayAvg": round(fi.two_hundred_day_average, 2),
            "yearHigh": round(fi.year_high, 2),
            "yearLow": round(fi.year_low, 2),
            "yearChange": round(fi.year_change * 100, 2),
            "currency": fi.currency,
        }

    def get_info(self, ticker: str) -> dict:
        cached = read_cache(ticker, "info.json", DAY)
        if cached:
            return cached
        t = yf.Ticker(ticker)
        data = dict(t.info)
        # Clean NaN values
        for k, v in data.items():
            data[k] = _safe(v)
        write_cache(ticker, "info.json", data)
        return data

    def get_profile(self, ticker: str) -> dict:
        info = self.get_info(ticker)
        profile = {
            "ticker": ticker.upper(),
            "name": info.get("shortName", ""),
            "longName": info.get("longName", ""),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "description": info.get("longBusinessSummary", ""),
            "website": info.get("website", ""),
            "employees": info.get("fullTimeEmployees"),
            "city": info.get("city", ""),
            "state": info.get("state", ""),
            "country": info.get("country", ""),
            "exchange": info.get("exchange", ""),
        }
        if self.edgar:
            try:
                ec = read_cache(ticker, "edgar_company.json", WEEK)
                if not ec:
                    company = self.edgar.lookup_company(ticker)
                    ec = {
                        "cik": company.cik,
                        "sic": company.sic,
                        "filingCategory": company.category,
                    }
                    write_cache(ticker, "edgar_company.json", ec)
                profile["cik"] = ec.get("cik")
                profile["sic"] = ec.get("sic")
            except Exception:
                pass
        return profile

    def get_metrics(self, ticker: str) -> dict:
        info = self.get_info(ticker)
        return {
            "trailingPE": _safe(info.get("trailingPE")),
            "forwardPE": _safe(info.get("forwardPE")),
            "priceToBook": _safe(info.get("priceToBook")),
            "priceToSales": _safe(info.get("priceToSalesTrailing12Months")),
            "evToRevenue": _safe(info.get("enterpriseToRevenue")),
            "evToEbitda": _safe(info.get("enterpriseToEbitda")),
            "dividendYield": _safe(info.get("dividendYield")),
            "beta": _safe(info.get("beta")),
            "marketCap": _safe(info.get("marketCap")),
            "enterpriseValue": _safe(info.get("enterpriseValue")),
            "trailingEps": _safe(info.get("trailingEps")),
            "forwardEps": _safe(info.get("forwardEps")),
            "bookValue": _safe(info.get("bookValue")),
            "returnOnEquity": _safe(info.get("returnOnEquity")),
            "returnOnAssets": _safe(info.get("returnOnAssets")),
            "debtToEquity": _safe(info.get("debtToEquity")),
            "currentRatio": _safe(info.get("currentRatio")),
            "quickRatio": _safe(info.get("quickRatio")),
            "grossMargins": _safe(info.get("grossMargins")),
            "operatingMargins": _safe(info.get("operatingMargins")),
            "profitMargins": _safe(info.get("profitMargins")),
            "revenueGrowth": _safe(info.get("revenueGrowth")),
            "earningsGrowth": _safe(info.get("earningsGrowth")),
            "earningsQuarterlyGrowth": _safe(info.get("earningsQuarterlyGrowth")),
            "freeCashflow": _safe(info.get("freeCashflow")),
            "operatingCashflow": _safe(info.get("operatingCashflow")),
            "totalRevenue": _safe(info.get("totalRevenue")),
            "totalDebt": _safe(info.get("totalDebt")),
            "totalCash": _safe(info.get("totalCash")),
            "sharesOutstanding": _safe(info.get("sharesOutstanding")),
            "floatShares": _safe(info.get("floatShares")),
            "heldPercentInsiders": _safe(info.get("heldPercentInsiders")),
            "heldPercentInstitutions": _safe(info.get("heldPercentInstitutions")),
            "shortRatio": _safe(info.get("shortRatio")),
            "shortPercentOfFloat": _safe(info.get("shortPercentOfFloat")),
            "payoutRatio": _safe(info.get("payoutRatio")),
            "fiftyTwoWeekChange": _safe(info.get("52WeekChange")),
        }

    def get_history(self, ticker: str, period: str = "1y") -> list[dict]:
        interval = PERIOD_INTERVAL_MAP.get(period, "1d")
        filename = f"history_{period}.json"
        max_age = HOUR if period in ("1d", "5d") else DAY

        cached = read_cache(ticker, filename, max_age)
        if cached:
            return cached.get("data", cached) if isinstance(cached, dict) else cached

        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval)
        records = []
        for idx, row in df.iterrows():
            if interval in ("1d", "1wk", "1mo"):
                time_val = idx.strftime("%Y-%m-%d")
            else:
                time_val = int(idx.timestamp())
            records.append({
                "time": time_val,
                "open": round(row["Open"], 2),
                "high": round(row["High"], 2),
                "low": round(row["Low"], 2),
                "close": round(row["Close"], 2),
                "volume": int(row["Volume"]),
            })
        write_cache(ticker, filename, records)
        return records

    def get_financials(self, ticker: str, stmt_type: str = "income", freq: str = "annual") -> dict:
        filename = f"{'financials' if stmt_type == 'income' else stmt_type}_{freq}.json"
        cached = read_cache(ticker, filename, WEEK)
        if cached:
            return cached

        t = yf.Ticker(ticker)
        attr_map = {
            ("income", "annual"): "financials",
            ("income", "quarterly"): "quarterly_financials",
            ("balance_sheet", "annual"): "balance_sheet",
            ("balance_sheet", "quarterly"): "quarterly_balance_sheet",
            ("cash_flow", "annual"): "cash_flow",
            ("cash_flow", "quarterly"): "quarterly_cash_flow",
        }
        attr = attr_map.get((stmt_type, freq))
        if not attr:
            return {"columns": [], "rows": []}

        df = getattr(t, attr, None)
        data = _df_to_table(df)
        write_cache(ticker, filename, data)
        return data

    def get_recommendations(self, ticker: str) -> dict:
        cached = read_cache(ticker, "recommendations.json", DAY)
        if cached:
            return cached

        t = yf.Ticker(ticker)
        data = {"current": {}, "history": []}
        try:
            recs = t.recommendations
            if recs is not None and not recs.empty:
                latest = recs.iloc[-1]
                data["current"] = {
                    "strongBuy": int(latest.get("strongBuy", 0)),
                    "buy": int(latest.get("buy", 0)),
                    "hold": int(latest.get("hold", 0)),
                    "sell": int(latest.get("sell", 0)),
                    "strongSell": int(latest.get("strongSell", 0)),
                }
                for _, row in recs.iterrows():
                    data["history"].append({
                        "period": str(row.name),
                        "strongBuy": int(row.get("strongBuy", 0)),
                        "buy": int(row.get("buy", 0)),
                        "hold": int(row.get("hold", 0)),
                        "sell": int(row.get("sell", 0)),
                        "strongSell": int(row.get("strongSell", 0)),
                    })
        except Exception:
            pass
        write_cache(ticker, "recommendations.json", data)
        return data

    def get_analyst_targets(self, ticker: str) -> dict:
        cached = read_cache(ticker, "analyst_targets.json", DAY)
        if cached:
            return cached

        t = yf.Ticker(ticker)
        data = {}
        try:
            targets = t.analyst_price_targets
            if targets is not None:
                data = {
                    "current": _safe(targets.get("current")),
                    "high": _safe(targets.get("high")),
                    "low": _safe(targets.get("low")),
                    "mean": _safe(targets.get("mean")),
                    "median": _safe(targets.get("median")),
                }
        except Exception:
            pass
        write_cache(ticker, "analyst_targets.json", data)
        return data

    def get_news(self, ticker: str) -> list[dict]:
        cached = read_cache(ticker, "news.json", HOUR)
        if cached:
            items = cached.get("data", cached) if isinstance(cached, dict) else cached
            return items

        t = yf.Ticker(ticker)
        items = []
        try:
            news = t.news
            if news:
                for n in news[:20]:
                    content = n.get("content", {})
                    items.append({
                        "title": content.get("title", n.get("title", "")),
                        "url": content.get("canonicalUrl", {}).get("url", n.get("link", "")),
                        "publishedAt": content.get("pubDate", ""),
                        "source": content.get("provider", {}).get("displayName", ""),
                    })
        except Exception:
            pass
        write_cache(ticker, "news.json", items)
        return items

    def get_upgrades(self, ticker: str) -> list[dict]:
        cached = read_cache(ticker, "upgrades.json", DAY)
        if cached:
            items = cached.get("data", cached) if isinstance(cached, dict) else cached
            return items

        t = yf.Ticker(ticker)
        items = []
        try:
            upgrades = t.upgrades_downgrades
            if upgrades is not None and not upgrades.empty:
                for idx, row in upgrades.head(20).iterrows():
                    items.append({
                        "date": str(idx.date()) if hasattr(idx, 'date') else str(idx),
                        "firm": row.get("Firm", ""),
                        "toGrade": row.get("ToGrade", ""),
                        "fromGrade": row.get("FromGrade", ""),
                        "action": row.get("Action", ""),
                    })
        except Exception:
            pass
        write_cache(ticker, "upgrades.json", items)
        return items

    def get_holders(self, ticker: str) -> dict:
        cached = read_cache(ticker, "holders.json", DAY)
        if cached:
            return cached

        t = yf.Ticker(ticker)
        data = {}
        try:
            holders = t.major_holders
            if holders is not None and not holders.empty:
                for _, row in holders.iterrows():
                    label = str(row.iloc[1]).strip() if len(row) > 1 else ""
                    value = row.iloc[0]
                    if "insider" in label.lower():
                        data["insidersPercent"] = _safe(value)
                    elif "institution" in label.lower() and "float" not in label.lower():
                        data["institutionsPercent"] = _safe(value)
                    elif "float" in label.lower():
                        data["institutionsFloatPercent"] = _safe(value)
                    elif "shares" in label.lower() or "count" in label.lower():
                        data["institutionsCount"] = _safe(value)
        except Exception:
            pass
        write_cache(ticker, "holders.json", data)
        return data

    def get_filings(self, ticker: str) -> list[dict]:
        cached = read_cache(ticker, "edgar_filings.json", WEEK)
        if cached:
            items = cached.get("data", cached) if isinstance(cached, dict) else cached
            return items

        if not self.edgar:
            return []

        five_years_ago = (datetime.now() - timedelta(days=5 * 365)).strftime("%Y-%m-%d")
        try:
            filings = self.edgar.list_filings(
                ticker,
                start_date=five_years_ago,
                max_results=100,
            )
            items = [
                {
                    "formType": f.form_type,
                    "filingDate": f.filing_date,
                    "accessionNumber": f.accession_number,
                    "description": f.description,
                }
                for f in filings
            ]
        except Exception:
            items = []
        write_cache(ticker, "edgar_filings.json", items)
        return items

    def fetch_all(self, ticker: str) -> dict:
        """Populate the full cache for a ticker. Returns summary of what was fetched."""
        results = {}
        fetchers = [
            ("info", lambda: self.get_info(ticker)),
            ("profile", lambda: self.get_profile(ticker)),
            ("metrics", lambda: self.get_metrics(ticker)),
            ("history", lambda: self.get_history(ticker, "1y")),
            ("financials", lambda: self.get_financials(ticker, "income", "annual")),
            ("balance_sheet", lambda: self.get_financials(ticker, "balance_sheet", "annual")),
            ("cash_flow", lambda: self.get_financials(ticker, "cash_flow", "annual")),
            ("recommendations", lambda: self.get_recommendations(ticker)),
            ("analyst_targets", lambda: self.get_analyst_targets(ticker)),
            ("news", lambda: self.get_news(ticker)),
            ("upgrades", lambda: self.get_upgrades(ticker)),
            ("holders", lambda: self.get_holders(ticker)),
            ("filings", lambda: self.get_filings(ticker)),
        ]
        for name, fn in fetchers:
            try:
                fn()
                results[name] = "ok"
            except Exception as e:
                results[name] = f"error: {e}"
        return results
