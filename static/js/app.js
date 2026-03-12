/* Main application controller */

let currentTicker = null;
let priceInterval = null;
let currentStmtType = 'income';
let currentFreq = 'annual';

// === Auth ===
function getToken() { return localStorage.getItem('ss_token'); }
function setToken(token) { localStorage.setItem('ss_token', token); }
function clearToken() { localStorage.removeItem('ss_token'); localStorage.removeItem('ss_user'); }
function getUser() { try { return JSON.parse(localStorage.getItem('ss_user')); } catch { return null; } }
function setUser(user) { localStorage.setItem('ss_user', JSON.stringify(user)); }

function showLogin() {
    document.getElementById('login-screen').classList.remove('hidden');
    document.getElementById('welcome').classList.add('hidden');
    document.getElementById('dashboard').classList.add('hidden');
    document.getElementById('logout-btn').classList.add('hidden');
    document.getElementById('user-info').textContent = '';
    document.getElementById('login-email').focus();
}

function hideLogin() {
    document.getElementById('login-screen').classList.add('hidden');
    const user = getUser();
    if (user) {
        document.getElementById('user-info').textContent = user.name || user.email;
        document.getElementById('logout-btn').classList.remove('hidden');
    }
}

async function login(email, password) {
    const errEl = document.getElementById('login-error');
    const btn = document.getElementById('login-btn');
    errEl.classList.add('hidden');
    btn.disabled = true;
    btn.textContent = 'Signing in...';

    try {
        const res = await fetch('/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });
        const data = await res.json();
        if (!res.ok) {
            errEl.textContent = data.error || 'Login failed';
            errEl.classList.remove('hidden');
            return;
        }
        setToken(data.token);
        setUser(data.user);
        hideLogin();
        document.getElementById('welcome').classList.remove('hidden');
        document.getElementById('ticker-input').focus();
    } catch (e) {
        errEl.textContent = 'Network error. Try again.';
        errEl.classList.remove('hidden');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Sign In';
    }
}

function logout() {
    clearToken();
    if (priceInterval) clearInterval(priceInterval);
    currentTicker = null;
    showLogin();
}

// Login form handler
document.getElementById('login-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    if (email && password) login(email, password);
});

// Logout button
document.getElementById('logout-btn').addEventListener('click', logout);

// Check auth on page load
async function checkAuth() {
    const token = getToken();
    if (!token) {
        // Try without auth — if JWT_SECRET is not set, the API allows unauthenticated access
        try {
            const res = await fetch('/api/v1/auth/me');
            if (res.ok) {
                const user = await res.json();
                if (user.id === null) {
                    // Auth disabled (local dev mode)
                    setUser({ email: 'dev', name: 'Local Dev', role: 'admin' });
                    hideLogin();
                    document.getElementById('welcome').classList.remove('hidden');
                    return;
                }
            }
        } catch { /* ignore */ }
        showLogin();
        return;
    }
    // Verify token is still valid
    try {
        const res = await fetch('/api/v1/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` },
        });
        if (res.ok) {
            const user = await res.json();
            setUser(user);
            hideLogin();
            document.getElementById('welcome').classList.remove('hidden');
        } else {
            clearToken();
            showLogin();
        }
    } catch {
        // Network error — show login
        showLogin();
    }
}

checkAuth();

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
let currentPeriods = 5;
let lastFinancialsData = null;

async function loadFinancials(ticker) {
    const data = await fetchJSON(`/api/financials/${ticker}?type=${currentStmtType}&freq=${currentFreq}&periods=${currentPeriods}`);
    lastFinancialsData = data;
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

document.getElementById('financials-periods').addEventListener('change', (e) => {
    currentPeriods = parseInt(e.target.value, 10);
    if (currentTicker) loadFinancials(currentTicker);
});

document.getElementById('financials-csv-btn').addEventListener('click', () => {
    if (!lastFinancialsData || !lastFinancialsData.columns || lastFinancialsData.columns.length === 0) return;
    const d = lastFinancialsData;
    const header = ['Metric', ...d.columns];
    const lines = [header.join(',')];
    for (const row of d.rows) {
        const vals = row.values.map(v => v != null ? v : '');
        lines.push([`"${row.label}"`, ...vals].join(','));
    }
    const csv = lines.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentTicker}_${currentStmtType}_${currentFreq}.csv`;
    a.click();
    URL.revokeObjectURL(url);
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
    const headers = {};
    const token = getToken();
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    const res = await fetch(url, { headers });
    if (res.status === 401) {
        clearToken();
        showLogin();
        throw new Error('Session expired');
    }
    return res.json();
}

// Handle URL hash for direct linking
if (window.location.hash) {
    const ticker = window.location.hash.slice(1).toUpperCase();
    if (ticker) {
        // Will load after auth check completes
        const waitForAuth = setInterval(() => {
            if (!document.getElementById('login-screen').classList.contains('hidden') ||
                getToken() || getUser()) {
                clearInterval(waitForAuth);
                if (getToken() || getUser()) {
                    document.getElementById('ticker-input').value = ticker;
                    loadStock(ticker);
                }
            }
        }, 100);
        // Timeout after 5 seconds
        setTimeout(() => clearInterval(waitForAuth), 5000);
    }
}
