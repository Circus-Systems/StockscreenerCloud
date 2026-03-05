"""Real-time stock quote data via Yahoo Finance (yfinance)."""

from dataclasses import dataclass

import yfinance as yf


@dataclass
class StockQuote:
    ticker: str
    name: str
    price: float
    open: float
    previous_close: float
    day_high: float
    day_low: float
    volume: int
    market_cap: int
    shares: int
    fifty_day_avg: float
    two_hundred_day_avg: float
    year_high: float
    year_low: float
    year_change: float
    currency: str

    @property
    def change(self) -> float:
        return self.price - self.previous_close

    @property
    def change_pct(self) -> float:
        if self.previous_close == 0:
            return 0.0
        return (self.change / self.previous_close) * 100


def get_quote(ticker: str) -> StockQuote:
    t = yf.Ticker(ticker)
    fi = t.fast_info
    info = t.info
    return StockQuote(
        ticker=ticker.upper(),
        name=info.get("shortName", ticker.upper()),
        price=fi.last_price,
        open=fi.open,
        previous_close=fi.previous_close,
        day_high=fi.day_high,
        day_low=fi.day_low,
        volume=fi.last_volume,
        market_cap=fi.market_cap,
        shares=fi.shares,
        fifty_day_avg=fi.fifty_day_average,
        two_hundred_day_avg=fi.two_hundred_day_average,
        year_high=fi.year_high,
        year_low=fi.year_low,
        year_change=fi.year_change,
        currency=fi.currency,
    )
