-- Phase 1: Core schema for portfolio tracking platform
-- Run against PostgreSQL via: psql $DATABASE_URL -f screener/migrations/001_initial.sql

BEGIN;

-- Canonical stock record
CREATE TABLE IF NOT EXISTS stocks (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(20) NOT NULL,
    exchange        VARCHAR(10) NOT NULL DEFAULT 'NASDAQ',
    yf_ticker       VARCHAR(20) NOT NULL,
    name            VARCHAR(200),
    sector          VARCHAR(100),
    industry        VARCHAR(100),
    cik             INTEGER,
    has_sec_filings BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ticker, exchange)
);

-- Portfolio positions (multiple lots per stock)
CREATE TABLE IF NOT EXISTS positions (
    id              SERIAL PRIMARY KEY,
    stock_id        INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    shares          DECIMAL(18,6) NOT NULL,
    purchase_price  DECIMAL(18,6) NOT NULL,
    purchase_date   DATE NOT NULL,
    currency        VARCHAR(5) DEFAULT 'USD',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Watchlist
CREATE TABLE IF NOT EXISTS watchlist (
    id              SERIAL PRIMARY KEY,
    stock_id        INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE UNIQUE,
    added_at        TIMESTAMPTZ DEFAULT NOW(),
    notes           TEXT
);

-- Filing metadata (tracks what's in S3)
CREATE TABLE IF NOT EXISTS filings (
    id                  SERIAL PRIMARY KEY,
    stock_id            INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    form_type           VARCHAR(20) NOT NULL,
    filing_date         DATE NOT NULL,
    accession_number    VARCHAR(30) NOT NULL UNIQUE,
    description         TEXT,
    sec_url             TEXT,
    s3_raw_key          TEXT,
    s3_processed_key    TEXT,
    processed_at        TIMESTAMPTZ,
    word_count          INTEGER,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_filings_stock_date ON filings(stock_id, filing_date DESC);

-- AI research reports
CREATE TABLE IF NOT EXISTS research_reports (
    id                  SERIAL PRIMARY KEY,
    stock_id            INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    report_type         VARCHAR(30) NOT NULL,
    trigger_filing_id   INTEGER REFERENCES filings(id),
    s3_report_key       TEXT NOT NULL,
    summary             TEXT,
    outlook             VARCHAR(20),
    risk_level          VARCHAR(20),
    price_target_low    DECIMAL(18,2),
    price_target_mid    DECIMAL(18,2),
    price_target_high   DECIMAL(18,2),
    llm_model           VARCHAR(50),
    llm_cost_usd        DECIMAL(10,6),
    filing_count        INTEGER,
    generated_at        TIMESTAMPTZ DEFAULT NOW(),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_reports_stock ON research_reports(stock_id, generated_at DESC);

-- Filing check log
CREATE TABLE IF NOT EXISTS filing_check_log (
    id                  SERIAL PRIMARY KEY,
    stock_id            INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    checked_at          TIMESTAMPTZ DEFAULT NOW(),
    new_filings_found   INTEGER DEFAULT 0,
    error               TEXT
);

-- Key-value settings (single-user)
CREATE TABLE IF NOT EXISTS settings (
    key         VARCHAR(100) PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Default settings
INSERT INTO settings (key, value) VALUES
    ('filing_check_interval_hours', '6'),
    ('llm_provider', 'claude'),
    ('alert_email', ''),
    ('ses_from_email', '')
ON CONFLICT (key) DO NOTHING;

-- Q&A conversation history
CREATE TABLE IF NOT EXISTS qa_sessions (
    id          SERIAL PRIMARY KEY,
    stock_id    INTEGER NOT NULL REFERENCES stocks(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS qa_messages (
    id          SERIAL PRIMARY KEY,
    session_id  INTEGER NOT NULL REFERENCES qa_sessions(id) ON DELETE CASCADE,
    role        VARCHAR(10) NOT NULL,
    content     TEXT NOT NULL,
    llm_model   VARCHAR(50),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

COMMIT;
