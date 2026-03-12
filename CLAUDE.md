# StockScreener Cloud

## What This Is
A stock analysis dashboard with portfolio tracking, SEC EDGAR filings (XBRL), financial statements, and multi-user auth. Flask backend, vanilla JS frontend, PostgreSQL database, deployed on AWS App Runner.

## Architecture

```
Browser → App Runner (Docker/gunicorn) → Flask
                                          ├── /api/* (stock data - no auth)
                                          └── /api/v1/* (portfolio, watchlist, users - JWT auth)
                                                ├── PostgreSQL (RDS)
                                                ├── yfinance (market data)
                                                └── SEC EDGAR (filings)
```

## Deployment

**Auto-deploy pipeline:** Push to `main` → GitHub Actions builds Docker → pushes to ECR → App Runner auto-deploys (~3 min)

- **URL:** https://chw35kgqn3.us-east-1.awsapprunner.com
- **Repo:** https://github.com/Circus-Systems/StockscreenerCloud
- **ECR:** 860272297846.dkr.ecr.us-east-1.amazonaws.com/stockscreener
- **RDS:** stockscreener-db.cwposa8mu4a1.us-east-1.rds.amazonaws.com (PostgreSQL)
- **S3:** stockscreener-cloud-data
- **Region:** us-east-1

### Environment Variables (App Runner)
```
DATABASE_URL    = postgresql://screener:<pw>@stockscreener-db.cwposa8mu4a1.us-east-1.rds.amazonaws.com:5432/stockscreener
JWT_SECRET      = <64-char secret>
ADMIN_EMAIL     = andrew.james.joyce@gmail.com
ADMIN_PASSWORD  = <password>
EDGAR_EMAIL     = andrew@sailingcircus.com
S3_BUCKET       = stockscreener-cloud-data
AWS_REGION      = us-east-1
PORT            = 8080
```

### CI/CD Pipeline (.github/workflows/deploy.yml)
Builds Docker image, tags with commit SHA + `latest`, pushes both to ECR. App Runner has auto-deploy enabled from ECR.

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `app.py` | Flask app, registers blueprints, stock data API routes (`/api/*`) |
| `screener/api_v1.py` | Auth-protected REST API (`/api/v1/*`) — portfolio, watchlist, users, settings |
| `screener/auth.py` | User CRUD, bcrypt password hashing, authenticate() |
| `screener/db.py` | PostgreSQL connection, migration runner, admin seeding |
| `screener/models.py` | Domain operations — stocks, positions, watchlist, settings (user-scoped) |
| `screener/data_service.py` | Aggregates data from yfinance + EDGAR for each ticker |
| `screener/edgar_client.py` | SEC EDGAR XBRL client |
| `screener/xbrl_mapping.py` | Maps XBRL tags to financial statement line items |
| `screener/yahoo.py` | yfinance wrapper |
| `screener/cache.py` | File-based cache at `data/{TICKER}/` |
| `screener/storage.py` | Filing storage (local, future: S3) |

### Frontend (vanilla JS SPA)
| File | Purpose |
|------|---------|
| `templates/index.html` | Single-page app shell — login screen, dashboard, modals |
| `static/js/app.js` | Main controller — auth, search, data loading |
| `static/js/chart.js` | Lightweight Charts price/volume chart |
| `static/js/metrics.js` | Renders metric panels, financial tables, filings |
| `static/js/calcs.js` | Metric calculation pop-ups |
| `static/js/utils.js` | Formatting helpers (currency, numbers, dates) |
| `static/css/dashboard.css` | All styles — dark theme, login, panels, modals |

### Database
| File | Purpose |
|------|---------|
| `screener/migrations/001_initial.sql` | Core schema: stocks, positions, watchlist, filings, settings, research_reports |
| `screener/migrations/002_users.sql` | Users table, adds user_id to positions/watchlist |

## Database Schema

- **stocks** — Global stock catalog (ticker, exchange, yf_ticker, sector, industry, CIK)
- **positions** — Portfolio positions per user (stock_id, user_id, shares, purchase_price, purchase_date)
- **watchlist** — Watched stocks per user (stock_id, user_id, notes)
- **users** — Auth (email, password_hash, role: admin|readonly)
- **settings** — Global key-value config
- **filings** — SEC filing metadata (for future S3 pipeline)
- **research_reports** — AI research reports (future)
- **_migrations** — Tracks which SQL migrations have been applied

## Auth System

- **JWT tokens** with user_id, email, role in payload
- **Two roles:** `admin` (full access, user management) and `readonly` (own portfolio/watchlist only)
- **Admin creates users** — no self-registration
- **Auth disabled** when `JWT_SECRET` env var is not set (local dev convenience)
- Token stored in localStorage, sent as `Authorization: Bearer <token>` header
- 401 responses auto-redirect to login screen

## API Endpoints

### Public stock data (`/api/*` — no auth)
```
GET /api/quote/<ticker>
GET /api/profile/<ticker>
GET /api/metrics/<ticker>
GET /api/history/<ticker>?period=1y
GET /api/financials/<ticker>?type=income&freq=annual&periods=5
GET /api/recommendations/<ticker>
GET /api/analyst_targets/<ticker>
GET /api/news/<ticker>
GET /api/upgrades/<ticker>
GET /api/holders/<ticker>
GET /api/filings/<ticker>
POST /api/fetch/<ticker>
GET /api/filing-proxy?url=<sec_url>
```

### Authenticated (`/api/v1/*` — JWT required)
```
POST /api/v1/auth/login          → { email, password } → { token, user }
GET  /api/v1/auth/me             → current user info

GET  /api/v1/portfolio           → user's positions with live prices + P&L
POST /api/v1/portfolio           → add position { ticker, shares, purchasePrice, purchaseDate }
PUT  /api/v1/portfolio/<id>      → update position
DELETE /api/v1/portfolio/<id>    → delete position
GET  /api/v1/portfolio/summary   → aggregate P&L

GET  /api/v1/watchlist           → user's watchlist with prices
POST /api/v1/watchlist           → add { ticker }
DELETE /api/v1/watchlist/<id>    → remove

GET  /api/v1/users               → list users (admin only)
POST /api/v1/users               → create user (admin only)
PUT  /api/v1/users/<id>          → update user (admin only)
DELETE /api/v1/users/<id>        → delete user (admin only)

GET  /api/v1/settings            → global settings (admin only)
PUT  /api/v1/settings            → update settings (admin only)
```

## Future Phases (planned, not yet built)

- **Phase 2:** S3 filing storage + sync pipeline (download SEC filings to S3, process HTML → structured text)
- **Phase 3:** LLM research reports + Q&A (Claude/OpenAI abstraction layer, AI-generated stock analysis)
- **Phase 4:** APScheduler for automated filing checks + SES email alerts
- **Phase 5:** Dashboard UI panels for portfolio, watchlist, research; ASX exchange support

## Conventions

- **Python 3.13**, Flask 3.x
- Dark theme UI with CSS variables (see `:root` in dashboard.css)
- Monospace font for financial data (`--font-mono`)
- All SQL uses parameterized queries (no f-strings)
- Migrations are numbered `001_*.sql`, `002_*.sql`, etc. — run in order by `db.init_db()`
- Stock tickers stored uppercase, ASX tickers get `.AX` suffix in `yf_ticker`
- `models.py` functions take optional `user_id` param — `None` means global (backwards compatible)
