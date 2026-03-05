/* Main application controller */

let currentTicker = null;
let priceInterval = null;
let currentStmtType = 'income';
let currentFreq = 'annual';

// === Ticker Search ===
document.getElementById('search-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = document.getElementById('ticker-input');
    const ticker = input.value.trim().toUpperCase();
    if (ticker) loadStock(ticker);
});

async function loadStock(ticker) {
    currentTicker = ticker;
    document.getElementById('ticker-input').value = ticker;

    // Show loading, hide welcome
    document.getElementById('welcome').classList.add('hidden');
    document.getElementById('loading-overlay').classList.remove('hidden');
    document.getElementById('dashboard').classList.add('hidden');

    try {
        // Fetch primary data in parallel
        const [quote, metrics, history, targets, recs] = await Promise.all([
            fetchJSON(`/api/quote/${ticker}`),
            fetchJSON(`/api/metrics/${ticker}`),
            fetchJSON(`/api/history/${ticker}?period=1y`),
            fetchJSON(`/api/analyst_targets/${ticker}`),
            fetchJSON(`/api/recommendations/${ticker}`),
        ]);

        if (quote.error) {
            alert(`Error loading ${ticker}: ${quote.error}`);
            document.getElementById('loading-overlay').classList.add('hidden');
            document.getElementById('welcome').classList.remove('hidden');
            return;
        }

        // Show dashboard
        document.getElementById('loading-overlay').classList.add('hidden');
        document.getElementById('dashboard').classList.remove('hidden');

        // Store metrics with current price for calculation pop-ups
        metrics._price = quote.price;
        setMetricsData(metrics);

        // Render primary sections
        renderHeader(quote);
        renderChart(history);
        renderMetrics(metrics);
        renderAnalystTargets(targets, quote.price);
        renderRecommendations(recs);

        // Set active period button
        setActivePeriod('1y');

        // Start price polling
        if (priceInterval) clearInterval(priceInterval);
        priceInterval = setInterval(() => refreshPrice(ticker), 15000);

        // Load secondary data (non-blocking)
        loadFinancials(ticker);
        loadSecondaryPanels(ticker);

        // Trigger full background fetch
        fetch(`/api/fetch/${ticker}`, { method: 'POST' });

    } catch (err) {
        console.error('Error loading stock:', err);
        document.getElementById('loading-overlay').classList.add('hidden');
        document.getElementById('welcome').classList.remove('hidden');
        alert(`Failed to load ${ticker}. Check the ticker and try again.`);
    }
}

// === Header ===
function renderHeader(quote) {
    const profile = fetchJSON(`/api/profile/${currentTicker}`).then(p => {
        const meta = [p.sector, p.industry, p.exchange].filter(Boolean).join(' | ');
        document.getElementById('header-meta').textContent = meta;
    });

    document.getElementById('header-ticker').textContent = quote.ticker;
    document.getElementById('header-name').textContent = quote.name;
    updatePrice(quote);
}

function updatePrice(quote) {
    const priceEl = document.getElementById('header-price');
    const changeEl = document.getElementById('header-change');

    const sign = quote.change >= 0 ? '+' : '';
    const cls = quote.change >= 0 ? 'price-up' : 'price-down';

    priceEl.textContent = fmtCurrency(quote.price);
    priceEl.className = `stock-price ${cls}`;

    changeEl.textContent = `${sign}${fmtNumber(quote.change)} (${sign}${fmtNumber(quote.changePct)}%)`;
    changeEl.className = `stock-change ${cls}`;

    // Pulse animation
    priceEl.classList.remove('price-pulse-up', 'price-pulse-down');
    void priceEl.offsetWidth; // force reflow
    priceEl.classList.add(quote.change >= 0 ? 'price-pulse-up' : 'price-pulse-down');
}

async function refreshPrice(ticker) {
    try {
        const quote = await fetchJSON(`/api/quote/${ticker}`);
        if (!quote.error) updatePrice(quote);
    } catch (e) { /* silent fail on poll */ }
}

// === Period Buttons ===
document.getElementById('period-buttons').addEventListener('click', (e) => {
    if (e.target.tagName !== 'BUTTON') return;
    const period = e.target.dataset.period;
    setActivePeriod(period);
    changePeriod(currentTicker, period);
});

function setActivePeriod(period) {
    document.querySelectorAll('#period-buttons button').forEach(b => {
        b.classList.toggle('active', b.dataset.period === period);
    });
}

// === Financials ===
async function loadFinancials(ticker) {
    const data = await fetchJSON(`/api/financials/${ticker}?type=${currentStmtType}&freq=${currentFreq}`);
    renderFinancials(data);
}

document.querySelectorAll('.stmt-tabs button').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.stmt-tabs button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentStmtType = btn.dataset.type;
        if (currentTicker) loadFinancials(currentTicker);
    });
});

document.querySelectorAll('.freq-tabs button').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.freq-tabs button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFreq = btn.dataset.freq;
        if (currentTicker) loadFinancials(currentTicker);
    });
});

// === Secondary Panels ===
async function loadSecondaryPanels(ticker) {
    const [news, upgrades, filings] = await Promise.all([
        fetchJSON(`/api/news/${ticker}`),
        fetchJSON(`/api/upgrades/${ticker}`),
        fetchJSON(`/api/filings/${ticker}`),
    ]);
    renderNews(news);
    renderUpgrades(upgrades);
    renderFilings(filings);
}

// === Utilities ===
async function fetchJSON(url) {
    const res = await fetch(url);
    return res.json();
}

// Focus ticker input on page load
document.getElementById('ticker-input').focus();

// Handle URL hash for direct linking
if (window.location.hash) {
    const ticker = window.location.hash.slice(1).toUpperCase();
    if (ticker) {
        document.getElementById('ticker-input').value = ticker;
        loadStock(ticker);
    }
}
