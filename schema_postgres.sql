-- Production PostgreSQL Schema
-- =============================
-- Run this to set up PostgreSQL database

-- Accounts table (broker connections)
CREATE TABLE IF NOT EXISTS accounts (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255),
    password VARCHAR(255),
    tradovate_token TEXT,
    tradovate_refresh_token TEXT,
    md_access_token TEXT,
    token_expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Traders table (trading accounts)
CREATE TABLE IF NOT EXISTS traders (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    name VARCHAR(255) NOT NULL,
    subaccount_id INTEGER,
    subaccount_name VARCHAR(255),
    is_demo BOOLEAN DEFAULT TRUE,
    max_contracts INTEGER DEFAULT 10,
    custom_ticker VARCHAR(50),
    multiplier REAL DEFAULT 1.0,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recorders table (signal receivers)
CREATE TABLE IF NOT EXISTS recorders (
    id SERIAL PRIMARY KEY,
    trader_id INTEGER REFERENCES traders(id),
    name VARCHAR(255) NOT NULL UNIQUE,
    enabled BOOLEAN DEFAULT TRUE,
    webhook_token VARCHAR(255) UNIQUE,
    ticker VARCHAR(50),
    position_size INTEGER DEFAULT 1,
    tp_enabled BOOLEAN DEFAULT TRUE,
    tp_targets TEXT,  -- JSON array of TP targets
    sl_enabled BOOLEAN DEFAULT FALSE,
    sl_amount REAL,
    trailing_sl BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recorded trades table
CREATE TABLE IF NOT EXISTS recorded_trades (
    id SERIAL PRIMARY KEY,
    recorder_id INTEGER REFERENCES recorders(id),
    signal_id VARCHAR(255),
    ticker VARCHAR(50),
    action VARCHAR(20),
    side VARCHAR(10),
    entry_price REAL,
    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    exit_price REAL,
    exit_time TIMESTAMP,
    quantity INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'open',
    tp_price REAL,
    sl_price REAL,
    tp_order_id VARCHAR(100),
    sl_order_id VARCHAR(100),
    pnl REAL,
    pnl_ticks REAL,
    exit_reason VARCHAR(50),
    broker_order_id VARCHAR(100),
    broker_strategy_id VARCHAR(100),
    broker_fill_price REAL,
    broker_managed_tp_sl BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recorder positions table (current position tracking)
CREATE TABLE IF NOT EXISTS recorder_positions (
    id SERIAL PRIMARY KEY,
    recorder_id INTEGER REFERENCES recorders(id),
    ticker VARCHAR(50),
    side VARCHAR(10),
    total_quantity INTEGER DEFAULT 0,
    fills TEXT,  -- JSON array of fills
    avg_entry_price REAL,
    realized_pnl REAL DEFAULT 0,
    unrealized_pnl REAL DEFAULT 0,
    worst_unrealized_pnl REAL DEFAULT 0,
    exit_price REAL,
    exit_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Signals table (webhook history)
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    recorder_id INTEGER REFERENCES recorders(id),
    raw_data TEXT,
    action VARCHAR(20),
    ticker VARCHAR(50),
    price REAL,
    processed BOOLEAN DEFAULT FALSE,
    result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_recorded_trades_recorder_status ON recorded_trades(recorder_id, status);
CREATE INDEX IF NOT EXISTS idx_recorded_trades_status ON recorded_trades(status);
CREATE INDEX IF NOT EXISTS idx_recorder_positions_recorder_status ON recorder_positions(recorder_id, status);
CREATE INDEX IF NOT EXISTS idx_signals_recorder_id ON signals(recorder_id);
CREATE INDEX IF NOT EXISTS idx_recorders_webhook_token ON recorders(webhook_token);
CREATE INDEX IF NOT EXISTS idx_recorders_name ON recorders(name);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables
DROP TRIGGER IF EXISTS update_accounts_updated_at ON accounts;
CREATE TRIGGER update_accounts_updated_at
    BEFORE UPDATE ON accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_traders_updated_at ON traders;
CREATE TRIGGER update_traders_updated_at
    BEFORE UPDATE ON traders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_recorders_updated_at ON recorders;
CREATE TRIGGER update_recorders_updated_at
    BEFORE UPDATE ON recorders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_recorded_trades_updated_at ON recorded_trades;
CREATE TRIGGER update_recorded_trades_updated_at
    BEFORE UPDATE ON recorded_trades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_recorder_positions_updated_at ON recorder_positions;
CREATE TRIGGER update_recorder_positions_updated_at
    BEFORE UPDATE ON recorder_positions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed)
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_user;
