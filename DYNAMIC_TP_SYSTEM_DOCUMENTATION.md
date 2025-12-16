# Dynamic TP Order Movement System - Documentation

## 🎯 Overview

This system automatically moves Take Profit (TP) limit orders to maintain the correct distance from the position's average entry price, even when the position changes through DCA (Dollar Cost Averaging).

**Status: ✅ WORKING - DO NOT BREAK**

This has been a long-standing goal and is now functioning correctly. The system dynamically updates TP orders as positions grow.

---

## 🔑 Key Components

### 1. TP Reconciliation System (`_place_tp_order` method)

**Location:** `recorder_service_v2.py` ~line 3700-3900

**How it works:**
- When a position's average price changes (e.g., from DCA), the TP target is recalculated
- The system cancels the old TP limit order
- Places a new TP limit order at the updated price
- Ensures only ONE TP order exists per position at any time

**Key Logic:**
```python
# Recalculate TP price based on new average
if pos.side == "LONG":
    desired_tp_price = pos.avg_price + (strategy.tp_ticks * tick_size)
else:
    desired_tp_price = pos.avg_price - (strategy.tp_ticks * tick_size)

# Cancel all existing TP orders
# Place new TP order with updated price
```

### 2. TP Order Tracking (`_active_tp_orders`)

**Location:** `recorder_service_v2.py` ~line 2025

**Purpose:**
- Tracks active TP orders per position
- Prevents multiple TP orders from existing simultaneously
- Uses order tags for reconciliation with broker

**Structure:**
```python
self._active_tp_orders: Dict[str, Dict[str, Any]] = {
    position_key: {
        'order_id': str,
        'price': float,
        'qty': int,
        'tag': str,
        'timestamp': float
    }
}
```

### 3. TP Reconciliation After Position Changes

**Location:** `recorder_service_v2.py` ~line 3060-3066

**Trigger Points:**
- After broker fills (entry or DCA)
- When position average price changes
- Uses a short delay (0.3s) to allow position to update first

**Code:**
```python
if strategy and strategy.mode == StrategyMode.LIVE.value and strategy.tp_ticks:
    # Trigger TP reconciliation after a short delay
    threading.Timer(0.3, lambda: self._reconcile_tp_orders_after_position_change(pos, strategy)).start()
```

### 4. Quantity Safety Checks

**Location:** `recorder_service_v2.py` ~line 3850-3890

**Critical:** Uses entries sum as source of truth for quantity
- Prevents quantity mismatches
- Validates qty before placing TP orders
- Logs warnings if mismatches detected

**Code:**
```python
# SAFETY CHECK: Calculate actual qty from entries
entries_qty = sum(entry.get('qty', 0) for entry in pos.entries)
if entries_qty != pos.total_qty:
    logger.warning(f"⚠️ QUANTITY MISMATCH: pos.total_qty={pos.total_qty} but sum(entries)={entries_qty}")
    actual_qty = entries_qty  # Use entries sum as source of truth
else:
    actual_qty = pos.total_qty
```

---

## 🔄 Flow Diagram

```
1. Position Opens
   └─> TP order placed at: avg_price + (tp_ticks * tick_size)

2. DCA Adds to Position
   └─> Position avg_price recalculated
   └─> TP target recalculated: new_avg_price + (tp_ticks * tick_size)
   └─> Old TP order cancelled
   └─> New TP order placed at updated price
   └─> Quantity validated from entries sum

3. Position Changes
   └─> Broker fill received
   └─> Position updated
   └─> TP reconciliation triggered (0.3s delay)
   └─> TP order updated if needed
```

---

## 📋 Key Methods to Preserve

### `_place_tp_order(self, pos: V2Position, strategy: StrategyInstance)`
- **Location:** `recorder_service_v2.py` ~line 3700
- **Purpose:** Places/updates TP limit orders
- **Critical Features:**
  - Cancels existing TP orders first
  - Validates quantity from entries
  - Uses order tags for reconciliation
  - Prevents marketable orders

### `_reconcile_tp_orders_after_position_change(self, pos: V2Position, strategy: StrategyInstance)`
- **Location:** `recorder_service_v2.py` ~line 3700
- **Purpose:** Reconciles TP orders after position changes
- **Trigger:** Called after broker fills with 0.3s delay

### `_check_tp_marketability(self, tp_price: float, current_price: float, side: str, tick_size: float)`
- **Location:** `recorder_service_v2.py` ~line 3700
- **Purpose:** Prevents placing TP orders that would fill immediately
- **Returns:** (is_safe: bool, error_msg: str)

### Quantity Validation Logic
- **Location:** Multiple places in `recorder_service_v2.py`
- **Purpose:** Ensures TP order quantity matches actual position size
- **Key:** Always use `sum(entries)` as source of truth

---

## 🛡️ Safety Mechanisms

1. **Order Tagging System**
   - Each TP order has a unique tag: `JT:{account_id}:{symbol}:{strategy_id}:TP:{sequence}`
   - Allows reconciliation with broker
   - Prevents duplicate orders

2. **Sequence Counter**
   - Tracks TP order sequence per position
   - Ensures proper ordering
   - Location: `_tp_sequence_counter` dict

3. **Reconciliation Locks**
   - Prevents race conditions
   - Location: `_tp_reconciliation_locks` dict
   - Ensures only one reconciliation at a time per position

4. **Marketability Check**
   - Prevents placing TP orders that would fill instantly
   - Checks if TP price is too close to current market price
   - Skips placement if unsafe

---

## ⚠️ Critical Rules - DO NOT BREAK

1. **Always cancel old TP before placing new one**
   - Prevents multiple TP orders
   - Ensures only one TP per position

2. **Always use entries sum for quantity validation**
   - `pos.total_qty` can be wrong
   - `sum(entry.get('qty', 0) for entry in pos.entries)` is source of truth

3. **Always recalculate TP price from current avg_price**
   - TP should always be: `avg_price ± (tp_ticks * tick_size)`
   - Recalculate whenever avg_price changes

4. **Always use order tags for reconciliation**
   - Tags allow finding TP orders on broker
   - Format: `JT:{account_id}:{symbol}:{strategy_id}:TP:{sequence}`

5. **Always validate quantity before placing orders**
   - Check entries sum vs total_qty
   - Log warnings if mismatch
   - Use entries sum as source of truth

---

## 🔧 Refinement Opportunities

### Areas to Improve (Without Breaking Core Logic):

1. **Reconciliation Timing**
   - Current: 0.3s delay after fill
   - Could: Make configurable or adaptive based on market conditions

2. **Marketability Threshold**
   - Current: Fixed check
   - Could: Make threshold configurable per strategy

3. **Error Handling**
   - Current: Logs errors
   - Could: Add retry logic for failed cancellations/placements

4. **Performance**
   - Current: Queries broker for all orders
   - Could: Cache order state to reduce API calls

5. **Logging**
   - Current: Good logging exists
   - Could: Add metrics/telemetry for TP order updates

---

## 📝 Testing Checklist

When modifying this system, verify:

- [ ] TP order moves when DCA adds to position
- [ ] Only one TP order exists per position
- [ ] TP order quantity matches position size
- [ ] TP order price is correct distance from avg_price
- [ ] Old TP orders are cancelled before new ones placed
- [ ] System handles rapid DCA additions correctly
- [ ] System handles manual broker closes correctly
- [ ] Quantity validation catches mismatches

---

## 🚨 Breaking Changes to Avoid

**DO NOT:**
- Remove the cancellation of old TP orders before placing new ones
- Remove quantity validation from entries sum
- Remove order tagging system
- Remove marketability checks
- Change TP price calculation formula
- Remove reconciliation locks
- Remove sequence counter

**DO:**
- Add logging for debugging
- Improve error messages
- Add configuration options
- Optimize performance (without breaking logic)
- Add metrics/telemetry

---

## 📚 Related Code Locations

- **TP Order Placement:** `recorder_service_v2.py` ~line 3700-3900
- **TP Order Tracking:** `recorder_service_v2.py` ~line 2025
- **TP Reconciliation Trigger:** `recorder_service_v2.py` ~line 3060-3066
- **Quantity Validation:** `recorder_service_v2.py` ~line 3850-3890
- **Exit Order Quantity:** `recorder_service_v2.py` ~line 3380-3400
- **Position Drift Detection:** `recorder_service_v2.py` ~line 1767-1814

---

## 🎉 Success Criteria

This system is considered working when:
- ✅ TP orders automatically move when position avg_price changes
- ✅ Only one TP order exists per position
- ✅ TP order quantity always matches position size
- ✅ TP orders are placed at correct distance from avg_price
- ✅ System handles DCA additions smoothly
- ✅ No duplicate TP orders
- ✅ No quantity mismatches

**Current Status: ✅ ALL CRITERIA MET**

---

*Last Updated: December 12, 2025*
*Status: WORKING - Preserve Core Logic*

