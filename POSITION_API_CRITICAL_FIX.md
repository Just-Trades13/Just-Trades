# 🚨🚨🚨 CRITICAL FIX: POSITION API ENDPOINT ROUTING 🚨🚨🚨

**Date:** December 16, 2025  
**Status:** ✅ FIXED AND WORKING  
**Git Tag:** `WORKING_DEC16_2025_POSITION_API_FIX`  
**Backup:** `backups/WORKING_STATE_DEC16_2025_POSITION_API_FIX/`

---

## THE PROBLEM

`get_positions()` was returning **0 positions** even when the broker had open positions.

This caused:
- ❌ DCA not working (system thought no position to add to)
- ❌ Multiple TP orders (system didn't know about existing orders)
- ❌ TP prices wrong (couldn't get real average from broker)
- ❌ Database getting cleared ("drift detected" when comparing to broker's "0")

---

## THE ROOT CAUSE

**File:** `phantom_scraper/tradovate_integration.py`  
**Function:** `get_positions()` (~line 923-930)

The code was trying the **LIVE** API endpoint first, even for **DEMO** accounts:

```python
# ❌ BROKEN CODE:
live_url = "https://live.tradovateapi.com/v1"
demo_url = "https://demo.tradovateapi.com/v1"

# This tried LIVE first for demo accounts - WRONG!
urls_to_try = [live_url, demo_url] if "demo" in self.base_url else [self.base_url]
```

**Why this broke everything:**
- Demo positions **ONLY** exist on `demo.tradovateapi.com`
- Live positions **ONLY** exist on `live.tradovateapi.com`
- Querying live for demo → returns empty array (not an error, just no positions)
- System thought "broker says 0 positions" → cleared database → chaos

---

## THE FIX (ONE LINE)

```python
# ✅ FIXED CODE:
# CRITICAL: Use the CORRECT endpoint for the account type
# Demo positions ONLY exist on demo API, live positions ONLY exist on live API
# DO NOT try cross-API calls - they will return 0 positions
urls_to_try = [self.base_url]  # Use the configured endpoint only
```

**That's it.** Just use the endpoint that was configured for the account type.

---

## WHAT WORKS NOW

| Feature | Before Fix | After Fix |
|---------|------------|-----------|
| `get_positions()` | Returns 0 | Returns real positions |
| Broker avg price | Unknown (0) | Real avg from broker |
| TP calculation | Wrong or missing | 5 ticks from real avg |
| DCA TP management | Creates multiple orders | MODIFIES existing order |
| Database sync | Constantly clearing | Stable state |

---

## THE DCA TP MODIFICATION LOGIC

Now that we have real position data, the TP modification works:

### 1. New Trade Opens
```
Signal: BUY MNQ
→ Execute market order
→ Get fill price from broker
→ Calculate TP = fill_price + (5 × 0.25) = fill_price + 1.25
→ Place TP limit order
→ Store tp_order_id in database
```

### 2. DCA Signal (Add to Position)
```
Signal: BUY MNQ (already have position)
→ Execute market order
→ Get broker position (qty=2, avg=25331.00) ← NOW WORKS!
→ Calculate new TP = 25331.00 + 1.25 = 25332.25
→ Fetch existing tp_order_id from database
→ MODIFY existing TP order (same ID, new price + qty)
→ ONE order on screen, updated price and quantity
```

### Key Functions
- `ensure_single_tp_limit()` - Modifies existing or places new TP
- `update_exit_brackets()` - Fetches tp_order_id and calls ensure_single_tp_limit
- `get_order_item()` - Gets full order details for modification

### Database Column
```sql
ALTER TABLE recorded_trades ADD COLUMN tp_order_id TEXT;
```

---

## ⛔ NEVER DO THESE THINGS

1. **NEVER** try live endpoint for demo account positions
2. **NEVER** try demo endpoint for live account positions
3. **NEVER** assume broker returns 0 is correct without checking endpoint
4. **NEVER** cancel and replace TP orders (modify instead)
5. **NEVER** remove the `urls_to_try = [self.base_url]` fix

---

## RECOVERY COMMANDS

If something breaks, restore from backup:

```bash
# Restore critical files
cp backups/WORKING_STATE_DEC16_2025_POSITION_API_FIX/tradovate_integration.py phantom_scraper/
cp backups/WORKING_STATE_DEC16_2025_POSITION_API_FIX/recorder_service.py ./

# Or restore from git tag
git checkout WORKING_DEC16_2025_POSITION_API_FIX -- phantom_scraper/tradovate_integration.py
git checkout WORKING_DEC16_2025_POSITION_API_FIX -- recorder_service.py

# Restart services
pkill -f "recorder_service"
python3 recorder_service.py > /tmp/recorder_service.log 2>&1 &
```

---

## VERIFICATION

To verify the fix is working:

```bash
# Check logs for real position data
tail -f /tmp/recorder_service.log | grep -E "positions|Found position|BROKER CONFIRMED"

# Should see:
# "Retrieved 3 positions for account 26029294"
# "Found position: MNQH6 qty=1 @ 25332.0"
# "BROKER CONFIRMED: Filled @ 25332.0"

# NOT:
# "Retrieved 0 positions"
# "DRIFT DETECTED: Broker shows 0"
```

---

---

## BROKER POSITION SYNC (Dec 16, 2025)

### Auto-Sync Every 60 Seconds

The system now automatically compares DB with broker positions every 60 seconds:

| Scenario | Action |
|----------|--------|
| DB shows position, broker shows 0 | Close trade in DB (`exit_reason = 'manual_broker_close'`) |
| DB qty > broker qty | Update DB qty (partial close detected) |
| DB avg ≠ broker avg | Update DB avg price |
| Broker has position, DB doesn't | Alert (orphan position) |

### Manual Sync Endpoints

```bash
# Force sync all positions immediately
curl -X POST http://localhost:8083/api/broker-sync

# Sync specific recorder
curl -X POST http://localhost:8083/api/recorders/123/sync-broker
```

### Use Case

1. Strategy is in a 5-contract DCA position
2. User sees volatility spike, manually closes on Tradovate
3. Within 60 seconds, system detects broker is flat
4. DB automatically marked as closed
5. No ghost trades, no drift, no DCA adding to closed position

---

*This fix took 2+ days to diagnose. The root cause was a single line of code trying the wrong API endpoint. PRESERVE THIS FIX.*
