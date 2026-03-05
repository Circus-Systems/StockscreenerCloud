/* Metric calculation pop-ups — step-by-step derivations with data sources */

// Raw metrics data is stored here by app.js after fetching
let _metricsData = null;

function setMetricsData(data) { _metricsData = data; }

// ---------------------------------------------------------------------------
// Calculation definitions
// Each key maps to { formula, steps(m) }
//   formula: human-readable formula string
//   steps(m): returns array of { label, value, formatted, source }
//   The last step is always the result.
// ---------------------------------------------------------------------------

const CALC_DEFS = {
    'P/E (TTM)': {
        formula: 'Price ÷ EPS (TTM)',
        steps: m => [
            { label: 'Stock Price', value: m._price, formatted: fmtCurrency(m._price), source: 'Yahoo Finance — real-time quote' },
            { label: 'Earnings Per Share (TTM)', value: m.trailingEps, formatted: fmtCurrency(m.trailingEps), source: 'Yahoo Finance — trailing 12-month EPS' },
            'divider',
            { label: 'P/E (TTM)', value: m.trailingPE, formatted: fmtRatio(m.trailingPE), source: 'Price ÷ EPS (TTM)', result: true },
        ],
    },
    'P/E (Fwd)': {
        formula: 'Price ÷ Forward EPS',
        steps: m => [
            { label: 'Stock Price', value: m._price, formatted: fmtCurrency(m._price), source: 'Yahoo Finance — real-time quote' },
            { label: 'Forward EPS (est.)', value: m.forwardEps, formatted: fmtCurrency(m.forwardEps), source: 'Yahoo Finance — analyst consensus forward EPS' },
            'divider',
            { label: 'P/E (Forward)', value: m.forwardPE, formatted: fmtRatio(m.forwardPE), source: 'Price ÷ Forward EPS', result: true },
        ],
    },
    'EPS (TTM)': {
        formula: 'Net Income (TTM) ÷ Diluted Shares Outstanding',
        steps: m => {
            const netIncome = m.trailingEps && m.sharesOutstanding ? m.trailingEps * m.sharesOutstanding : null;
            return [
                { label: 'Net Income (TTM)', value: netIncome, formatted: fmtLarge(netIncome), source: 'Yahoo Finance — trailing 12-month net income' },
                { label: 'Diluted Shares Outstanding', value: m.sharesOutstanding, formatted: fmtLarge(m.sharesOutstanding), source: 'Yahoo Finance — shares outstanding' },
                'divider',
                { label: 'EPS (TTM)', value: m.trailingEps, formatted: fmtCurrency(m.trailingEps), source: 'Net Income ÷ Shares', result: true },
            ];
        },
    },
    'EPS (Fwd)': {
        formula: 'Analyst Consensus Forward EPS Estimate',
        steps: m => [
            { label: 'Forward EPS (est.)', value: m.forwardEps, formatted: fmtCurrency(m.forwardEps), source: 'Yahoo Finance — analyst consensus estimate for next fiscal year', result: true },
        ],
    },
    'Div Yield': {
        formula: 'Annual Dividend Per Share ÷ Price × 100',
        steps: m => {
            const divPerShare = m.dividendYield != null && m._price ? (m.dividendYield / 100) * m._price : null;
            return [
                { label: 'Annual Dividend / Share', value: divPerShare, formatted: fmtCurrency(divPerShare), source: 'Yahoo Finance — trailing annual dividend' },
                { label: 'Stock Price', value: m._price, formatted: fmtCurrency(m._price), source: 'Yahoo Finance — real-time quote' },
                'divider',
                { label: 'Dividend Yield', value: m.dividendYield, formatted: m.dividendYield != null ? fmtPercent(m.dividendYield, false) : '—', source: 'Dividend / Price × 100', result: true },
            ];
        },
    },
    'Beta': {
        formula: 'Covariance(Stock, Market) ÷ Variance(Market)',
        steps: m => [
            { label: '5Y Monthly Beta vs S&P 500', value: m.beta, formatted: fmtRatio(m.beta), source: 'Yahoo Finance — 5-year monthly regression vs S&P 500', result: true },
        ],
    },
    'Payout Ratio': {
        formula: 'Dividends Paid ÷ Net Income × 100',
        steps: m => {
            const netIncome = m.trailingEps && m.sharesOutstanding ? m.trailingEps * m.sharesOutstanding : null;
            const divPaid = m.payoutRatio && netIncome ? m.payoutRatio * netIncome : null;
            return [
                { label: 'Total Dividends Paid', value: divPaid, formatted: fmtLarge(divPaid), source: 'Yahoo Finance — trailing 12-month dividends' },
                { label: 'Net Income (TTM)', value: netIncome, formatted: fmtLarge(netIncome), source: 'Yahoo Finance — trailing 12-month net income' },
                'divider',
                { label: 'Payout Ratio', value: m.payoutRatio, formatted: m.payoutRatio != null ? fmtPercent(m.payoutRatio) : '—', source: 'Dividends ÷ Net Income', result: true },
            ];
        },
    },
    'Market Cap': {
        formula: 'Share Price × Shares Outstanding',
        steps: m => [
            { label: 'Stock Price', value: m._price, formatted: fmtCurrency(m._price), source: 'Yahoo Finance — real-time quote' },
            { label: 'Shares Outstanding', value: m.sharesOutstanding, formatted: fmtLarge(m.sharesOutstanding), source: 'Yahoo Finance — total shares outstanding' },
            'divider',
            { label: 'Market Capitalisation', value: m.marketCap, formatted: fmtLarge(m.marketCap), source: 'Price × Shares', result: true },
        ],
    },
    'EV': {
        formula: 'Market Cap + Total Debt − Cash & Equivalents',
        steps: m => [
            { label: 'Market Capitalisation', value: m.marketCap, formatted: fmtLarge(m.marketCap), source: 'Yahoo Finance — price × shares outstanding' },
            { label: 'Total Debt', value: m.totalDebt, formatted: fmtLarge(m.totalDebt), source: 'Yahoo Finance — short-term + long-term debt' },
            { label: 'Cash & Equivalents', value: m.totalCash, formatted: fmtLarge(m.totalCash), source: 'Yahoo Finance — cash, equivalents & short-term investments' },
            'divider',
            { label: 'Enterprise Value', value: m.enterpriseValue, formatted: fmtLarge(m.enterpriseValue), source: 'Market Cap + Debt − Cash', result: true },
        ],
    },
    'EV/EBITDA': {
        formula: 'Enterprise Value ÷ EBITDA (TTM)',
        steps: m => {
            const ebitda = m.enterpriseValue && m.evToEbitda ? m.enterpriseValue / m.evToEbitda : null;
            return [
                { label: 'Enterprise Value', value: m.enterpriseValue, formatted: fmtLarge(m.enterpriseValue), source: 'Yahoo Finance — Market Cap + Debt − Cash' },
                { label: 'EBITDA (TTM)', value: ebitda, formatted: fmtLarge(ebitda), source: 'Yahoo Finance — trailing 12-month EBITDA' },
                'divider',
                { label: 'EV / EBITDA', value: m.evToEbitda, formatted: fmtRatio(m.evToEbitda), source: 'EV ÷ EBITDA', result: true },
            ];
        },
    },
    'EV/Revenue': {
        formula: 'Enterprise Value ÷ Revenue (TTM)',
        steps: m => [
            { label: 'Enterprise Value', value: m.enterpriseValue, formatted: fmtLarge(m.enterpriseValue), source: 'Yahoo Finance — Market Cap + Debt − Cash' },
            { label: 'Total Revenue (TTM)', value: m.totalRevenue, formatted: fmtLarge(m.totalRevenue), source: 'Yahoo Finance — trailing 12-month revenue' },
            'divider',
            { label: 'EV / Revenue', value: m.evToRevenue, formatted: fmtRatio(m.evToRevenue), source: 'EV ÷ Revenue', result: true },
        ],
    },
    'P/B': {
        formula: 'Price ÷ Book Value Per Share',
        steps: m => [
            { label: 'Stock Price', value: m._price, formatted: fmtCurrency(m._price), source: 'Yahoo Finance — real-time quote' },
            { label: 'Book Value Per Share', value: m.bookValue, formatted: fmtCurrency(m.bookValue), source: 'Yahoo Finance — total equity ÷ shares outstanding' },
            'divider',
            { label: 'Price / Book', value: m.priceToBook, formatted: fmtRatio(m.priceToBook), source: 'Price ÷ BVPS', result: true },
        ],
    },
    'P/S': {
        formula: 'Market Cap ÷ Revenue (TTM)',
        steps: m => [
            { label: 'Market Capitalisation', value: m.marketCap, formatted: fmtLarge(m.marketCap), source: 'Yahoo Finance — price × shares outstanding' },
            { label: 'Total Revenue (TTM)', value: m.totalRevenue, formatted: fmtLarge(m.totalRevenue), source: 'Yahoo Finance — trailing 12-month revenue' },
            'divider',
            { label: 'Price / Sales', value: m.priceToSales, formatted: fmtRatio(m.priceToSales), source: 'Market Cap ÷ Revenue', result: true },
        ],
    },
    'Gross Margin': {
        formula: '(Revenue − COGS) ÷ Revenue × 100',
        steps: m => {
            const rev = m.totalRevenue;
            const cogs = rev && m.grossMargins ? rev * (1 - m.grossMargins) : null;
            const gp = rev && m.grossMargins ? rev * m.grossMargins : null;
            return [
                { label: 'Total Revenue (TTM)', value: rev, formatted: fmtLarge(rev), source: 'Yahoo Finance — trailing 12-month revenue' },
                { label: 'Cost of Revenue', value: cogs, formatted: fmtLarge(cogs), source: 'Yahoo Finance — trailing 12-month COGS' },
                { label: 'Gross Profit', value: gp, formatted: fmtLarge(gp), source: 'Revenue − COGS' },
                'divider',
                { label: 'Gross Margin', value: m.grossMargins, formatted: fmtPercent(m.grossMargins), source: 'Gross Profit ÷ Revenue × 100', result: true },
            ];
        },
    },
    'Op Margin': {
        formula: 'Operating Income ÷ Revenue × 100',
        steps: m => {
            const rev = m.totalRevenue;
            const opIncome = rev && m.operatingMargins ? rev * m.operatingMargins : null;
            return [
                { label: 'Operating Income (TTM)', value: opIncome, formatted: fmtLarge(opIncome), source: 'Yahoo Finance — trailing 12-month operating income' },
                { label: 'Total Revenue (TTM)', value: rev, formatted: fmtLarge(rev), source: 'Yahoo Finance — trailing 12-month revenue' },
                'divider',
                { label: 'Operating Margin', value: m.operatingMargins, formatted: fmtPercent(m.operatingMargins), source: 'Op Income ÷ Revenue × 100', result: true },
            ];
        },
    },
    'Net Margin': {
        formula: 'Net Income ÷ Revenue × 100',
        steps: m => {
            const rev = m.totalRevenue;
            const netIncome = rev && m.profitMargins ? rev * m.profitMargins : null;
            return [
                { label: 'Net Income (TTM)', value: netIncome, formatted: fmtLarge(netIncome), source: 'Yahoo Finance — trailing 12-month net income' },
                { label: 'Total Revenue (TTM)', value: rev, formatted: fmtLarge(rev), source: 'Yahoo Finance — trailing 12-month revenue' },
                'divider',
                { label: 'Net Margin', value: m.profitMargins, formatted: fmtPercent(m.profitMargins), source: 'Net Income ÷ Revenue × 100', result: true },
            ];
        },
    },
    'Rev Growth': {
        formula: '(Revenue Current − Revenue Prior) ÷ Revenue Prior × 100',
        steps: m => [
            { label: 'Revenue Growth (QoQ)', value: m.revenueGrowth, formatted: m.revenueGrowth != null ? fmtPercent(m.revenueGrowth) : '—', source: 'Yahoo Finance — most recent quarter vs same quarter prior year', result: true },
        ],
    },
    'Earn Growth': {
        formula: '(Earnings Current − Earnings Prior) ÷ Earnings Prior × 100',
        steps: m => [
            { label: 'Earnings Growth (QoQ)', value: m.earningsGrowth, formatted: m.earningsGrowth != null ? fmtPercent(m.earningsGrowth) : '—', source: 'Yahoo Finance — most recent quarter vs same quarter prior year', result: true },
        ],
    },
    'D/E': {
        formula: 'Total Debt ÷ Shareholders\' Equity',
        steps: m => {
            const equity = m.totalDebt && m.debtToEquity ? (m.totalDebt / m.debtToEquity) * 100 : null;
            return [
                { label: 'Total Debt', value: m.totalDebt, formatted: fmtLarge(m.totalDebt), source: 'Yahoo Finance — short-term + long-term debt' },
                { label: 'Shareholders\' Equity', value: equity, formatted: fmtLarge(equity), source: 'Yahoo Finance — total stockholders\' equity' },
                'divider',
                { label: 'Debt / Equity', value: m.debtToEquity, formatted: fmtRatio(m.debtToEquity), source: 'Total Debt ÷ Equity (×100)', result: true },
            ];
        },
    },
    'Current Ratio': {
        formula: 'Current Assets ÷ Current Liabilities',
        steps: m => [
            { label: 'Current Ratio', value: m.currentRatio, formatted: fmtRatio(m.currentRatio), source: 'Yahoo Finance — current assets ÷ current liabilities from latest balance sheet', result: true },
        ],
    },
    'ROE': {
        formula: 'Net Income (TTM) ÷ Shareholders\' Equity × 100',
        steps: m => {
            const equity = m.totalDebt && m.debtToEquity ? (m.totalDebt / m.debtToEquity) * 100 : null;
            const netIncome = equity && m.returnOnEquity ? m.returnOnEquity * equity : null;
            return [
                { label: 'Net Income (TTM)', value: netIncome, formatted: fmtLarge(netIncome), source: 'Yahoo Finance — trailing 12-month net income' },
                { label: 'Shareholders\' Equity', value: equity, formatted: fmtLarge(equity), source: 'Yahoo Finance — total stockholders\' equity' },
                'divider',
                { label: 'Return on Equity', value: m.returnOnEquity, formatted: m.returnOnEquity != null ? fmtPercent(m.returnOnEquity) : '—', source: 'Net Income ÷ Equity × 100', result: true },
            ];
        },
    },
    'ROA': {
        formula: 'Net Income (TTM) ÷ Total Assets × 100',
        steps: m => [
            { label: 'Return on Assets', value: m.returnOnAssets, formatted: m.returnOnAssets != null ? fmtPercent(m.returnOnAssets) : '—', source: 'Yahoo Finance — net income (TTM) ÷ total assets from latest balance sheet', result: true },
        ],
    },
    'FCF': {
        formula: 'Operating Cash Flow − Capital Expenditures',
        steps: m => {
            const capex = m.operatingCashflow && m.freeCashflow ? m.operatingCashflow - m.freeCashflow : null;
            return [
                { label: 'Operating Cash Flow', value: m.operatingCashflow, formatted: fmtLarge(m.operatingCashflow), source: 'Yahoo Finance — trailing 12-month operating cash flow' },
                { label: 'Capital Expenditures', value: capex, formatted: fmtLarge(capex ? -capex : null), source: 'Yahoo Finance — trailing 12-month capex' },
                'divider',
                { label: 'Free Cash Flow', value: m.freeCashflow, formatted: fmtLarge(m.freeCashflow), source: 'Operating CF − CapEx', result: true },
            ];
        },
    },
    'Op Cash Flow': {
        formula: 'Net Income + Non-Cash Charges + Changes in Working Capital',
        steps: m => [
            { label: 'Operating Cash Flow (TTM)', value: m.operatingCashflow, formatted: fmtLarge(m.operatingCashflow), source: 'Yahoo Finance — trailing 12-month operating cash flow (see Cash Flow statement for full breakdown)', result: true },
        ],
    },
};


// ---------------------------------------------------------------------------
// Modal display
// ---------------------------------------------------------------------------

function showCalcModal(metricLabel) {
    const def = CALC_DEFS[metricLabel];
    if (!def || !_metricsData) return;

    const modal = document.getElementById('calc-modal');
    const title = document.getElementById('calc-title');
    const body = document.getElementById('calc-body');

    title.textContent = metricLabel;

    const steps = def.steps(_metricsData);

    let html = `<div class="calc-formula">${def.formula}</div>`;
    html += '<div class="calc-steps">';

    for (const step of steps) {
        if (step === 'divider') {
            html += '<hr class="calc-divider">';
            continue;
        }
        const cls = step.result ? 'calc-result' : 'calc-step';
        html += `
            <div class="${cls}">
                <div>
                    <div class="calc-step-label">${step.label}</div>
                    <div class="calc-step-source">${step.source}</div>
                </div>
                <div class="calc-step-value">${step.formatted}</div>
            </div>`;
    }

    html += '</div>';
    body.innerHTML = html;
    modal.classList.remove('hidden');
}

function hideCalcModal() {
    document.getElementById('calc-modal').classList.add('hidden');
}

// Close on backdrop click or close button
document.addEventListener('click', e => {
    if (e.target.classList.contains('calc-backdrop') || e.target.classList.contains('calc-close')) {
        hideCalcModal();
    }
});

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') hideCalcModal();
});
