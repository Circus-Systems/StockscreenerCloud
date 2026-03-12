-- Phase 2: User authentication and multi-tenancy
-- Adds users table, scopes positions and watchlist per-user

BEGIN;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(200) NOT NULL UNIQUE,
    password_hash VARCHAR(200) NOT NULL,
    role          VARCHAR(20) NOT NULL DEFAULT 'readonly',
    name          VARCHAR(200),
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Add user_id to positions and watchlist
ALTER TABLE positions ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);
ALTER TABLE watchlist ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id);

-- Drop the old single-user UNIQUE on watchlist(stock_id)
-- Replace with per-user uniqueness
ALTER TABLE watchlist DROP CONSTRAINT IF EXISTS watchlist_stock_id_key;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'watchlist_user_stock_unique'
    ) THEN
        ALTER TABLE watchlist ADD CONSTRAINT watchlist_user_stock_unique UNIQUE(user_id, stock_id);
    END IF;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_positions_user ON positions(user_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id);

COMMIT;
