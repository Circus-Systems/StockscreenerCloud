/* Metric panels, analyst targets, and recommendation rendering */

function renderMetricList(containerId, items) {
    const el = document.getElementById(containerId);
    el.innerHTML = items.map(([label, value]) =>
        `<div class="metric-row">
            <span class="metric-label">${label}</span>
            <span class="metric-value">${value}</span>
        </div>`
    ).join('');
}

function renderMetrics(metrics) {
    renderMetricList('key-metrics', [
        ['P/E (TTM)', fmtRatio(metrics.trailingPE)],
        ['P/E (Fwd)', fmtRatio(metrics.forwardPE)],
        ['EPS (TTM)', fmtCurrency(metrics.trailingEps)],
        ['EPS (Fwd)', fmtCurrency(metrics.forwardEps)],
        ['Div Yield', metrics.dividendYield != null ? fmtPercent(metrics.dividendYield, false) : '—'],
        ['Beta', fmtRatio(metrics.beta)],
        ['Payout Ratio', metrics.payoutRatio != null ? fmtPercent(metrics.payoutRatio) : '—'],
    ]);

    renderMetricList('valuation-metrics', [
        ['Market Cap', fmtLarge(metrics.marketCap)],
        ['EV', fmtLarge(metrics.enterpriseValue)],
        ['EV/EBITDA', fmtRatio(metrics.evToEbitda)],
        ['EV/Revenue', fmtRatio(metrics.evToRevenue)],
        ['P/B', fmtRatio(metrics.priceToBook)],
        ['P/S', fmtRatio(metrics.priceToSales)],
    ]);

    renderMetricList('profitability-metrics', [
        ['Gross Margin', fmtPercent(metrics.grossMargins)],
        ['Op Margin', fmtPercent(metrics.operatingMargins)],
        ['Net Margin', fmtPercent(metrics.profitMargins)],
        ['Rev Growth', metrics.revenueGrowth != null ? fmtPercent(metrics.revenueGrowth) : '—'],
        ['Earn Growth', metrics.earningsGrowth != null ? fmtPercent(metrics.earningsGrowth) : '—'],
    ]);

    renderMetricList('balance-metrics', [
        ['D/E', fmtRatio(metrics.debtToEquity)],
        ['Current Ratio', fmtRatio(metrics.currentRatio)],
        ['ROE', metrics.returnOnEquity != null ? fmtPercent(metrics.returnOnEquity) : '—'],
        ['ROA', metrics.returnOnAssets != null ? fmtPercent(metrics.returnOnAssets) : '—'],
        ['FCF', fmtLarge(metrics.freeCashflow)],
        ['Op Cash Flow', fmtLarge(metrics.operatingCashflow)],
    ]);
}

function renderAnalystTargets(targets, currentPrice) {
    const el = document.getElementById('analyst-targets');
    if (!targets || !targets.low) {
        el.innerHTML = '<div class="empty-state">No analyst targets available</div>';
        return;
    }

    const low = targets.low;
    const high = targets.high;
    const mean = targets.mean;
    const median = targets.median;
    const range = high - low;

    const currentPct = range > 0 ? ((currentPrice - low) / range) * 100 : 50;
    const meanPct = range > 0 ? ((mean - low) / range) * 100 : 50;

    el.innerHTML = `
        <div class="target-bar-wrap">
            <div class="target-bar">
                <div class="target-marker mean" style="left:${meanPct}%" title="Mean: ${fmtCurrency(mean)}"></div>
                <div class="target-marker current" style="left:${Math.max(0, Math.min(100, currentPct))}%" title="Current: ${fmtCurrency(currentPrice)}"></div>
            </div>
            <div class="target-labels">
                <span>${fmtCurrency(low)}</span>
                <span>${fmtCurrency(high)}</span>
            </div>
        </div>
        <div class="target-stats">
            <div class="target-stat"><span class="metric-label">Current</span><span class="metric-value">${fmtCurrency(currentPrice)}</span></div>
            <div class="target-stat"><span class="metric-label">Mean</span><span class="metric-value">${fmtCurrency(mean)}</span></div>
            <div class="target-stat"><span class="metric-label">Median</span><span class="metric-value">${fmtCurrency(median)}</span></div>
            <div class="target-stat"><span class="metric-label">Low</span><span class="metric-value">${fmtCurrency(low)}</span></div>
            <div class="target-stat"><span class="metric-label">High</span><span class="metric-value">${fmtCurrency(high)}</span></div>
        </div>
    `;
}

function renderRecommendations(recs) {
    const el = document.getElementById('recommendations');
    const c = recs.current;
    if (!c || (!c.strongBuy && !c.buy && !c.hold && !c.sell && !c.strongSell)) {
        el.innerHTML = '<div class="empty-state">No recommendation data available</div>';
        return;
    }

    const total = c.strongBuy + c.buy + c.hold + c.sell + c.strongSell;
    const pct = (v) => total > 0 ? (v / total * 100).toFixed(1) : 0;

    const segments = [
        { cls: 'strong-buy', val: c.strongBuy, label: 'Strong Buy' },
        { cls: 'buy', val: c.buy, label: 'Buy' },
        { cls: 'hold', val: c.hold, label: 'Hold' },
        { cls: 'sell', val: c.sell, label: 'Sell' },
        { cls: 'strong-sell', val: c.strongSell, label: 'Strong Sell' },
    ].filter(s => s.val > 0);

    el.innerHTML = `
        <div class="rec-bar-wrap">
            <div class="rec-bar">
                ${segments.map(s =>
                    `<div class="rec-segment ${s.cls}" style="flex:${s.val}" title="${s.label}: ${s.val}">${s.val}</div>`
                ).join('')}
            </div>
        </div>
        <div class="rec-legend">
            ${[
                { cls: 'strong-buy', label: 'Strong Buy', val: c.strongBuy, color: '#00c853' },
                { cls: 'buy', label: 'Buy', val: c.buy, color: '#4caf50' },
                { cls: 'hold', label: 'Hold', val: c.hold, color: '#ff9800' },
                { cls: 'sell', label: 'Sell', val: c.sell, color: '#ff5722' },
                { cls: 'strong-sell', label: 'Strong Sell', val: c.strongSell, color: '#d32f2f' },
            ].map(s =>
                `<div class="rec-legend-item">
                    <span class="rec-dot" style="background:${s.color}"></span>
                    ${s.label}: ${s.val}
                </div>`
            ).join('')}
        </div>
        <div style="margin-top:8px;font-size:11px;color:var(--text-muted)">${total} analysts</div>
    `;
}

function renderFinancials(data) {
    const thead = document.getElementById('financials-thead');
    const tbody = document.getElementById('financials-tbody');

    if (!data || !data.columns || data.columns.length === 0) {
        thead.innerHTML = '';
        tbody.innerHTML = '<tr><td class="empty-state" colspan="5">No financial data available</td></tr>';
        return;
    }

    thead.innerHTML = '<tr><th>Metric</th>' +
        data.columns.map(c => `<th>${c}</th>`).join('') + '</tr>';

    tbody.innerHTML = data.rows.map(row => {
        const cells = row.values.map(v => {
            const formatted = fmtLarge(v);
            const cls = v != null && v < 0 ? ' class="negative"' : '';
            return `<td${cls}>${formatted}</td>`;
        }).join('');
        return `<tr><td>${row.label}</td>${cells}</tr>`;
    }).join('');
}

function renderNews(items) {
    const el = document.getElementById('news-list');
    if (!items || items.length === 0) {
        el.innerHTML = '<div class="empty-state">No recent news</div>';
        return;
    }
    el.innerHTML = items.slice(0, 10).map(n => `
        <div class="news-item">
            <a href="${n.url}" target="_blank" rel="noopener">${n.title}</a>
            <div class="news-meta">${n.source}${n.publishedAt ? ' &middot; ' + fmtDate(n.publishedAt) : ''}</div>
        </div>
    `).join('');
}

function renderUpgrades(items) {
    const el = document.getElementById('upgrades-list');
    if (!items || items.length === 0) {
        el.innerHTML = '<div class="empty-state">No recent upgrades/downgrades</div>';
        return;
    }
    el.innerHTML = items.slice(0, 15).map(u => `
        <div class="upgrade-row">
            <span class="upgrade-date">${u.date}</span>
            <span class="upgrade-firm">${u.firm}</span>
            <span class="upgrade-grade">${u.toGrade}</span>
            <span class="upgrade-action" style="color:${u.action === 'up' ? 'var(--gain)' : u.action === 'down' ? 'var(--loss)' : 'var(--text-secondary)'}">${u.action || ''}</span>
        </div>
    `).join('');
}

function renderFilings(items) {
    const el = document.getElementById('filings-list');
    if (!items || items.length === 0) {
        el.innerHTML = '<div class="empty-state">No SEC filings available</div>';
        return;
    }
    el.innerHTML = items.slice(0, 30).map(f => `
        <div class="filing-row">
            <span class="filing-form">${f.formType}</span>
            <span class="filing-date">${f.filingDate}</span>
            <span class="filing-desc">${f.description || f.formType}</span>
        </div>
    `).join('');
}
