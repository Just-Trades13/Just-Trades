# Just Trades — Developer Cheat Sheet

> **Quick reference for common operations. Read the full doc when in doubt.**
> **Last updated**: Feb 18, 2026

---

## BEFORE EVERY CODE CHANGE

```
1. STATE what you're changing and why
2. READ the full function first (not from memory)
3. CHECK if it's a Sacred File → get approval
4. SHOW the exact diff before editing
5. ONE change only → commit → test → next
6. VERIFY: python3 -c "import py_compile; py_compile.compile('file.py', doraise=True)"
```

---

## SACRED FILES — NEVER EDIT WITHOUT APPROVAL

| File | What |
|------|------|
| `recorder_service.py` | Trading engine, brackets, TP/SL, DCA |
| `ultra_simple_server.py` | Flask server, webhook pipeline, broker workers |
| `tradovate_integration.py` | Tradovate REST API, bracket builder |

---

## SQL — ALWAYS DUAL-DATABASE SAFE

```python
is_postgres = is_using_postgres()
placeholder = '%s' if is_postgres else '?'
enabled_value = 'TRUE' if is_postgres else '1'

cursor.execute(f'SELECT * FROM t WHERE id = {placeholder}', (value,))
```

**NEVER** hardcode `?` — it silently fails on PostgreSQL.

---

## ADDING A NEW SETTING TO A RECORDER

1. **Add column** (migration in `recorder_service.py` init):
```python
try:
    if is_postgres:
        cursor.execute("ALTER TABLE recorders ADD COLUMN new_setting TEXT DEFAULT 'value'")
    else:
        cursor.execute('ALTER TABLE recorders ADD COLUMN new_setting TEXT DEFAULT "value"')
except:
    pass
```

2. **Add to trader overrides** (if per-account):
```python
try:
    if is_postgres:
        cursor.execute("ALTER TABLE traders ADD COLUMN new_setting TEXT")
    else:
        cursor.execute('ALTER TABLE traders ADD COLUMN new_setting TEXT')
except:
    pass
```

3. **Add to `enabled_accounts` dict** (~line 1138-1182 in `recorder_service.py`):
```python
account_settings['new_setting'] = trader.get('new_setting') or recorder.get('new_setting', 'default')
```

4. **Add to UI** (template + API endpoint)

5. **Test**: Real signal with the new setting active

---

## ADDING A NEW API ENDPOINT

1. Add route to `ultra_simple_server.py`:
```python
@app.route('/api/new-endpoint', methods=['GET'])
@login_required
def new_endpoint():
    # ...
    return jsonify(result)
```

2. If it receives external POSTs (webhooks), add to CSRF exempt:
```python
_CSRF_EXEMPT_PREFIXES = ['/webhook/', '/webhooks/', '/oauth/', '/api/new-prefix/']
```

3. If template JS calls it, verify `fetch()` URL matches `@app.route()`.

---

## ADDING A NEW BROKER

See existing integrations:
- `tradovate_integration.py` — OAuth + REST (primary)
- `projectx_integration.py` — API Key + REST
- `webull_integration.py` — App Key/Secret + HMAC

**Pattern:**
1. Create `newbroker_integration.py` with:
   - `login()` / `authenticate()`
   - `place_market_order()`
   - `place_bracket_order()` (if native brackets supported)
   - `cancel_order()`
   - `get_positions()`
   - `get_orders()`
2. Add broker option to `accounts` table (`broker TEXT`)
3. Add `do_trade_for_newbroker()` function in `recorder_service.py`
4. Route to it from `execute_trade_simple()` based on `broker` field
5. **Do NOT modify existing broker code paths**

---

## BRACKET ORDER QUICK REFERENCE

### Tradovate (REST — `orderStrategy/startOrderStrategy`)
```python
# Single TP + SL
place_bracket_order(session, account_id, symbol, action, quantity,
    tp_ticks=20, sl_ticks=10)

# Multi-TP + trailing SL
place_bracket_order(session, account_id, symbol, action, quantity,
    multi_brackets=[
        {"ticks": 20, "trim": 5},
        {"ticks": 50, "trim": 5},
        {"ticks": 100, "trim": 5}
    ],
    sl_ticks=20, use_trailing=True, trail_trigger=10, trail_freq=5)
```

- TP/SL values in **POINTS** (not ticks) — multiply by tick_size
- Direction-signed: Buy TP = positive, Buy SL = negative
- `params` must be **stringified JSON** inside the payload

### ProjectX (REST — `Order/place`)
```python
create_market_order_with_brackets(api_key, account_id, contract_id,
    side=0, quantity=1, take_profit_ticks=20, stop_loss_ticks=10)
```

- Sides: 0=Buy, 1=Sell (integers)
- Order types: 1=Limit, 2=Market, 3=StopLimit, 4=Stop, 5=TrailingStop
- TP sign: Buy=+, Sell=-; SL sign: Buy=-, Sell=+; Trailing=unsigned

### Webull
- **No native brackets** — place entry, then separate TP and SL orders

---

## TICK SIZES (Futures)

| Symbol | Tick Size | $ per Tick |
|--------|-----------|-----------|
| NQ (E-mini Nasdaq) | 0.25 | $5.00 |
| ES (E-mini S&P) | 0.25 | $12.50 |
| MNQ (Micro Nasdaq) | 0.25 | $0.50 |
| MES (Micro S&P) | 0.25 | $1.25 |
| GC (Gold) | **0.10** | $10.00 |
| MGC (Micro Gold) | **0.10** | $1.00 |
| CL (Crude Oil) | **0.01** | $10.00 |
| MCL (Micro Crude) | **0.01** | $1.00 |
| SI (Silver) | **0.005** | $25.00 |
| HG (Copper) | **0.0005** | $12.50 |
| NG (Natural Gas) | **0.001** | $10.00 |
| YM (Dow Mini) | **1.0** | $5.00 |
| RTY (Russell 2000) | **0.10** | $5.00 |
| ZB (30Y Bond) | 1/32 (0.03125) | $31.25 |
| ZN (10Y Note) | 1/64 (0.015625) | $15.625 |

**Price rounding (ALWAYS):**
```python
price = round(round(price / tick_size) * tick_size, 10)
```

---

## COMMON ACTION VALUES (TradingView Webhooks)

| Incoming | Meaning | Our Handling |
|----------|---------|-------------|
| `buy` | Enter long | Bracket order (first) or REST market + TP (DCA) |
| `sell` | Enter short | Same as buy, opposite direction |
| `closelong` | Close long | Market sell + cancel resting orders |
| `closeshort` | Close short | Market buy + cancel resting orders |
| `close` | Close any | Flatten position |

---

## DCA BEHAVIOR

| DCA Enabled | Signal | What Happens |
|-------------|--------|-------------|
| OFF | Same direction | **Fresh bracket** (ignore position state — Rule 12) |
| OFF | Opposite | Close position, fresh bracket |
| ON | Same direction | REST market order + cancel old TP + new TP at weighted avg |
| ON | Opposite | Close position + new bracket |

---

## RECOVERY — FAST ROLLBACK

```bash
# Current stable
git reset --hard WORKING_FEB18_2026_DCA_SKIP_STABLE && git push -f origin main

# Check production after deploy (~90s)
curl -s "https://justtrades-production.up.railway.app/api/broker-execution/status"
```

---

## DEBUGGING CHECKLIST

### Trade Not Executing
1. Check webhook received: `/api/raw-webhooks?limit=10`
2. Check broker queue: `/api/broker-execution/status`
3. Check failures: `/api/broker-execution/failures?limit=20`
4. Check trader enabled: `SELECT enabled FROM traders WHERE recorder_id = X`
5. Check account token valid: Try a manual broker API call

### Wrong Position Size
1. Is multiplier set on trader? (`SELECT multiplier FROM traders`)
2. Is DCA off but position state stale? (Rule 12)
3. Is `initial_position_size` NULL? (Falls back to recorder default — Rule 19)
4. Is `trim_units='Contracts'`? Check multiplier scaling (Rule 13)

### TP/SL Not Placing
1. Price rounding? (Must be on tick boundaries — Rule 3)
2. Tick size correct? (2-letter symbols like GC need special handling — Rule 15)
3. Cross-account TP ID? (Don't trust DB, query broker — Rule 5)
4. Rate limit hit? (Per token, not per account — Rule 16)

### Webhook Not Arriving
1. TradingView alert still active? (Auto-disables at 15/3min)
2. CSRF blocking? Check `/webhooks/` in exempt list (Rule 23)
3. SSL cert valid? TradingView validates certs
4. Correct port? Only 80 and 443

---

## KEY ARCHITECTURE

```
TradingView → POST /webhook/{token}
  → 10 webhook workers (parse, validate, queue)
  → broker_execution_queue
  → 10 broker workers (parallel)
  → execute_trade_simple() → do_trade_for_account() per account
  → REST API → Broker → Order filled
```

**Non-negotiable:**
- Paper trades = daemon threads (NEVER synchronous)
- Signal tracking = daemon threads (NEVER synchronous)
- All Tradovate orders = REST (NEVER WebSocket)
- DCA = Cancel + Replace (NEVER modify)

---

## FILE LOCATIONS

| What | File | ~Line |
|------|------|-------|
| Webhook handler | `ultra_simple_server.py` | ~16500 |
| Broker worker | `ultra_simple_server.py` | ~14500 |
| risk_config builder | `ultra_simple_server.py` | ~16829 |
| Trade execution | `recorder_service.py` | ~850+ |
| Bracket builder | `recorder_service.py` | ~2089 |
| Tradovate REST orders | `tradovate_integration.py` | ~1840 |
| ProjectX orders | `projectx_integration.py` | ~1066 |
| Tick size dict | `tradovate_integration.py` | ~1875 |
| enabled_accounts | `recorder_service.py` | ~1138 |
| DB migrations | `recorder_service.py` | ~2869 |
| CSRF exempt list | `ultra_simple_server.py` | search `_CSRF_EXEMPT_PREFIXES` |

---

*Quick ref only. For details, see the full docs in `/docs/` and CLAUDE.md rules.*
