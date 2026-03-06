"""Orchestrates all data fetching and caching for stock data."""

import math
import re
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


def _match_columns_to_filings(columns: list[str], filings: list[dict], freq: str) -> list:
    """Map each column label (e.g. 'FY 2025', 'Q1 2026') to its source SEC filing.

    Returns a list the same length as *columns* with either a filing dict or None.
    """
    if not filings:
        return [None] * len(columns)

    # Build lookup: (formType) -> list of filings sorted by date desc
    annual_filings = [f for f in filings if f.get("formType") in ("10-K", "20-F")]
    quarterly_filings = [f for f in filings if f.get("formType") in ("10-Q", "6-K")]

    result = []
    for col in columns:
        filing = None
        # Parse column label
        fy_match = re.match(r"FY\s*(\d{4})", col)
        q_match = re.match(r"Q([1-4])\s*(\d{4})", col)

        if freq == "annual" and fy_match:
            year = int(fy_match.group(1))
            # 10-K is filed after fiscal year end; look for filing date
            # within ~6 months after the fiscal year (covers all fiscal calendars)
            for f in annual_filings:
                try:
                    fd = datetime.strptime(f["filingDate"], "%Y-%m-%d")
                    # Filing date should be in the same year or up to 6 months after
                    if fd.year == year or (fd.year == year + 1 and fd.month <= 6):
                        filing = f
                        break
                except (ValueError, KeyError):
                    continue
        elif q_match:
            q_num = int(q_match.group(1))
            year = int(q_match.group(2))
            # 10-Q filed within ~3 months after quarter end
            for f in quarterly_filings:
                try:
                    fd = datetime.strptime(f["filingDate"], "%Y-%m-%d")
                    # Map filing date to approximate quarter
                    f_q = (fd.month - 1) // 3 + 1
                    f_year = fd.year
                    # Check if this filing covers the target quarter
                    # Q filing lags by ~1-2 months, so Q1 report files in Q2
                    if f_year == year and f_q == q_num:
                        filing = f
                        break
                    if f_year == year and f_q == q_num + 1:
                        filing = f
                        break
                    # Q4 of year X files in Q1 of year X+1
                    if q_num == 4 and f_year == year + 1 and f_q == 1:
                        filing = f
                        break
                except (ValueError, KeyError):
                    continue

        if filing:
            result.append({
                "formType": filing["formType"],
                "filingDate": filing["filingDate"],
                "url": filing.get("url", ""),
                "accessionNumber": filing.get("accessionNumber", ""),
            })
        else:
            result.append(None)

    return result


# ---------------------------------------------------------------------------
# Curated line-item definitions.  Each tuple is (label, row_type) where
# row_type is one of:
#   "item"    – regular line item (e.g. R&D, Interest Expense)
#   "total"   – subtotal / total (e.g. Gross Profit, Net Income)
#   "metric"  – derived metric (e.g. EPS, EBITDA)
#
# Only these rows are shown, in this order.  Duplicates are eliminated and
# the statements reconcile:
#   Income:  Revenue – COGS = Gross Profit – OpEx = Operating Income
#            +/- Non-operating = Pretax Income – Taxes = Net Income
#   Balance: Assets = Liabilities + Equity
#   Cash:    Operating + Investing + Financing = Change in Cash
# ---------------------------------------------------------------------------

INCOME_ITEMS = [
    ("Total Revenue",                      "total"),
    ("Cost Of Revenue",                    "item"),
    ("Gross Profit",                       "total"),
    ("Research And Development",           "item"),
    ("Selling General And Administration", "item"),
    ("Operating Expense",                  "total"),
    ("Operating Income",                   "total"),
    ("Interest Income",                    "item"),
    ("Interest Expense",                   "item"),
    ("Other Non Operating Income Expenses","item"),
    ("Pretax Income",                      "total"),
    ("Tax Provision",                      "item"),
    ("Net Income",                         "total"),
    ("Basic EPS",                          "metric"),
    ("Diluted EPS",                        "metric"),
    ("Basic Average Shares",              "metric"),
    ("Diluted Average Shares",            "metric"),
    ("EBITDA",                             "metric"),
    ("EBIT",                               "metric"),
    # SBC-adjusted metrics are computed at runtime and inserted here:
    # "EBITDA Less SBC", "EBIT Less SBC", "Net Income Less SBC"
]

BALANCE_SHEET_ITEMS = [
    # --- Assets ---
    ("Current Assets",                                  "total"),
    ("Cash And Cash Equivalents",                       "item"),
    ("Other Short Term Investments",                    "item"),
    ("Accounts Receivable",                             "item"),
    ("Other Receivables",                               "item"),
    ("Inventory",                                       "item"),
    ("Other Current Assets",                            "item"),
    ("Total Non Current Assets",                        "total"),
    ("Net PPE",                                         "item"),
    ("Investments And Advances",                        "item"),
    ("Non Current Deferred Taxes Assets",               "item"),
    ("Other Non Current Assets",                        "item"),
    ("Total Assets",                                    "total"),
    # --- Liabilities ---
    ("Current Liabilities",                             "total"),
    ("Accounts Payable",                                "item"),
    ("Current Debt",                                    "item"),
    ("Current Deferred Revenue",                        "item"),
    ("Other Current Liabilities",                       "item"),
    ("Total Non Current Liabilities Net Minority Interest", "total"),
    ("Long Term Debt",                                  "item"),
    ("Long Term Capital Lease Obligation",              "item"),
    ("Other Non Current Liabilities",                   "item"),
    ("Total Liabilities Net Minority Interest",         "total"),
    # --- Equity ---
    ("Common Stock",                                    "item"),
    ("Retained Earnings",                               "item"),
    ("Gains Losses Not Affecting Retained Earnings",    "item"),
    ("Stockholders Equity",                             "total"),
    # --- Supplemental ---
    ("Total Debt",                                      "metric"),
    ("Net Debt",                                        "metric"),
    ("Working Capital",                                 "metric"),
    ("Ordinary Shares Number",                          "metric"),
]

CASH_FLOW_ITEMS = [
    # --- Operating ---
    ("Net Income From Continuing Operations",   "item"),
    ("Depreciation And Amortization",           "item"),
    ("Stock Based Compensation",                "item"),
    ("Deferred Income Tax",                     "item"),
    ("Other Non Cash Items",                    "item"),
    ("Change In Working Capital",               "item"),
    ("Change In Receivables",                   "item"),
    ("Change In Inventory",                     "item"),
    ("Change In Account Payable",               "item"),
    ("Change In Other Working Capital",         "item"),
    ("Operating Cash Flow",                     "total"),
    # --- Investing ---
    ("Capital Expenditure",                     "item"),
    ("Purchase Of Business",                    "item"),
    ("Purchase Of Investment",                  "item"),
    ("Sale Of Investment",                      "item"),
    ("Net Other Investing Changes",             "item"),
    ("Investing Cash Flow",                     "total"),
    # --- Financing ---
    ("Long Term Debt Issuance",                 "item"),
    ("Long Term Debt Payments",                 "item"),
    ("Common Stock Issuance",                   "item"),
    ("Common Stock Payments",                   "item"),
    ("Common Stock Dividend Paid",              "item"),
    ("Net Other Financing Charges",             "item"),
    ("Financing Cash Flow",                     "total"),
    # --- Summary ---
    ("Beginning Cash Position",                 "metric"),
    ("End Cash Position",                       "metric"),
    ("Free Cash Flow",                          "metric"),
]

STMT_ITEMS_MAP = {
    "income": INCOME_ITEMS,
    "balance_sheet": BALANCE_SHEET_ITEMS,
    "cash_flow": CASH_FLOW_ITEMS,
}


def _df_to_table(df, stmt_type=None, sbc_values=None) -> dict:
    """Convert a pandas DataFrame (financials-style) to JSON-friendly table.

    When *stmt_type* is provided the output is filtered to a curated set of
    line items and returned in the canonical accounting order so that the
    statement reconciles correctly.  Each row includes a ``type`` field
    ("item", "total", or "metric") for frontend styling.

    *sbc_values* is an optional list of SBC amounts per column (from the cash
    flow statement) used to compute SBC-adjusted metrics on the income
    statement.
    """
    if df is None or df.empty:
        return {"columns": [], "rows": []}
    columns = [str(c.date()) if hasattr(c, 'date') else str(c) for c in df.columns]
    n_cols = len(columns)

    # Build lookup of all available rows keyed by label
    all_rows = {}
    for label, row in df.iterrows():
        all_rows[str(label)] = [_safe(v) for v in row.tolist()]

    whitelist = STMT_ITEMS_MAP.get(stmt_type)
    if whitelist:
        # Only include items present in the data, in whitelist order
        rows = []
        type_map = {name: rtype for name, rtype in whitelist}
        for name, rtype in whitelist:
            if name in all_rows:
                rows.append({"label": name, "values": all_rows[name], "type": rtype})

        # For income statements, append SBC-adjusted metrics
        if stmt_type == "income" and sbc_values and len(sbc_values) == n_cols:
            for base_label, adj_label in [
                ("EBITDA",      "EBITDA Less SBC"),
                ("EBIT",        "EBIT Less SBC"),
                ("Net Income",  "Net Income Less SBC"),
            ]:
                if base_label in all_rows:
                    base = all_rows[base_label]
                    adj = []
                    for b, s in zip(base, sbc_values):
                        if b is not None and s is not None:
                            adj.append(b - s)
                        else:
                            adj.append(None)
                    rows.append({"label": adj_label, "values": adj, "type": "metric"})
    else:
        # No whitelist — return everything in original order
        rows = [{"label": label, "values": vals, "type": "item"}
                for label, vals in all_rows.items()]

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

        # --- Try SEC EDGAR XBRL first for fundamental metrics ---
        sec_metrics = None
        if self.edgar:
            try:
                # Get current price for hybrid valuation ratios
                t = yf.Ticker(ticker)
                current_price = t.fast_info.last_price
                sec_metrics = self.edgar.get_xbrl_metrics(ticker, current_price)
            except Exception:
                sec_metrics = None

        # Yahoo-only metrics (never from SEC)
        yahoo_only = {
            "forwardPE": _safe(info.get("forwardPE")),
            "forwardEps": _safe(info.get("forwardEps")),
            "dividendYield": _safe(info.get("dividendYield")),
            "beta": _safe(info.get("beta")),
            "floatShares": _safe(info.get("floatShares")),
            "heldPercentInsiders": _safe(info.get("heldPercentInsiders")),
            "heldPercentInstitutions": _safe(info.get("heldPercentInstitutions")),
            "shortRatio": _safe(info.get("shortRatio")),
            "shortPercentOfFloat": _safe(info.get("shortPercentOfFloat")),
            "earningsQuarterlyGrowth": _safe(info.get("earningsQuarterlyGrowth")),
            "quickRatio": _safe(info.get("quickRatio")),
            "fiftyTwoWeekChange": _safe(info.get("52WeekChange")),
        }

        # Yahoo fallback values for all SEC-sourced metrics
        yahoo_fallback = {
            "trailingPE": _safe(info.get("trailingPE")),
            "priceToBook": _safe(info.get("priceToBook")),
            "priceToSales": _safe(info.get("priceToSalesTrailing12Months")),
            "evToRevenue": _safe(info.get("enterpriseToRevenue")),
            "evToEbitda": _safe(info.get("enterpriseToEbitda")),
            "marketCap": _safe(info.get("marketCap")),
            "enterpriseValue": _safe(info.get("enterpriseValue")),
            "trailingEps": _safe(info.get("trailingEps")),
            "bookValue": _safe(info.get("bookValue")),
            "returnOnEquity": _safe(info.get("returnOnEquity")),
            "returnOnAssets": _safe(info.get("returnOnAssets")),
            "grossMargins": _safe(info.get("grossMargins")),
            "operatingMargins": _safe(info.get("operatingMargins")),
            "profitMargins": _safe(info.get("profitMargins")),
            "debtToEquity": _safe(info.get("debtToEquity")),
            "currentRatio": _safe(info.get("currentRatio")),
            "totalRevenue": _safe(info.get("totalRevenue")),
            "totalDebt": _safe(info.get("totalDebt")),
            "totalCash": _safe(info.get("totalCash")),
            "sharesOutstanding": _safe(info.get("sharesOutstanding")),
            "freeCashflow": _safe(info.get("freeCashflow")),
            "operatingCashflow": _safe(info.get("operatingCashflow")),
            "revenueGrowth": _safe(info.get("revenueGrowth")),
            "earningsGrowth": _safe(info.get("earningsGrowth")),
            "payoutRatio": _safe(info.get("payoutRatio")),
        }

        # Merge: SEC first, Yahoo fallback for any None values
        result = dict(yahoo_only)
        if sec_metrics:
            for key, sec_val in sec_metrics.items():
                if key in yahoo_only:
                    continue  # Already set from Yahoo-only
                result[key] = sec_val if sec_val is not None else yahoo_fallback.get(key)
        else:
            # No SEC data — use Yahoo for everything
            result.update(yahoo_fallback)

        return result

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

    def get_financials(self, ticker: str, stmt_type: str = "income", freq: str = "annual", periods: int = 5) -> dict:
        filename = f"{'financials' if stmt_type == 'income' else stmt_type}_{freq}_{periods}.json"
        cached = read_cache(ticker, filename, WEEK)
        if cached:
            return cached

        # --- Try SEC EDGAR XBRL first ---
        sec_df = None
        if self.edgar:
            try:
                sec_df = self.edgar.get_xbrl_statement(
                    ticker,
                    stmt_type=stmt_type,
                    annual=(freq == "annual"),
                    periods=periods,
                )
            except Exception:
                sec_df = None

        if sec_df is not None and not sec_df.empty:
            # For income statements, pull SBC and D&A from SEC cash flow
            sbc_values = None
            if stmt_type == "income":
                try:
                    cf_df = self.edgar.get_xbrl_statement(
                        ticker,
                        stmt_type="cash_flow",
                        annual=(freq == "annual"),
                        periods=periods,
                    )
                    if cf_df is not None:
                        # Align cash flow columns to income statement columns
                        common_cols = [c for c in sec_df.columns if c in cf_df.columns]

                        if "Stock Based Compensation" in cf_df.index and common_cols:
                            sbc_values = [_safe(cf_df.at["Stock Based Compensation", c]) for c in common_cols]
                            # Pad if income statement has more columns
                            while len(sbc_values) < len(sec_df.columns):
                                sbc_values.append(None)

                        # Compute EBITDA = Operating Income + D&A
                        if ("Depreciation And Amortization" in cf_df.index
                                and "Operating Income" in sec_df.index
                                and "EBITDA" not in sec_df.index
                                and common_cols):
                            ebitda_vals = []
                            for col in sec_df.columns:
                                if col in cf_df.columns:
                                    oi = _safe(sec_df.at["Operating Income", col])
                                    da = _safe(cf_df.at["Depreciation And Amortization", col])
                                    if oi is not None and da is not None:
                                        ebitda_vals.append(oi + da)
                                    else:
                                        ebitda_vals.append(None)
                                else:
                                    ebitda_vals.append(None)
                            sec_df.loc["EBITDA"] = ebitda_vals
                except Exception:
                    sbc_values = None

            data = _df_to_table(sec_df, stmt_type, sbc_values)
            data["source"] = "sec"
            # Map columns to source SEC filings (fetch 10-K/10-Q specifically)
            try:
                forms = ["10-K", "20-F"] if freq == "annual" else ["10-Q", "6-K"]
                raw = self.edgar.list_filings(
                    ticker, forms=forms,
                    start_date=(datetime.now() - timedelta(days=15 * 365)).strftime("%Y-%m-%d"),
                    max_results=20,
                )
                stmt_filings = [self._filing_to_dict(f) for f in raw]
                data["columnFilings"] = _match_columns_to_filings(
                    data.get("columns", []), stmt_filings, freq
                )
            except Exception:
                data["columnFilings"] = None
            write_cache(ticker, filename, data)
            return data

        # --- Fall back to Yahoo Finance ---
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

        # For income statements, pull SBC from the matching cash flow to
        # compute SBC-adjusted metrics.
        sbc_values = None
        if stmt_type == "income" and df is not None and not df.empty:
            cf_attr = "cash_flow" if freq == "annual" else "quarterly_cash_flow"
            cf_df = getattr(t, cf_attr, None)
            if cf_df is not None and "Stock Based Compensation" in cf_df.index:
                sbc_row = cf_df.loc["Stock Based Compensation"]
                sbc_values = [_safe(v) for v in sbc_row.reindex(df.columns).tolist()]

        data = _df_to_table(df, stmt_type, sbc_values)
        data["source"] = "yahoo"
        data["columnFilings"] = None
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

    @staticmethod
    def _filing_to_dict(f) -> dict:
        """Convert a FilingInfo to a JSON-serialisable dict with correct SEC URL."""
        homepage_parts = (f.homepage_url or "").split("/")
        cik = homepage_parts[6] if len(homepage_parts) > 6 else ""
        acc_no_hyphens = f.accession_number.replace("-", "")
        primary = f.primary_document or ""
        if cik and acc_no_hyphens and primary:
            url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_hyphens}/{primary}"
        elif f.homepage_url:
            url = f.homepage_url
        else:
            url = ""
        return {
            "formType": f.form_type,
            "filingDate": f.filing_date,
            "accessionNumber": f.accession_number,
            "description": f.description,
            "url": url,
        }

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
            items = [self._filing_to_dict(f) for f in filings]
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
