#!/usr/bin/env python3
"""
SEC EDGAR Filing Downloader CLI

Usage:
    python cli.py --email you@example.com lookup AAPL
    python cli.py --email you@example.com list AAPL --forms 10-K 10-Q --after 2023-01-01
    python cli.py --email you@example.com download AAPL MSFT --forms 10-K --after 2023-01-01
"""

import argparse
import sys

from screener.edgar_client import EdgarScreener, SUPPORTED_FORMS
from screener.yahoo import get_quote


def cmd_lookup(screener: EdgarScreener, args):
    info = screener.lookup_company(args.ticker)
    print(f"Ticker:   {info.ticker}")
    print(f"Name:     {info.name}")
    print(f"CIK:      {info.cik}")
    print(f"SIC:      {info.sic}")
    print(f"Industry: {info.industry}")
    print(f"Category: {info.category}")


def cmd_list(screener: EdgarScreener, args):
    forms = args.forms if args.forms else None
    for ticker in args.tickers:
        print(f"\n{'='*60}")
        print(f" {ticker.upper()} — Filings")
        print(f"{'='*60}")
        filings = screener.list_filings(
            ticker,
            forms=forms,
            start_date=args.after,
            end_date=args.before,
            max_results=args.max,
        )
        if not filings:
            print("  No filings found.")
            continue
        for f in filings:
            print(f"  {f.filing_date}  {f.form_type:<10}  {f.accession_number}")


def cmd_download(screener: EdgarScreener, args):
    forms = args.forms if args.forms else None
    for ticker in args.tickers:
        print(f"\nDownloading filings for {ticker.upper()}...")
        downloaded = screener.download_filings(
            ticker,
            forms=forms,
            start_date=args.after,
            end_date=args.before,
            max_results=args.max,
            output_dir=args.output,
        )
        print(f"  Total downloaded: {len(downloaded)} filing(s)")


STATEMENT_CHOICES = ["income", "balance-sheet", "cash-flow"]


def cmd_financials(screener: EdgarScreener, args):
    print(screener.get_financials(args.ticker, statement=args.statement))


def _fmt_large(n: float) -> str:
    abs_n = abs(n)
    if abs_n >= 1e12:
        return f"${n/1e12:.2f}T"
    if abs_n >= 1e9:
        return f"${n/1e9:.2f}B"
    if abs_n >= 1e6:
        return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"


def cmd_quote(args):
    for ticker in args.tickers:
        q = get_quote(ticker)
        sign = "+" if q.change >= 0 else ""
        print(f"\n{'='*50}")
        print(f" {q.name} ({q.ticker})")
        print(f"{'='*50}")
        print(f"  Price:        ${q.price:.2f}  {sign}{q.change:.2f} ({sign}{q.change_pct:.2f}%)")
        print(f"  Open:         ${q.open:.2f}")
        print(f"  Day Range:    ${q.day_low:.2f} - ${q.day_high:.2f}")
        print(f"  52-Wk Range:  ${q.year_low:.2f} - ${q.year_high:.2f}")
        print(f"  Volume:       {q.volume:,}")
        print(f"  Market Cap:   {_fmt_large(q.market_cap)}")
        print(f"  50-Day Avg:   ${q.fifty_day_avg:.2f}")
        print(f"  200-Day Avg:  ${q.two_hundred_day_avg:.2f}")
        print(f"  YTD Change:   {q.year_change*100:+.2f}%")


def main():
    parser = argparse.ArgumentParser(
        description="Download SEC EDGAR filings for stock screening"
    )
    parser.add_argument(
        "--email",
        help="Your email for SEC EDGAR User-Agent (required for SEC commands)"
    )

    subparsers = parser.add_subparsers(dest="command")

    # lookup
    lookup = subparsers.add_parser("lookup", help="Look up company info by ticker")
    lookup.add_argument("ticker", help="Ticker symbol (e.g. AAPL)")

    # list
    ls = subparsers.add_parser("list", help="List filings without downloading")
    ls.add_argument("tickers", nargs="+", help="Ticker symbol(s)")
    ls.add_argument("--forms", nargs="+", choices=SUPPORTED_FORMS, help="Filing types")
    ls.add_argument("--after", help="Only filings after this date (YYYY-MM-DD)")
    ls.add_argument("--before", help="Only filings before this date (YYYY-MM-DD)")
    ls.add_argument("--max", type=int, default=20, help="Max filings per ticker (default: 20)")

    # download
    dl = subparsers.add_parser("download", help="Download filings to disk")
    dl.add_argument("tickers", nargs="+", help="Ticker symbol(s)")
    dl.add_argument("--forms", nargs="+", choices=SUPPORTED_FORMS, help="Filing types")
    dl.add_argument("--after", help="Only filings after this date (YYYY-MM-DD)")
    dl.add_argument("--before", help="Only filings before this date (YYYY-MM-DD)")
    dl.add_argument("--max", type=int, default=20, help="Max filings per ticker (default: 20)")
    dl.add_argument("--output", default="filings", help="Output directory (default: filings/)")

    # quote (uses Yahoo Finance, no --email needed)
    qt = subparsers.add_parser("quote", help="Get real-time stock quote (via Yahoo Finance)")
    qt.add_argument("tickers", nargs="+", help="Ticker symbol(s)")

    # financials
    fin = subparsers.add_parser("financials", help="Show structured financial statements (XBRL)")
    fin.add_argument("ticker", help="Ticker symbol (e.g. AAPL)")
    fin.add_argument("--statement", choices=STATEMENT_CHOICES,
                     help="Show only one statement (default: all three)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # quote uses Yahoo Finance, no SEC identity needed
    if args.command == "quote":
        cmd_quote(args)
        return

    if not args.email:
        parser.error("--email is required for SEC EDGAR commands")

    screener = EdgarScreener(args.email)

    if args.command == "lookup":
        cmd_lookup(screener, args)
    elif args.command == "list":
        cmd_list(screener, args)
    elif args.command == "download":
        cmd_download(screener, args)
    elif args.command == "financials":
        cmd_financials(screener, args)


if __name__ == "__main__":
    main()
