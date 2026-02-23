# Database Schema Reference — Just Trades Platform

> **Dual-database**: SQLite (local dev) + PostgreSQL (Railway production)
> **ALL SQL must work on BOTH** — use `'%s' if is_postgres else '?'` (Rule 4)
> Schema defined in: recorder_service.py ~line 2869+
> Last verified: Feb 23, 2026

---

## CRITICAL GOTCHAS

1. **`recorded_trades` has NO `subaccount_id` column** — tp_order_id is shared across ALL accounts on a recorder (Rule 5)
2. **NULL masking in templates** — `{{ field or 1 }}` shows NULL as "1" in the UI (Rule 19)
3. **PostgreSQL uses `%s`, SQLite uses `?`** — hardcoded `?` silently fails on production (Rule 4)
4. **PostgreSQL string defaults use single quotes**, SQLite uses double quotes
5. **Boolean values**: PostgreSQL = `'TRUE'/'FALSE'`, SQLite = `1/0` — use `enabled_value = 'TRUE' if is_postgres else '1'`

### SQL Placeholder Pattern

```python
is_postgres = is_using_postgres()
placeholder = '%s' if is_postgres else '?'
enabled_value = 'TRUE' if is_postgres else '1'

cursor.execute(f'SELECT * FROM table WHERE id = {placeholder}', (value,))
```

---

## TABLE: users

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0,
    is_approved INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## TABLE: accounts

```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    broker TEXT DEFAULT 'Tradovate',        -- 'Tradovate', 'NinjaTrader', 'ProjectX', 'Webull'
    auth_type TEXT DEFAULT 'credentials',    -- 'credentials', 'api_key'
    environment TEXT DEFAULT 'demo',         -- 'demo', 'live'
    -- Tradovate/NinjaTrader OAuth
    tradovate_token TEXT,
    tradovate_refresh_token TEXT,
    tradovate_token_expires TEXT,
    tradovate_username TEXT,
    tradovate_password TEXT,
    tradovate_client_id TEXT,
    tradovate_client_secret TEXT,
    -- ProjectX
    projectx_api_key TEXT,
    projectx_username TEXT,
    -- Webull
    webull_app_key TEXT,
    webull_app_secret TEXT,
    -- State
    subaccount_id TEXT,                      -- Tradovate subaccount ID
    account_spec TEXT,                       -- Tradovate account spec (e.g., "DEMO12345")
    enabled INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

**Key field:** `subaccount_id` is the Tradovate account ID used for API calls.

---

## TABLE: recorders

The "strategy" — defines what symbol to trade and how (TP/SL/DCA settings).

```sql
CREATE TABLE recorders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    user_id INTEGER,
    strategy_type TEXT DEFAULT 'Futures',
    symbol TEXT,
    -- Account linkage
    demo_account_id TEXT,
    account_id INTEGER,
    -- Position Settings
    initial_position_size INTEGER DEFAULT 2,
    add_position_size INTEGER DEFAULT 2,
    -- TP Settings
    tp_units TEXT DEFAULT 'Ticks',            -- 'Ticks', 'Points', 'Percent'
    trim_units TEXT DEFAULT 'Contracts',       -- 'Contracts', 'Percent'
    tp_targets TEXT DEFAULT '[]',              -- JSON: [{"ticks":20,"trim":1}, ...]
    -- SL Settings
    sl_enabled INTEGER DEFAULT 0,
    sl_amount REAL DEFAULT 0,
    sl_units TEXT DEFAULT 'Ticks',
    sl_type TEXT DEFAULT 'Fixed',             -- 'Fixed', 'Trail', 'Trailing'
    trail_trigger REAL DEFAULT 0,
    trail_freq REAL DEFAULT 0,
    -- Averaging Down (DCA)
    avg_down_enabled INTEGER DEFAULT 0,       -- aka dca_enabled
    avg_down_amount INTEGER DEFAULT 1,
    avg_down_point REAL DEFAULT 0,
    avg_down_units TEXT DEFAULT 'Ticks',
    -- Break-Even
    break_even_enabled INTEGER DEFAULT 0,
    break_even_ticks REAL DEFAULT 0,
    break_even_offset REAL DEFAULT 0,
    -- Filter Settings
    add_delay INTEGER DEFAULT 1,              -- seconds between DCA entries
    signal_cooldown INTEGER DEFAULT 0,        -- seconds between signals
    max_signals_per_session INTEGER DEFAULT 0, -- 0 = unlimited
    max_contracts_per_trade INTEGER DEFAULT 0,
    max_daily_loss REAL DEFAULT 0,            -- 0 = disabled
    -- Time Filters
    time_filter_1_start TEXT DEFAULT '8:45 AM',
    time_filter_1_end TEXT DEFAULT '3:00 PM',
    time_filter_enabled INTEGER DEFAULT 0,
    time_filter_2_start TEXT,
    time_filter_2_end TEXT,
    time_filter_2_enabled INTEGER DEFAULT 0,
    auto_flat_after_cutoff INTEGER DEFAULT 0,
    -- Other
    custom_ticker TEXT,                       -- Override symbol for execution
    inverse_strategy INTEGER DEFAULT 0,
    option_premium_filter REAL DEFAULT 0,
    direction_filter TEXT,
    -- Webhook
    webhook_token TEXT UNIQUE,                -- UUID for webhook URL
    -- State
    recording_enabled INTEGER DEFAULT 1,
    simulation_mode INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_recorders_webhook ON recorders(webhook_token);
```

**tp_targets format:**
```json
[
    {"ticks": 20, "trim": 1},
    {"ticks": 50, "trim": 1},
    {"ticks": 100, "trim": 1}
]
```
Note: Some legacy data uses `"value"` instead of `"ticks"` — code handles both.

---

## TABLE: traders

Links an account to a recorder with per-account overrides.

```sql
CREATE TABLE traders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    recorder_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    enabled INTEGER DEFAULT 1,
    -- Override settings (NULL = use recorder default)
    multiplier REAL DEFAULT 1.0,              -- account_multiplier (scales all quantities)
    initial_position_size INTEGER,            -- NULL falls back to recorder
    add_position_size INTEGER,                -- NULL falls back to recorder
    -- Per-trader risk overrides (all optional)
    sl_type TEXT,
    sl_amount REAL,
    sl_enabled INTEGER,
    trail_trigger REAL,
    trail_freq REAL,
    tp_targets TEXT,
    break_even_enabled INTEGER,
    break_even_ticks REAL,
    break_even_offset REAL,
    dca_enabled INTEGER,                      -- overrides recorder avg_down_enabled
    custom_ticker TEXT,
    add_delay INTEGER,
    signal_cooldown INTEGER,
    max_signals_per_session INTEGER,
    max_daily_loss REAL,
    -- Broker Account Mapping (added via migration)
    subaccount_id TEXT,                       -- Tradovate subaccount ID (numeric, from accounts table)
    subaccount_name TEXT,                     -- Human-readable account name
    is_demo INTEGER DEFAULT 1,               -- 0=live, 1=demo
    enabled_accounts TEXT,                    -- JSON: per-account settings override
    -- State
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (recorder_id) REFERENCES recorders(id),
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);
```

**Override chain:** Trader value > Recorder value > Default. NULL means "use recorder value."

**Important:** `subaccount_id` exists on BOTH `accounts` and `traders` tables. When querying for WebSocket connections, use `t.subaccount_id` from traders (the proven pattern in recorder_service.py line 229 prewarm query).

---

## TABLE: recorded_trades

Individual trade records. Used for position detection and signal tracking.

```sql
CREATE TABLE recorded_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id INTEGER NOT NULL,
    signal_id INTEGER,
    ticker TEXT,
    side TEXT,                                -- 'LONG' or 'SHORT'
    quantity INTEGER DEFAULT 1,
    entry_price REAL,
    exit_price REAL,
    tp_price REAL,
    sl_price REAL,
    pnl REAL,
    pnl_ticks REAL,
    max_favorable REAL DEFAULT 0,             -- MFE
    max_adverse REAL DEFAULT 0,               -- MAE
    status TEXT DEFAULT 'open',               -- 'open', 'closed', 'cancelled'
    exit_reason TEXT,
    tp_order_id TEXT,                         -- !! SHARED across ALL accounts !!
    entry_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    exit_time DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recorder_id) REFERENCES recorders(id) ON DELETE CASCADE
);
CREATE INDEX idx_trades_recorder ON recorded_trades(recorder_id);
CREATE INDEX idx_trades_status ON recorded_trades(status);
```

**CRITICAL:** `tp_order_id` has NO `subaccount_id` column. For multi-account recorders, the last account to write "wins." DCA code must query the BROKER directly, not this table (Rule 5).

**Stale records warning (Rule 14):** Signal tracking can leave stale `status='open'` records if DCA is off. These pollute position detection. When DCA is off + same direction, old record must be closed before opening new one.

---

## TABLE: recorder_positions

Aggregated position tracking (combines multiple DCA entries).

```sql
CREATE TABLE recorder_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    side TEXT NOT NULL,                       -- 'LONG' or 'SHORT'
    total_quantity INTEGER DEFAULT 0,
    avg_entry_price REAL,
    entries TEXT,                              -- JSON array of individual entries
    current_price REAL,
    unrealized_pnl REAL DEFAULT 0,
    worst_unrealized_pnl REAL DEFAULT 0,
    best_unrealized_pnl REAL DEFAULT 0,
    exit_price REAL,
    realized_pnl REAL,
    status TEXT DEFAULT 'open',
    opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    closed_at DATETIME,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recorder_id) REFERENCES recorders(id) ON DELETE CASCADE
);
CREATE INDEX idx_positions_recorder ON recorder_positions(recorder_id);
CREATE INDEX idx_positions_status ON recorder_positions(status);
```

---

## TABLE: recorded_signals

Raw webhook signals received.

```sql
CREATE TABLE recorded_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recorder_id INTEGER NOT NULL,
    signal_number INTEGER,
    action TEXT,                               -- 'buy', 'sell', 'close', etc.
    ticker TEXT,
    price REAL,
    contracts INTEGER DEFAULT 1,
    position_size REAL,
    market_position TEXT,
    raw_payload TEXT,                          -- Full JSON from TradingView
    processed INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recorder_id) REFERENCES recorders(id) ON DELETE CASCADE
);
```

---

## TABLE: leader_accounts

Accounts designated as copy trading signal sources (Pro Copy Trader feature).

```sql
CREATE TABLE leader_accounts (
    id SERIAL PRIMARY KEY,                    -- (INTEGER PRIMARY KEY AUTOINCREMENT for SQLite)
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    subaccount_id VARCHAR(50) NOT NULL,
    label VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,           -- (INTEGER DEFAULT 1 for SQLite)
    auto_copy_enabled BOOLEAN DEFAULT FALSE,  -- (INTEGER DEFAULT 0 for SQLite)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, account_id, subaccount_id)
);
-- Index: idx_leader_accounts_user ON leader_accounts(user_id)
```

## TABLE: follower_accounts

Accounts that follow and copy trades from a leader account.

```sql
CREATE TABLE follower_accounts (
    id SERIAL PRIMARY KEY,
    leader_id INTEGER NOT NULL REFERENCES leader_accounts(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    subaccount_id VARCHAR(50) NOT NULL,
    label VARCHAR(100),
    is_enabled BOOLEAN DEFAULT TRUE,
    multiplier REAL DEFAULT 1.0,              -- Position size multiplier for follower
    max_position_size INTEGER DEFAULT 0,      -- 0 = unlimited
    copy_tp BOOLEAN DEFAULT TRUE,             -- Copy take profit orders
    copy_sl BOOLEAN DEFAULT TRUE,             -- Copy stop loss orders
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(leader_id, account_id, subaccount_id)
);
-- Index: idx_follower_accounts_leader ON follower_accounts(leader_id)
```

## TABLE: copy_trade_log

Audit trail of all copy trade executions.

```sql
CREATE TABLE copy_trade_log (
    id SERIAL PRIMARY KEY,
    leader_id INTEGER NOT NULL REFERENCES leader_accounts(id),
    follower_id INTEGER NOT NULL REFERENCES follower_accounts(id),
    leader_order_id VARCHAR(100),
    follower_order_id VARCHAR(100),
    symbol VARCHAR(50) NOT NULL,
    side VARCHAR(10) NOT NULL,                -- 'Buy' or 'Sell'
    leader_quantity INTEGER NOT NULL,
    follower_quantity INTEGER NOT NULL,
    leader_price REAL,
    follower_price REAL,
    status VARCHAR(20) DEFAULT 'pending',     -- pending, filled, failed, cancelled
    error_message TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Index: idx_copy_trade_log_leader ON copy_trade_log(leader_id)
-- Index: idx_copy_trade_log_created ON copy_trade_log(created_at)
```

---

## MIGRATION PATTERN

New columns are added via try/except ALTER TABLE (idempotent):

```python
try:
    cursor.execute('ALTER TABLE recorders ADD COLUMN new_column TEXT DEFAULT "value"')
    logger.info("Added new_column to recorders")
except:
    pass  # Column already exists
```

**PostgreSQL vs SQLite string defaults:**
```python
if is_postgres:
    cursor.execute("ALTER TABLE t ADD COLUMN x TEXT DEFAULT 'value'")
else:
    cursor.execute('ALTER TABLE t ADD COLUMN x TEXT DEFAULT "value"')
```

---

## COMMON QUERIES

### Find open trades for a recorder
```python
placeholder = '%s' if is_postgres else '?'
cursor.execute(f"SELECT * FROM recorded_trades WHERE recorder_id = {placeholder} AND status = 'open'", (recorder_id,))
```

### Get trader settings with account info
```python
cursor.execute(f"""
    SELECT t.*, a.tradovate_token, a.subaccount_id, a.account_spec
    FROM traders t
    JOIN accounts a ON t.account_id = a.id
    WHERE t.recorder_id = {placeholder} AND t.enabled = {enabled_value}
""", (recorder_id,))
```

---

*Source: recorder_service.py CREATE TABLE statements + MEMORY.md*
