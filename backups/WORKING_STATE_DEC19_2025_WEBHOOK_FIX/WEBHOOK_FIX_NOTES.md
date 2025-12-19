# Dec 19, 2025 (Evening) - Multi-Account Webhook Trading Fix

## Session Summary

This session fixed critical issues preventing multi-account trading via webhooks on Railway (PostgreSQL).

---

## Problem 1: Only One Account Getting Trades

**Symptom:** Webhooks showed `accounts_traded: 1` when multiple traders were subscribed.

**Root Cause:** `recorder_service.py` was using SQLite `?` placeholder in the trader query, which fails silently on PostgreSQL.

**Fix Location:** `recorder_service.py` lines 657 and 692

```python
# Line 657 - Main trader query
placeholder = '%s' if is_postgres else '?'
cursor.execute(f'''
    SELECT t.id, t.enabled_accounts, t.subaccount_id, t.subaccount_name, t.is_demo,
           a.tradovate_token, a.username, a.password, a.id as account_id
    FROM traders t
    JOIN accounts a ON t.account_id = a.id
    WHERE t.recorder_id = {placeholder} AND t.enabled = {'true' if is_postgres else '1'}
''', (recorder_id,))

# Line 692 - Account credentials lookup
cursor.execute(f'''
    SELECT tradovate_token, tradovate_refresh_token, md_access_token, token_expires_at, environment
    FROM accounts WHERE id = {placeholder}
''', (account_row['account_id'],))
```

---

## Problem 2: JADNQ Webhooks Not Parsing

**Symptom:** JADNQ signals received but no trades executed.

**Root Cause:** Pine Script was sending text format, not JSON.

**Correct Format:**
```json
{"action": "buy", "ticker": "MNQ1!", "price": 21800, "position_size": "1", "market_position": "long"}
```

**Pine Script Fix:**
```pine
message='{"action": "{{strategy.order.action}}", "ticker": "{{ticker}}", "price": {{close}}, "position_size": "{{strategy.position_size}}", "market_position": "{{strategy.market_position}}"}'
```

---

## Problem 3: Orphaned Positions Can't Be Closed

**Solution:** Use `/api/manual-trade` endpoint:

```bash
curl -X POST "https://justtrades-production.up.railway.app/api/manual-trade" \
  -H "Content-Type: application/json" \
  -d '{"account_subaccount": "10:35752793", "symbol": "NQH6", "side": "Close", "quantity": 1}'
```

---

## Current Active Recorders

| ID | Name | Webhook Token |
|----|------|---------------|
| 15 | JADVIX | pP-ObgdipXfk-zLvM4V_Hg |
| 18 | JADNQ | xG9xbK-Z9m2sQA9LOKTU-g |

---

## Emergency Close Commands

```bash
# Close all MNQ/NQ on all recorders
curl -X POST "https://justtrades-production.up.railway.app/webhook/pP-ObgdipXfk-zLvM4V_Hg" -H "Content-Type: application/json" -d '{"action": "CLOSE", "ticker": "MNQ1!", "price": 21800}'
curl -X POST "https://justtrades-production.up.railway.app/webhook/xG9xbK-Z9m2sQA9LOKTU-g" -H "Content-Type: application/json" -d '{"action": "CLOSE", "ticker": "MNQ1!", "price": 21800}'
```

---

*Session completed: Dec 19, 2025*
