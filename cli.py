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


def main():
    parser = argparse.ArgumentParser(
        description="Download SEC EDGAR filings for stock screening"
    )
    parser.add_argument(
        "--email", required=True,
        help="Your email for SEC EDGAR User-Agent (required by SEC)"
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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    screener = EdgarScreener(args.email)

    if args.command == "lookup":
        cmd_lookup(screener, args)
    elif args.command == "list":
        cmd_list(screener, args)
    elif args.command == "download":
        cmd_download(screener, args)


if __name__ == "__main__":
    main()
