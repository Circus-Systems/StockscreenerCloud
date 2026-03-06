"""XBRL concept-to-display-label mappings and DataFrame normalization.

Transforms edgartools MultiPeriodStatement DataFrames into yfinance-compatible
format so the existing _df_to_table() whitelist pipeline works unchanged.
"""

import math
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Concept → display label mappings.
#
# Each display label (matching the whitelist in data_service.py) maps to a
# list of XBRL concepts to try, in priority order.  The first concept found
# in the DataFrame is used.  This handles taxonomy variations across filers.
# ---------------------------------------------------------------------------

INCOME_CONCEPT_MAP = {
    "Total Revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "RevenueNet",
    ],
    "Cost Of Revenue": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
        "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
    ],
    "Gross Profit": [
        "GrossProfit",
    ],
    "Research And Development": [
        "ResearchAndDevelopmentExpense",
        "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    ],
    "Selling General And Administration": [
        "SellingGeneralAndAdministrativeExpense",
    ],
    "Operating Expense": [
        "OperatingExpenses",
        "CostsAndExpenses",
    ],
    "Operating Income": [
        "OperatingIncomeLoss",
    ],
    "Interest Income": [
        "InterestIncomeExpenseNet",
        "InvestmentIncomeInterest",
        "InterestIncome",
        "InterestIncomeOperating",
    ],
    "Interest Expense": [
        "InterestExpense",
        "InterestExpenseDebt",
        "InterestPaid",
    ],
    "Other Non Operating Income Expenses": [
        "NonoperatingIncomeExpense",
        "OtherNonoperatingIncomeExpense",
        "OtherIncome",
    ],
    "Pretax Income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesDomestic",
    ],
    "Tax Provision": [
        "IncomeTaxExpenseBenefit",
    ],
    "Net Income": [
        "NetIncomeLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "ProfitLoss",
    ],
    "Basic EPS": [
        "EarningsPerShareBasic",
    ],
    "Diluted EPS": [
        "EarningsPerShareDiluted",
    ],
    "Basic Average Shares": [
        "WeightedAverageNumberOfSharesOutstandingBasic",
        "CommonStockSharesOutstanding",
    ],
    "Diluted Average Shares": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ],
}

BALANCE_SHEET_CONCEPT_MAP = {
    "Current Assets": [
        "AssetsCurrent",
    ],
    "Cash And Cash Equivalents": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsAndShortTermInvestments",
        "Cash",
    ],
    "Other Short Term Investments": [
        "ShortTermInvestments",
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    ],
    "Accounts Receivable": [
        "AccountsReceivableNetCurrent",
        "AccountsReceivableNet",
        "ReceivablesNetCurrent",
    ],
    "Other Receivables": [
        "NontradeReceivablesCurrent",
        "OtherReceivables",
    ],
    "Inventory": [
        "InventoryNet",
        "InventoryFinishedGoods",
    ],
    "Other Current Assets": [
        "OtherAssetsCurrent",
        "PrepaidExpenseAndOtherAssetsCurrent",
    ],
    "Total Non Current Assets": [
        "AssetsNoncurrent",
        "NoncurrentAssets",
    ],
    "Net PPE": [
        "PropertyPlantAndEquipmentNet",
    ],
    "Investments And Advances": [
        "LongTermInvestments",
        "MarketableSecuritiesNoncurrent",
        "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent",
        "InvestmentsAndAdvances",
    ],
    "Non Current Deferred Taxes Assets": [
        "DeferredIncomeTaxAssetsNet",
        "DeferredTaxAssetsNetNoncurrent",
    ],
    "Other Non Current Assets": [
        "OtherAssetsNoncurrent",
    ],
    "Total Assets": [
        "Assets",
    ],
    "Current Liabilities": [
        "LiabilitiesCurrent",
    ],
    "Accounts Payable": [
        "AccountsPayableCurrent",
        "AccountsPayableAndAccruedLiabilitiesCurrent",
    ],
    "Current Debt": [
        "LongTermDebtCurrent",
        "ShortTermBorrowings",
        "CommercialPaper",
        "DebtCurrent",
    ],
    "Current Deferred Revenue": [
        "ContractWithCustomerLiabilityCurrent",
        "DeferredRevenueCurrent",
    ],
    "Other Current Liabilities": [
        "OtherLiabilitiesCurrent",
        "AccruedLiabilitiesCurrent",
    ],
    "Total Non Current Liabilities Net Minority Interest": [
        "LiabilitiesNoncurrent",
        "NoncurrentLiabilities",
    ],
    "Long Term Debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ],
    "Long Term Capital Lease Obligation": [
        "OperatingLeaseLiabilityNoncurrent",
        "CapitalLeaseObligationsNoncurrent",
        "FinanceLeaseLiabilityNoncurrent",
    ],
    "Other Non Current Liabilities": [
        "OtherLiabilitiesNoncurrent",
    ],
    "Total Liabilities Net Minority Interest": [
        "Liabilities",
    ],
    "Common Stock": [
        "CommonStocksIncludingAdditionalPaidInCapital",
        "CommonStockValue",
        "AdditionalPaidInCapital",
    ],
    "Retained Earnings": [
        "RetainedEarningsAccumulatedDeficit",
    ],
    "Gains Losses Not Affecting Retained Earnings": [
        "AccumulatedOtherComprehensiveIncomeLossNetOfTax",
    ],
    "Stockholders Equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "Ordinary Shares Number": [
        "CommonStockSharesOutstanding",
        "CommonStockSharesIssued",
    ],
}

CASH_FLOW_CONCEPT_MAP = {
    "Net Income From Continuing Operations": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "Depreciation And Amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
    "Stock Based Compensation": [
        "ShareBasedCompensation",
        "StockBasedCompensation",
        "AllocatedShareBasedCompensationExpense",
    ],
    "Deferred Income Tax": [
        "DeferredIncomeTaxExpenseBenefit",
        "DeferredIncomeTaxesAndTaxCredits",
    ],
    "Other Non Cash Items": [
        "OtherNoncashIncomeExpense",
        "OtherOperatingActivitiesCashFlowStatement",
    ],
    "Change In Working Capital": [
        "IncreaseDecreaseInOperatingCapital",
        "IncreaseDecreaseInOperatingLiabilities",
    ],
    "Change In Receivables": [
        "IncreaseDecreaseInAccountsReceivable",
    ],
    "Change In Inventory": [
        "IncreaseDecreaseInInventories",
    ],
    "Change In Account Payable": [
        "IncreaseDecreaseInAccountsPayable",
    ],
    "Change In Other Working Capital": [
        "IncreaseDecreaseInOtherOperatingCapitalNet",
        "IncreaseDecreaseInOtherOperatingLiabilities",
    ],
    "Operating Cash Flow": [
        "NetCashProvidedByUsedInOperatingActivities",
    ],
    "Capital Expenditure": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "CapitalExpendituresIncurredButNotYetPaid",
    ],
    "Purchase Of Business": [
        "PaymentsToAcquireBusinessesNetOfCashAcquired",
        "PaymentsToAcquireBusinessesGross",
    ],
    "Purchase Of Investment": [
        "PaymentsToAcquireInvestments",
        "PaymentsToAcquireAvailableForSaleSecuritiesDebt",
        "PaymentsToAcquireMarketableSecurities",
    ],
    "Sale Of Investment": [
        "ProceedsFromMaturitiesPrepaymentsAndCallsOfAvailableForSaleSecurities",
        "ProceedsFromSaleOfAvailableForSaleSecuritiesDebt",
        "ProceedsFromSaleAndMaturityOfMarketableSecurities",
        "ProceedsFromSaleOfInvestments",
    ],
    "Net Other Investing Changes": [
        "PaymentsForProceedsFromOtherInvestingActivities",
        "OtherInvestingActivities",
    ],
    "Investing Cash Flow": [
        "NetCashProvidedByUsedInInvestingActivities",
    ],
    "Long Term Debt Issuance": [
        "ProceedsFromIssuanceOfLongTermDebt",
        "ProceedsFromDebtNoncurrent",
    ],
    "Long Term Debt Payments": [
        "RepaymentsOfLongTermDebt",
        "RepaymentsOfDebtMaturitiesRepayments",
    ],
    "Common Stock Issuance": [
        "ProceedsFromIssuanceOfCommonStock",
        "ProceedsFromStockPlans",
    ],
    "Common Stock Payments": [
        "PaymentsForRepurchaseOfCommonStock",
        "PaymentsForRepurchaseOfEquity",
    ],
    "Common Stock Dividend Paid": [
        "PaymentsOfDividendsCommonStock",
        "PaymentsOfDividends",
    ],
    "Net Other Financing Charges": [
        "ProceedsFromPaymentsForOtherFinancingActivities",
        "OtherFinancingActivities",
    ],
    "Financing Cash Flow": [
        "NetCashProvidedByUsedInFinancingActivities",
    ],
    "Beginning Cash Position": [
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "CashAndCashEquivalentsAtCarryingValue",
    ],
    "End Cash Position": [
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
    ],
}

STMT_CONCEPT_MAPS = {
    "income": INCOME_CONCEPT_MAP,
    "balance_sheet": BALANCE_SHEET_CONCEPT_MAP,
    "cash_flow": CASH_FLOW_CONCEPT_MAP,
}


def _safe(val):
    """Convert NaN/inf to None."""
    if val is None:
        return None
    try:
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
    except (TypeError, ValueError):
        return None
    return val


def normalize_xbrl_dataframe(
    xbrl_df: pd.DataFrame,
    stmt_type: str,
) -> Optional[pd.DataFrame]:
    """Transform an edgartools MultiPeriodStatement DataFrame into yfinance format.

    Input:  DataFrame with XBRL concept names as index, columns include
            'label', 'depth', 'is_abstract', 'is_total', 'section',
            'confidence', plus period columns like 'FY 2025', 'Q1 2026'.

    Output: DataFrame with display labels as index, date/period strings as
            columns, values as floats.  Suitable for _df_to_table().
    """
    concept_map = STMT_CONCEPT_MAPS.get(stmt_type)
    if concept_map is None or xbrl_df is None or xbrl_df.empty:
        return None

    # Identify period columns (not metadata)
    meta_cols = {"label", "depth", "is_abstract", "is_total", "section", "confidence"}
    period_cols = [c for c in xbrl_df.columns if c not in meta_cols]
    if not period_cols:
        return None

    # Build available concept set
    available = set(xbrl_df.index)

    # Map display labels to values
    rows = {}
    for display_label, concept_candidates in concept_map.items():
        for concept in concept_candidates:
            if concept in available:
                vals = [_safe(xbrl_df.at[concept, col]) for col in period_cols]
                # Skip if all None
                if any(v is not None for v in vals):
                    rows[display_label] = vals
                break

    if not rows:
        return None

    # Build output DataFrame mimicking yfinance format
    result = pd.DataFrame(rows, index=period_cols).T
    result.columns = period_cols

    # Compute derived rows
    _compute_derived_rows(result, stmt_type, period_cols)

    return result


def _compute_derived_rows(df: pd.DataFrame, stmt_type: str, period_cols: list):
    """Add computed rows that XBRL doesn't provide directly."""

    if stmt_type == "income":
        # EBITDA = Operating Income + D&A (we need to get D&A from somewhere)
        # For now, EBITDA can be computed if we have Pretax Income + Interest Expense + D&A
        # Or simpler: if Operating Income exists but EBITDA doesn't, skip it.
        # EBIT = Operating Income (they're the same thing)
        if "Operating Income" in df.index and "EBIT" not in df.index:
            df.loc["EBIT"] = df.loc["Operating Income"]

        # Total Non Current Assets = Total Assets - Current Assets (if missing)
        pass

    elif stmt_type == "balance_sheet":
        # Total Debt = Current Debt + Long Term Debt
        if "Total Debt" not in df.index:
            current_debt = df.loc["Current Debt"] if "Current Debt" in df.index else None
            lt_debt = df.loc["Long Term Debt"] if "Long Term Debt" in df.index else None
            if current_debt is not None or lt_debt is not None:
                vals = []
                for col in period_cols:
                    cd = _safe(current_debt[col]) if current_debt is not None else None
                    ld = _safe(lt_debt[col]) if lt_debt is not None else None
                    if cd is not None or ld is not None:
                        vals.append((cd or 0) + (ld or 0))
                    else:
                        vals.append(None)
                df.loc["Total Debt"] = vals

        # Net Debt = Total Debt - Cash
        if "Net Debt" not in df.index and "Total Debt" in df.index:
            cash_label = "Cash And Cash Equivalents"
            if cash_label in df.index:
                vals = []
                for col in period_cols:
                    debt = _safe(df.at["Total Debt", col])
                    cash = _safe(df.at[cash_label, col])
                    if debt is not None and cash is not None:
                        vals.append(debt - cash)
                    else:
                        vals.append(None)
                df.loc["Net Debt"] = vals

        # Working Capital = Current Assets - Current Liabilities
        if "Working Capital" not in df.index:
            if "Current Assets" in df.index and "Current Liabilities" in df.index:
                vals = []
                for col in period_cols:
                    ca = _safe(df.at["Current Assets", col])
                    cl = _safe(df.at["Current Liabilities", col])
                    if ca is not None and cl is not None:
                        vals.append(ca - cl)
                    else:
                        vals.append(None)
                df.loc["Working Capital"] = vals

        # Total Non Current Assets = Total Assets - Current Assets
        if "Total Non Current Assets" not in df.index:
            if "Total Assets" in df.index and "Current Assets" in df.index:
                vals = []
                for col in period_cols:
                    ta = _safe(df.at["Total Assets", col])
                    ca = _safe(df.at["Current Assets", col])
                    if ta is not None and ca is not None:
                        vals.append(ta - ca)
                    else:
                        vals.append(None)
                df.loc["Total Non Current Assets"] = vals

        # Total Non Current Liabilities = Total Liabilities - Current Liabilities
        if "Total Non Current Liabilities Net Minority Interest" not in df.index:
            if ("Total Liabilities Net Minority Interest" in df.index
                    and "Current Liabilities" in df.index):
                vals = []
                for col in period_cols:
                    tl = _safe(df.at["Total Liabilities Net Minority Interest", col])
                    cl = _safe(df.at["Current Liabilities", col])
                    if tl is not None and cl is not None:
                        vals.append(tl - cl)
                    else:
                        vals.append(None)
                df.loc["Total Non Current Liabilities Net Minority Interest"] = vals

    elif stmt_type == "cash_flow":
        # Free Cash Flow = Operating Cash Flow + Capital Expenditure
        # (CapEx is negative in cash flow, so FCF = OCF + CapEx)
        if "Free Cash Flow" not in df.index:
            if "Operating Cash Flow" in df.index and "Capital Expenditure" in df.index:
                vals = []
                for col in period_cols:
                    ocf = _safe(df.at["Operating Cash Flow", col])
                    capex = _safe(df.at["Capital Expenditure", col])
                    if ocf is not None and capex is not None:
                        # CapEx from XBRL is typically negative (payments)
                        vals.append(ocf + capex)
                    else:
                        vals.append(None)
                df.loc["Free Cash Flow"] = vals


def compute_xbrl_metrics(facts, current_price: float = None) -> dict:
    """Compute fundamental metrics from SEC XBRL EntityFacts.

    Returns a dict with the same keys as StockDataService.get_metrics(),
    but only for metrics derivable from SEC data.  Keys not available
    from SEC are returned as None so the caller can fill them from Yahoo.
    """
    # Pull latest values via get_concept()
    def gc(name):
        try:
            v = facts.get_concept(name)
            return _safe(v)
        except Exception:
            return None

    revenue = gc("revenue")
    net_income = gc("net_income")
    gross_profit = gc("gross_profit")
    operating_income = gc("operating_income")
    total_assets = gc("total_assets")
    total_liabilities = gc("total_liabilities")
    cost_of_revenue = gc("cost_of_revenue")
    operating_expenses = gc("operating_expenses")
    interest_expense = gc("interest_expense")
    income_tax = gc("income_tax_expense")
    operating_cf = gc("operating_cash_flow")
    capex = gc("capex")
    cash = gc("cash_and_equivalents")

    # Try to get values that get_concept might miss
    eps_basic = gc("earnings_per_share_basic")
    eps_diluted = gc("earnings_per_share_diluted")
    shares = gc("shares_outstanding")
    total_debt = gc("total_debt")
    equity = gc("shareholders_equity")
    current_assets = gc("current_assets")
    current_liabilities = gc("current_liabilities")
    depreciation = gc("depreciation_amortization")
    sbc = gc("stock_based_compensation")
    free_cash_flow = gc("free_cash_flow")

    # If individual getters return None, try extracting from statements
    try:
        inc_stmt = facts.income_statement()
        inc_df = inc_stmt.to_dataframe()
        meta_cols = {"label", "depth", "is_abstract", "is_total", "section", "confidence"}
        period_cols = [c for c in inc_df.columns if c not in meta_cols]
        latest_period = period_cols[0] if period_cols else None

        if latest_period:
            def _get_inc(concepts):
                for c in concepts:
                    if c in inc_df.index:
                        v = _safe(inc_df.at[c, latest_period])
                        if v is not None:
                            return v
                return None

            if revenue is None:
                revenue = _get_inc(INCOME_CONCEPT_MAP["Total Revenue"])
            if net_income is None:
                net_income = _get_inc(INCOME_CONCEPT_MAP["Net Income"])
            if gross_profit is None:
                gross_profit = _get_inc(INCOME_CONCEPT_MAP["Gross Profit"])
            if operating_income is None:
                operating_income = _get_inc(INCOME_CONCEPT_MAP["Operating Income"])
            if eps_basic is None:
                eps_basic = _get_inc(INCOME_CONCEPT_MAP["Basic EPS"])
            if eps_diluted is None:
                eps_diluted = _get_inc(INCOME_CONCEPT_MAP["Diluted EPS"])
            if income_tax is None:
                income_tax = _get_inc(INCOME_CONCEPT_MAP["Tax Provision"])
            if interest_expense is None:
                interest_expense = _get_inc(INCOME_CONCEPT_MAP["Interest Expense"])
    except Exception:
        pass

    try:
        bs_stmt = facts.balance_sheet()
        bs_df = bs_stmt.to_dataframe()
        meta_cols = {"label", "depth", "is_abstract", "is_total", "section", "confidence"}
        bs_period_cols = [c for c in bs_df.columns if c not in meta_cols]
        bs_latest = bs_period_cols[0] if bs_period_cols else None

        if bs_latest:
            def _get_bs(concepts):
                for c in concepts:
                    if c in bs_df.index:
                        v = _safe(bs_df.at[c, bs_latest])
                        if v is not None:
                            return v
                return None

            if total_assets is None:
                total_assets = _get_bs(BALANCE_SHEET_CONCEPT_MAP["Total Assets"])
            if total_liabilities is None:
                total_liabilities = _get_bs(BALANCE_SHEET_CONCEPT_MAP["Total Liabilities Net Minority Interest"])
            if equity is None:
                equity = _get_bs(BALANCE_SHEET_CONCEPT_MAP["Stockholders Equity"])
            if cash is None:
                cash = _get_bs(BALANCE_SHEET_CONCEPT_MAP["Cash And Cash Equivalents"])
            if current_assets is None:
                current_assets = _get_bs(BALANCE_SHEET_CONCEPT_MAP["Current Assets"])
            if current_liabilities is None:
                current_liabilities = _get_bs(BALANCE_SHEET_CONCEPT_MAP["Current Liabilities"])
            if shares is None:
                shares = _get_bs(BALANCE_SHEET_CONCEPT_MAP["Ordinary Shares Number"])
            if total_debt is None:
                cd = _get_bs(BALANCE_SHEET_CONCEPT_MAP["Current Debt"])
                ld = _get_bs(BALANCE_SHEET_CONCEPT_MAP["Long Term Debt"])
                if cd is not None or ld is not None:
                    total_debt = (cd or 0) + (ld or 0)
    except Exception:
        pass

    try:
        cf_stmt = facts.cashflow_statement()
        cf_df = cf_stmt.to_dataframe()
        meta_cols = {"label", "depth", "is_abstract", "is_total", "section", "confidence"}
        cf_period_cols = [c for c in cf_df.columns if c not in meta_cols]
        cf_latest = cf_period_cols[0] if cf_period_cols else None

        if cf_latest:
            def _get_cf(concepts):
                for c in concepts:
                    if c in cf_df.index:
                        v = _safe(cf_df.at[c, cf_latest])
                        if v is not None:
                            return v
                return None

            if operating_cf is None:
                operating_cf = _get_cf(CASH_FLOW_CONCEPT_MAP["Operating Cash Flow"])
            if capex is None:
                capex = _get_cf(CASH_FLOW_CONCEPT_MAP["Capital Expenditure"])
            if depreciation is None:
                depreciation = _get_cf(CASH_FLOW_CONCEPT_MAP["Depreciation And Amortization"])
            if sbc is None:
                sbc = _get_cf(CASH_FLOW_CONCEPT_MAP["Stock Based Compensation"])
    except Exception:
        pass

    # --- Compute derived metrics ---
    gross_margins = None
    if gross_profit is not None and revenue and revenue != 0:
        gross_margins = gross_profit / revenue

    operating_margins = None
    if operating_income is not None and revenue and revenue != 0:
        operating_margins = operating_income / revenue

    profit_margins = None
    if net_income is not None and revenue and revenue != 0:
        profit_margins = net_income / revenue

    roe = None
    if net_income is not None and equity and equity != 0:
        roe = net_income / equity

    roa = None
    if net_income is not None and total_assets and total_assets != 0:
        roa = net_income / total_assets

    debt_to_equity = None
    if total_debt is not None and equity and equity != 0:
        debt_to_equity = (total_debt / equity) * 100  # yfinance reports D/E × 100

    current_ratio = None
    if current_assets is not None and current_liabilities and current_liabilities != 0:
        current_ratio = current_assets / current_liabilities

    book_value = None
    if equity is not None and shares and shares != 0:
        book_value = equity / shares

    # EPS: prefer diluted, fallback to basic, fallback to computed
    trailing_eps = eps_diluted or eps_basic
    if trailing_eps is None and net_income is not None and shares and shares != 0:
        trailing_eps = net_income / shares

    # FCF
    if free_cash_flow is None and operating_cf is not None and capex is not None:
        free_cash_flow = operating_cf + capex  # capex is negative from XBRL

    # EBITDA (for EV/EBITDA)
    ebitda = None
    if operating_income is not None and depreciation is not None:
        ebitda = operating_income + depreciation

    # Market cap & EV (hybrid: SEC shares + Yahoo price)
    market_cap = None
    enterprise_value = None
    trailing_pe = None
    price_to_book = None
    price_to_sales = None
    ev_to_ebitda = None
    ev_to_revenue = None

    if current_price:
        if shares:
            market_cap = current_price * shares
        if market_cap is not None:
            ev_debt = total_debt or 0
            ev_cash = cash or 0
            enterprise_value = market_cap + ev_debt - ev_cash
        if trailing_eps and trailing_eps != 0:
            trailing_pe = current_price / trailing_eps
        if book_value and book_value != 0:
            price_to_book = current_price / book_value
        if market_cap and revenue and revenue != 0:
            price_to_sales = market_cap / revenue
        if enterprise_value and ebitda and ebitda != 0:
            ev_to_ebitda = enterprise_value / ebitda
        if enterprise_value and revenue and revenue != 0:
            ev_to_revenue = enterprise_value / revenue

    # --- Revenue / earnings growth (YoY from annual statement) ---
    revenue_growth = None
    earnings_growth = None
    try:
        inc_stmt = facts.income_statement(periods=2)
        inc_df2 = inc_stmt.to_dataframe()
        meta_cols2 = {"label", "depth", "is_abstract", "is_total", "section", "confidence"}
        pcols2 = [c for c in inc_df2.columns if c not in meta_cols2]
        if len(pcols2) >= 2:
            def _yoy(concepts):
                for c in concepts:
                    if c in inc_df2.index:
                        curr = _safe(inc_df2.at[c, pcols2[0]])
                        prev = _safe(inc_df2.at[c, pcols2[1]])
                        if curr is not None and prev is not None and prev != 0:
                            return (curr - prev) / abs(prev)
                return None
            revenue_growth = _yoy(INCOME_CONCEPT_MAP["Total Revenue"])
            earnings_growth = _yoy(INCOME_CONCEPT_MAP["Net Income"])
    except Exception:
        pass

    # Payout ratio
    payout_ratio = None
    try:
        cf_stmt = facts.cashflow_statement()
        cf_df = cf_stmt.to_dataframe()
        meta_cols3 = {"label", "depth", "is_abstract", "is_total", "section", "confidence"}
        cf_pcols = [c for c in cf_df.columns if c not in meta_cols3]
        if cf_pcols and net_income and net_income != 0:
            div_concepts = CASH_FLOW_CONCEPT_MAP["Common Stock Dividend Paid"]
            for c in div_concepts:
                if c in cf_df.index:
                    div_paid = _safe(cf_df.at[c, cf_pcols[0]])
                    if div_paid is not None:
                        payout_ratio = abs(div_paid) / abs(net_income)
                    break
    except Exception:
        pass

    return {
        # Valuation (hybrid or SEC-only)
        "trailingPE": _safe(trailing_pe),
        "priceToBook": _safe(price_to_book),
        "priceToSales": _safe(price_to_sales),
        "evToRevenue": _safe(ev_to_revenue),
        "evToEbitda": _safe(ev_to_ebitda),
        "marketCap": _safe(market_cap),
        "enterpriseValue": _safe(enterprise_value),
        "trailingEps": _safe(trailing_eps),
        "bookValue": _safe(book_value),
        # Profitability
        "returnOnEquity": _safe(roe),
        "returnOnAssets": _safe(roa),
        "grossMargins": _safe(gross_margins),
        "operatingMargins": _safe(operating_margins),
        "profitMargins": _safe(profit_margins),
        # Balance sheet
        "debtToEquity": _safe(debt_to_equity),
        "currentRatio": _safe(current_ratio),
        "totalRevenue": _safe(revenue),
        "totalDebt": _safe(total_debt),
        "totalCash": _safe(cash),
        "sharesOutstanding": _safe(shares),
        # Cash flow
        "freeCashflow": _safe(free_cash_flow),
        "operatingCashflow": _safe(operating_cf),
        # Growth
        "revenueGrowth": _safe(revenue_growth),
        "earningsGrowth": _safe(earnings_growth),
        # Dividends
        "payoutRatio": _safe(payout_ratio),
        # --- Not available from SEC (caller fills from Yahoo) ---
        "forwardPE": None,
        "forwardEps": None,
        "dividendYield": None,
        "beta": None,
        "floatShares": None,
        "heldPercentInsiders": None,
        "heldPercentInstitutions": None,
        "shortRatio": None,
        "shortPercentOfFloat": None,
        "earningsQuarterlyGrowth": None,
        "quickRatio": None,
        "fiftyTwoWeekChange": None,
    }
