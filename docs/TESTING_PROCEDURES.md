# End-to-End Testing Procedures — Just Trades Platform

> **Run these tests after ANY code change to sacred files.**
> **Minimum: one real webhook signal test before marking a change as "Working".**
> **Last updated: Feb 21, 2026**

---

## QUICK TEST REFERENCE

### Send a Test Signal (curl)

```bash
# Replace {WEBHOOK_TOKEN} with the recorder's webhook_token from the DB
# Replace ticker/action as needed

# BUY signal (enter long)
curl -X POST "https://justtrades.app/webhook/{WEBHOOK_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"action": "buy", "ticker": "NQH6", "price": 21500.00}'

# SELL signal (enter short)
curl -X POST "https://justtrades.app/webhook/{WEBHOOK_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"action": "sell", "ticker": "NQH6", "price": 21500.00}'

# CLOSE LONG signal
curl -X POST "https://justtrades.app/webhook/{WEBHOOK_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"action": "closelong", "ticker": "NQH6"}'

# CLOSE SHORT signal
curl -X POST "https://justtrades.app/webhook/{WEBHOOK_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"action": "closeshort", "ticker": "NQH6"}'

# FLAT / CLOSE ALL
curl -X POST "https://justtrades.app/webhook/{WEBHOOK_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"action": "close", "ticker": "NQH6"}'
```

### Find Webhook Tokens

```sql
-- Connect via: railway connect postgres
SELECT id, name, symbol, webhook_token, recording_enabled
FROM recorders WHERE recording_enabled = TRUE ORDER BY name;
```

---

## PRE-TEST CHECKLIST

Before sending any test signal:

- [ ] Verify the correct recorder is targeted (check webhook_token)
- [ ] Verify the recorder is enabled: `recording_enabled = TRUE`
- [ ] Verify at least one trader is linked and enabled: `SELECT * FROM traders WHERE recorder_id = X AND enabled = TRUE`
- [ ] Verify the trader's account has a valid broker token: `curl -s "https://justtrades.app/api/accounts/auth-status"`
- [ ] Confirm market hours (or disable time filters for testing)
- [ ] Check that broker execution workers are alive: `curl -s "https://justtrades.app/api/broker-execution/status"`

---

## TEST 1: FIRST ENTRY (BRACKET ORDER)

**Scenario:** No existing position, DCA on or off. Should place a bracket order (entry + TP + SL in one call).

### Steps

1. **Ensure flat position** on the test account:
   ```bash
   curl -s "https://justtrades.app/api/traders/{TRADER_ID}/broker-state"
   ```
   If position exists, close it first.

2. **Send BUY signal:**
   ```bash
   curl -X POST "https://justtrades.app/webhook/{TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"action": "buy", "ticker": "NQH6", "price": 21500.00}'
   ```

3. **Verify within 5 seconds:**
   ```bash
   # Check webhook was received
   curl -s "https://justtrades.app/api/raw-webhooks?limit=5"

   # Check execution status
   curl -s "https://justtrades.app/api/broker-execution/status"

   # Check for failures
   curl -s "https://justtrades.app/api/broker-execution/failures?limit=5"
   ```

### Expected Results

| Check | Expected |
|-------|----------|
| Webhook received | `raw-webhooks` shows the signal with correct action/ticker |
| Queue processed | `broker-execution/status` shows `queue_size: 0` |
| No failures | `broker-execution/failures` has no new entries |
| Position opened | Broker shows long position with correct quantity |
| TP placed | Broker shows limit order at correct price (entry + tp_ticks * tick_size) |
| SL placed | Broker shows stop order at correct price (entry - sl_ticks * tick_size) |
| TP on tick boundary | TP price is a multiple of tick_size (Rule 3) |
| SL on tick boundary | SL price is a multiple of tick_size (Rule 3) |
| Correct quantity | Position size = `initial_position_size * multiplier` |
| DB record created | `recorded_trades` has new row with `status='open'` |

---

## TEST 2: DCA ADD (SAME DIRECTION + DCA ON)

**Prerequisite:** Existing long position from Test 1. Recorder has `avg_down_enabled = TRUE`.

### Steps

1. **Send another BUY signal** (same direction as existing):
   ```bash
   curl -X POST "https://justtrades.app/webhook/{TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"action": "buy", "ticker": "NQH6", "price": 21480.00}'
   ```

2. **Verify within 10 seconds.**

### Expected Results

| Check | Expected |
|-------|----------|
| REST market order placed | NOT a bracket order (DCA uses separate market + TP) |
| Quantity = add_position_size * multiplier | Not initial_position_size |
| Old TP CANCELLED | Previous TP order removed from broker |
| New TP placed at weighted average | TP recalculated from broker's average entry |
| New TP on tick boundary | Price rounded per Rule 3 |
| DB updated | New `recorded_trades` row with DCA details |

---

## TEST 3: CLOSE SIGNAL

**Prerequisite:** Existing long position.

### Steps

1. **Send CLOSELONG signal:**
   ```bash
   curl -X POST "https://justtrades.app/webhook/{TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"action": "closelong", "ticker": "NQH6"}'
   ```

2. **Verify within 5 seconds.**

### Expected Results

| Check | Expected |
|-------|----------|
| Position closed | Broker shows flat (no position) |
| Resting orders cancelled | All TP and SL orders cancelled on broker |
| DB record closed | `recorded_trades` updated: `status='closed'`, `exit_reason` set |
| `recorder_positions` closed | Position record status = 'closed' |

---

## TEST 4: FLIP SIGNAL (LONG → SHORT)

**Prerequisite:** Existing long position.

### Steps

1. **Send SELL signal** (opposite direction):
   ```bash
   curl -X POST "https://justtrades.app/webhook/{TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{"action": "sell", "ticker": "NQH6", "price": 21450.00}'
   ```

2. **Verify within 10 seconds.**

### Expected Results

| Check | Expected |
|-------|----------|
| Long position closed | Old long position flattened |
| Old TP/SL cancelled | Resting orders from long cleaned up (flip close cleanup) |
| Short position opened | New short position via bracket order |
| New TP/SL placed | Short-direction TP and SL on broker |
| DB records | Old trade closed, new trade opened |

---

## TEST 5: SAME DIRECTION + DCA OFF (FRESH BRACKET)

**Prerequisite:** Existing position. Recorder has `avg_down_enabled = FALSE` / trader `dca_enabled = FALSE`.

### Steps

1. **Send same-direction signal.**

### Expected Results

| Check | Expected |
|-------|----------|
| **Fresh bracket order** | NOT a DCA add — treated as independent entry (Rule 12) |
| Uses initial_position_size | Not add_position_size |
| Independent TP/SL | New bracket with own TP/SL, not merged with existing |
| Old trade record closed | Previous `recorded_trades` row closed with `exit_reason='new_entry'` (Rule 14) |
| New trade record opened | Fresh `recorded_trades` row |

---

## TEST 6: MULTI-BRACKET TP LEGS

**Prerequisite:** Recorder with multiple TP targets, e.g. `tp_targets = [{"ticks": 20, "trim": 1}, {"ticks": 50, "trim": 1}, {"ticks": 100, "trim": 1}]`.

### Steps

1. **Send entry signal (flat start).**

### Expected Results

| Check | Expected |
|-------|----------|
| Single bracket order | One REST call creates everything |
| Multiple TP legs on broker | 3 separate TP limit orders at different prices |
| Each TP has correct trim qty | `trim * multiplier` for Contracts mode, `qty * (trim/100)` for Percent mode |
| All TPs on tick boundary | Every price is a multiple of tick_size |
| Total trim = total quantity | Sum of all leg quantities = position size |

---

## STRATEGY-SPECIFIC TEST CASES

### NQ / MNQ (Nasdaq)
- Tick size: 0.25, $ per tick: $5.00 (NQ) / $0.50 (MNQ)
- Symbol format: `NQH6`, `MNQH6`
- Root extraction: NQ→NQ (2 char), MNQ→MNQ (3 char) — both work correctly

### GC / MGC (Gold)
- Tick size: **0.10** (NOT 0.25 default)
- Symbol format: `GCJ6`, `MGCJ6`
- Root extraction: GC→GC (2 char — Rule 15 fix required), MGC→MGC (3 char)
- **Extra verification:** Confirm TP/SL prices are multiples of 0.10, NOT 0.25

### CL (Crude Oil)
- Tick size: **0.01**
- Root extraction: CL→CL (2 char — Rule 15 fix required)

---

## REGRESSION CHECKLIST

After ANY code change to sacred files, verify ALL of these still work:

- [ ] **Entry signal** produces bracket order with correct TP/SL
- [ ] **DCA signal** (when DCA on) uses REST market + cancel/replace TP
- [ ] **DCA-off signal** produces fresh bracket (Rule 12)
- [ ] **Close signal** flattens position and cancels resting orders
- [ ] **Flip signal** closes old + opens new in opposite direction
- [ ] **Multi-bracket** TP legs placed correctly with correct trim quantities
- [ ] **Trailing stop** activates and trails (if configured)
- [ ] **Break-even** moves SL to entry after configured ticks
- [ ] **Time filter** blocks signals outside trading hours
- [ ] **Max daily loss** disables trading when limit hit
- [ ] **Multiplier** scales all quantities correctly (Rule 13)
- [ ] **TP/SL prices** are on tick boundaries (Rule 3)
- [ ] **2-letter symbols** (GC, CL) use correct tick_size (Rule 15)
- [ ] **Webhook response** < 200ms (no background→sync conversion)
- [ ] **No failures** in `/api/broker-execution/failures`

---

## POST-TEST CLEANUP

After testing, clean up test positions and records:

```sql
-- Close any test positions on broker
-- (Use the platform UI or broker's own interface)

-- Clean test records from DB
UPDATE recorded_trades SET status = 'closed', exit_reason = 'test_cleanup'
WHERE recorder_id = {TEST_RECORDER_ID} AND status = 'open';

UPDATE recorder_positions SET status = 'closed'
WHERE recorder_id = {TEST_RECORDER_ID} AND status = 'open';
```

---

## SMOKE TEST SCRIPT (Quick Health Check)

Run this after any deploy to confirm basic system health:

```bash
#!/bin/bash
echo "=== Just Trades Smoke Test ==="
echo ""

echo "1. Health check..."
curl -sf "https://justtrades.app/health" | python3 -m json.tool || echo "FAIL: Service down!"

echo ""
echo "2. Broker workers..."
STATUS=$(curl -sf "https://justtrades.app/api/broker-execution/status")
echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Workers: {d.get(\"broker_execution\",{}).get(\"workers_alive\",\"?\")}/10, Queue: {d.get(\"broker_execution\",{}).get(\"queue_size\",\"?\")}')" 2>/dev/null || echo "FAIL: Can't reach broker status!"

echo ""
echo "3. TradingView WebSocket..."
curl -sf "https://justtrades.app/api/tradingview/status" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Connected: {d.get(\"websocket_connected\")}, JWT Valid: {d.get(\"jwt_token_valid\")}')" 2>/dev/null || echo "FAIL: Can't reach TV status!"

echo ""
echo "4. Recent failures..."
FAILS=$(curl -sf "https://justtrades.app/api/broker-execution/failures?limit=5")
echo "$FAILS" | python3 -c "import sys,json; d=json.load(sys.stdin); failures=d.get('failures',[]); print(f'Recent failures: {len(failures)}')" 2>/dev/null || echo "FAIL: Can't reach failures!"

echo ""
echo "=== Smoke Test Complete ==="
```

---

*Source: Production testing experience with Just Trades platform. See CLAUDE.md for rules referenced.*
