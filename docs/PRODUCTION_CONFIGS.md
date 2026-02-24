# Production Strategy Configs — Just Trades Platform

> **WARNING:** These settings are stored in the PostgreSQL database on Railway. If the database is lost, these configs are gone forever.
> **Last updated: Feb 24, 2026**

---

## How to Extract Current Configs

```bash
# Connect to production PostgreSQL
railway connect postgres

# Export all recorder configs
SELECT id, name, symbol, initial_position_size, add_position_size,
       tp_units, trim_units, tp_targets, sl_enabled, sl_amount, sl_units,
       sl_type, trail_trigger, trail_freq, avg_down_enabled,
       avg_down_amount, avg_down_point, avg_down_units,
       break_even_enabled, break_even_ticks, break_even_offset,
       add_delay, signal_cooldown, max_signals_per_session,
       max_daily_loss, time_filter_1_enabled, time_filter_1_start,
       time_filter_1_stop, auto_flat_after_cutoff, custom_ticker,
       inverse_strategy, recording_enabled
FROM recorders WHERE recording_enabled = TRUE ORDER BY name;

# Export all trader overrides
SELECT t.id, t.recorder_id, r.name as recorder_name, t.account_id,
       t.enabled, t.multiplier, t.initial_position_size, t.add_position_size,
       t.dca_enabled, t.tp_targets, t.sl_enabled, t.sl_amount, t.sl_type,
       t.trail_trigger, t.trail_freq, t.break_even_enabled,
       t.break_even_ticks, t.break_even_offset, t.max_daily_loss
FROM traders t JOIN recorders r ON t.recorder_id = r.id
WHERE t.enabled = TRUE ORDER BY r.name;
```

## Production Recorder Configs (Snapshot: Feb 21, 2026)

> **Run `/api/admin/export-configs` to get the latest values. This snapshot may be outdated.**

### JADNQ V.2 (ID: 71) — NQ E-mini Nasdaq
```
initial_position_size: 1    add_position_size: 0
tp_targets: [{"ticks": 200, "trim": 100}]   tp_units: Ticks   trim_units: Contracts
sl_enabled: true   sl_amount: 50   sl_type: Trail   trail_trigger: 0   trail_freq: 0
avg_down_enabled: false   break_even_enabled: false
time_filters: disabled   max_daily_loss: 0   auto_flat: false
Active traders: 7 (multipliers: 1x, 1x, 1x, 1x, 1x, 1x, 3x init/multi-TP)
```

### JADMNQ V.2 (ID: 70) — MNQ Micro Nasdaq
```
initial_position_size: 1    add_position_size: 0
tp_targets: [{"ticks": 200, "trim": 100}]   tp_units: Ticks   trim_units: Contracts
sl_enabled: true   sl_amount: 50   sl_type: Trail   trail_trigger: 0   trail_freq: 0
avg_down_enabled: false   break_even_enabled: false
time_filters: disabled   max_daily_loss: 0   auto_flat: false
Active traders: 3 (multipliers: 1x, 20x, 1x live)
NOTE: One live trader (id 1490) has time_filter_1 enabled: 9:30AM-3:00PM
```

### JADVIX Medium Risk V.2 (ID: 67) — DCA Strategy
```
initial_position_size: 1    add_position_size: 1
tp_targets: [{"ticks": 50, "trim": 100}]   tp_units: Ticks   trim_units: Contracts
sl_enabled: false   sl_amount: 0   sl_type: Fixed
avg_down_enabled: true   avg_down_amount: 0   avg_down_point: 0
break_even_enabled: false
time_filters: disabled   max_daily_loss: 0   auto_flat: false
Active traders: 4 (multipliers: 1x, 1x, 2.5x, 1x) — ALL have dca_enabled=true
```

### JADVIX HIGH RISK V.2 (ID: 68) — Aggressive DCA Strategy
```
initial_position_size: 1    add_position_size: 1
tp_targets: [{"ticks": 20, "trim": 100}]   tp_units: Ticks   trim_units: Contracts
sl_enabled: false   sl_amount: 0   sl_type: Fixed
avg_down_enabled: true   avg_down_amount: 0   avg_down_point: 0
break_even_enabled: false
time_filters: disabled   max_daily_loss: 0   auto_flat: false
Active traders: 2 (multipliers: 1x, 30x) — ALL have dca_enabled=true
```

### MGC-C1MIN (ID: 69) — Micro Gold 1-Min
```
initial_position_size: 1    add_position_size: 1
tp_targets: [{"ticks": 20, "trim": 100}]   tp_units: Ticks   trim_units: Contracts
sl_enabled: false   sl_amount: 0   sl_type: Fixed
avg_down_enabled: false   break_even_enabled: false
time_filters: disabled   max_daily_loss: 400   auto_flat: false
Active traders: 0
```

### Key Patterns Across All Strategies
- **JADVIX (DCA on)**: No SL, smaller TP (20-50 ticks), avg_down_enabled=true
- **JAD NQ/MNQ (DCA off)**: Trail SL 50 ticks, large TP (200 ticks), avg_down_enabled=false
- **MGC**: Micro Gold with $400 daily loss limit, no active traders currently
- **Multipliers in use**: 1x (most), 2.5x, 3x (multi-TP), 20x, 30x
- **trim: 100** = 100% of position on single TP (full close)

## Config Structure Reference

Each recorder has these settings (see `docs/DATABASE_SCHEMA.md` for full schema):

**Position Settings:**
- `initial_position_size` — Contracts for first entry (default: 2)
- `add_position_size` — Contracts for DCA adds (default: 2)

**TP Settings:**
- `tp_units` — `'Ticks'`, `'Points'`, or `'Percent'`
- `trim_units` — `'Contracts'` or `'Percent'` (Contracts mode MUST scale by multiplier — Rule 13)
- `tp_targets` — JSON array: `[{"ticks": 20, "trim": 1}, {"ticks": 50, "trim": 1}]`

**SL Settings:**
- `sl_enabled` — 0/1
- `sl_amount` — Distance in `sl_units`
- `sl_units` — `'Ticks'`, `'Points'`, or `'Percent'`
- `sl_type` — `'Fixed'` or `'Trailing'`
- `trail_trigger` — Ticks before trail activates
- `trail_freq` — Trail update frequency in ticks

**DCA Settings:**
- `avg_down_enabled` — 0/1 (maps to trader `dca_enabled` — Rule 24)
- `avg_down_amount` — Contracts per DCA add
- `avg_down_point` — Distance to trigger DCA
- `avg_down_units` — `'Ticks'` or `'Points'`

**Break-Even:**
- `break_even_enabled` — 0/1
- `break_even_ticks` — Ticks in profit to move SL to break-even
- `break_even_offset` — Offset from entry (usually 0)

**Filters:**
- `add_delay` — Seconds between DCA entries (default: 1)
- `signal_cooldown` — Seconds between signals (default: 0)
- `max_signals_per_session` — 0 = unlimited
- `max_daily_loss` — Dollar amount, 0 = disabled
- `time_filter_1_start/end/enabled` — Trading hours window 1
- `time_filter_2_start/end/enabled` — Trading hours window 2
- `auto_flat_after_cutoff` — Flatten position after time window

**Trader-Level Overrides:**
All settings above can be overridden per trader. NULL = use recorder value. The `multiplier` field (default 1.0) scales ALL quantities for that account.

### JADVIX Startup Auto-Fix

**Location:** `ultra_simple_server.py` lines ~5651 and ~9068

On every deploy, automatically sets `dca_enabled=TRUE` on all traders linked to recorders with "JADVIX" in the name. This is a business requirement — all JADVIX strategies require DCA enabled for all users.

**NEVER remove this auto-fix.** It prevents the DCA field name mismatch (Rule 24) from disabling DCA on new traders.

---

*Source: CLAUDE.md "PRODUCTION STRATEGY CONFIG SNAPSHOT" section*
