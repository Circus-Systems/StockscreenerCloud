"""Local directory structure and download management for SEC filings."""

import re
from pathlib import Path


class FilingStorage:
    """
    Manages local filing storage.

    Structure:
        filings/
        └── AAPL/
            ├── 10-K/
            │   └── 2024-10-31_0000320193-24-000123.html
            └── 10-Q/
                └── 2024-08-01_0000320193-24-000099.html
    """

    def __init__(self, base_dir: Path = Path("filings")):
        self.base_dir = base_dir

    def filing_path(self, ticker: str, form_type: str, filing_date: str, accession_number: str) -> Path:
        safe_form = re.sub(r'[/\\]', '_', form_type)
        filename = f"{filing_date}_{accession_number}.html"
        return self.base_dir / ticker.upper() / safe_form / filename

    def exists(self, ticker: str, form_type: str, filing_date: str, accession_number: str) -> bool:
        path = self.filing_path(ticker, form_type, filing_date, accession_number)
        return path.exists() or path.with_suffix(".txt").exists()

    def list_downloaded(self, ticker: str, form_type: str = None) -> list[Path]:
        ticker_dir = self.base_dir / ticker.upper()
        if not ticker_dir.exists():
            return []
        if form_type:
            safe_form = re.sub(r'[/\\]', '_', form_type)
            form_dir = ticker_dir / safe_form
            if not form_dir.exists():
                return []
            return sorted(form_dir.iterdir())
        return sorted(ticker_dir.rglob("*.*"))
