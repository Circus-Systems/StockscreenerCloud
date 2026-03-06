"""High-level wrapper around edgartools for stock screening use cases."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
from edgar import Company, set_identity

from screener.storage import FilingStorage
from screener.xbrl_mapping import normalize_xbrl_dataframe, compute_xbrl_metrics

SUPPORTED_FORMS = ["10-K", "10-Q", "8-K", "DEF 14A", "4", "S-1", "S-3"]


@dataclass
class CompanyInfo:
    ticker: str
    name: str
    cik: int
    sic: str
    industry: str
    category: str


@dataclass
class FilingInfo:
    form_type: str
    filing_date: str
    accession_number: str
    description: str
    homepage_url: str = ""
    primary_document: str = ""


class EdgarScreener:
    """Connects to SEC EDGAR to look up companies, list filings, and download documents."""

    def __init__(self, email: str):
        set_identity(email)

    def lookup_company(self, ticker: str) -> CompanyInfo:
        company = Company(ticker)
        return CompanyInfo(
            ticker=ticker.upper(),
            name=company.name,
            cik=company.cik,
            sic=company.sic or "",
            industry=company.industry or "",
            category=company.filer_category or "",
        )

    def list_filings(
        self,
        ticker: str,
        forms: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_results: int = 20,
    ) -> list[FilingInfo]:
        company = Company(ticker)

        date_range = None
        if start_date and end_date:
            date_range = f"{start_date}:{end_date}"
        elif start_date:
            date_range = f"{start_date}:"
        elif end_date:
            date_range = f":{end_date}"

        form_filter = forms if forms else SUPPORTED_FORMS
        filings = company.get_filings(form=form_filter, filing_date=date_range)

        results = []
        for filing in filings[:max_results]:
            results.append(FilingInfo(
                form_type=filing.form,
                filing_date=str(filing.filing_date),
                accession_number=filing.accession_number,
                description=getattr(filing, 'primary_doc_description', filing.form),
                homepage_url=getattr(filing, 'homepage_url', ''),
                primary_document=getattr(filing, 'primary_document', ''),
            ))
        return results

    def download_filings(
        self,
        ticker: str,
        forms: Optional[list[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_results: int = 20,
        output_dir: str = "filings",
    ) -> list[Path]:
        storage = FilingStorage(Path(output_dir))
        company = Company(ticker)

        date_range = None
        if start_date and end_date:
            date_range = f"{start_date}:{end_date}"
        elif start_date:
            date_range = f"{start_date}:"
        elif end_date:
            date_range = f":{end_date}"

        form_filter = forms if forms else SUPPORTED_FORMS
        filings = company.get_filings(form=form_filter, filing_date=date_range)

        downloaded = []
        for filing in filings[:max_results]:
            dest = storage.filing_path(ticker, filing.form, str(filing.filing_date), filing.accession_number)
            if dest.exists():
                print(f"  Skipping (exists): {dest.name}")
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                html_content = filing.html()
                if html_content:
                    dest.write_text(html_content, encoding="utf-8")
                    downloaded.append(dest)
                    print(f"  Downloaded: {dest.name}")
                else:
                    text_content = filing.text()
                    if text_content:
                        txt_dest = dest.with_suffix(".txt")
                        txt_dest.write_text(text_content, encoding="utf-8")
                        downloaded.append(txt_dest)
                        print(f"  Downloaded: {txt_dest.name}")
                    else:
                        print(f"  No content available for {filing.accession_number}")
            except Exception as e:
                print(f"  Error downloading {filing.accession_number}: {e}")

        return downloaded

    def get_financials(self, ticker: str, statement: str = None) -> str:
        company = Company(ticker)
        facts = company.get_facts()

        sections = []
        statements = {
            "income": facts.income_statement,
            "balance-sheet": facts.balance_sheet,
            "cash-flow": facts.cashflow_statement,
        }

        if statement:
            if statement not in statements:
                raise ValueError(f"Unknown statement: {statement}. Choose from: {', '.join(statements)}")
            result = statements[statement]()
            sections.append(str(result))
        else:
            for name, func in statements.items():
                try:
                    result = func()
                    sections.append(str(result))
                except Exception as e:
                    sections.append(f"[{name}] Error: {e}")

        return "\n\n".join(sections)

    def get_xbrl_statement(
        self,
        ticker: str,
        stmt_type: str = "income",
        annual: bool = True,
        periods: int = 5,
    ) -> Optional[pd.DataFrame]:
        """Fetch an XBRL financial statement and normalize to yfinance format.

        Returns a pandas DataFrame with display labels as index and period
        columns, or None if data is unavailable.
        """
        company = Company(ticker)
        facts = company.get_facts()

        stmt_funcs = {
            "income": facts.income_statement,
            "balance_sheet": facts.balance_sheet,
            "cash_flow": facts.cashflow_statement,
        }
        func = stmt_funcs.get(stmt_type)
        if not func:
            return None

        stmt = func(periods=periods, annual=annual)
        raw_df = stmt.to_dataframe()
        return normalize_xbrl_dataframe(raw_df, stmt_type)

    def get_xbrl_metrics(self, ticker: str, current_price: float = None) -> dict:
        """Compute fundamental metrics from SEC XBRL data.

        Returns a dict with the same keys as StockDataService.get_metrics().
        Keys not derivable from SEC data are None.
        """
        company = Company(ticker)
        facts = company.get_facts()
        return compute_xbrl_metrics(facts, current_price)
