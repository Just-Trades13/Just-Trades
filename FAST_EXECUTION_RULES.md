# 🚨 CRITICAL: FAST TRADE EXECUTION (Jan 16, 2026)

## NEVER DO THESE THINGS:
- NEVER replace `execute_trade_fast()` with `execute_trade_simple()`
- NEVER add position checking BEFORE order placement
- NEVER add complex auth flows - use direct token from DB
- NEVER add position caching

## HOW IT WORKS:

The fast execution mirrors the manual copy trader for instant trades (~50ms vs 5-10 sec):

1. **`execute_trade_fast()`** in `ultra_simple_server.py` is THE execution path
2. **Direct token from DB** - no 4-level auth priority with retries
3. **Direct `place_order()` REST call** - simple like manual trader
4. **NO position check before order** - this was causing 5-10 sec delays!
5. **TP/SL placed AFTER order** with MODIFY (not cancel+replace)

## BROKER EXECUTION WORKER:

```python
# broker_execution_worker() calls execute_trade_fast(), NOT execute_trade_simple()
result = execute_trade_fast(
    recorder_id=recorder_id,
    action=action,
    ticker=ticker,
    quantity=quantity,
    tp_ticks=tp_ticks,
    sl_ticks=sl_ticks,
    risk_config=risk_config
)
```

## TP/SL HANDLING:

- Find existing TP/SL orders for symbol
- **MODIFY** existing orders (don't cancel+replace - causes orphans)
- Only create new if none exist
- Use **GTC** (Good Till Cancelled) for all TP/SL orders

## DIAGNOSTIC ENDPOINTS:

- `/api/execution-logs` - shows last 50 trades with timing (duration_ms)
- `/api/broker-execution/status` - shows queue stats
- `/api/websocket-status` - shows connection pool

## LOCATIONS:

- `ultra_simple_server.py` → `execute_trade_fast()`
- `ultra_simple_server.py` → `broker_execution_worker()` calls `execute_trade_fast`
- `ultra_simple_server.py` → `/api/execution-logs` endpoint
- `ultra_simple_server.py` → `log_execution()` function

## WHAT HAPPENS IF YOU BREAK THIS:

- Trades take 5-10 SECONDS instead of 50ms
- Manual trader is instant but webhook is slow
- Complex auth with retries adds massive delays
- Position checking before every trade adds 2-3 sec per account
- Users complain trades are "heavily delayed"

## HISTORY (Jan 16, 2026):

1. User reported webhook trades were 5-10 seconds delayed
2. Manual copy trader buttons were instant (~50ms)
3. Audit found `execute_trade_simple()` had too much overhead:
   - 4-level auth priority with 2-second retry sleeps
   - Position check via REST before every order
   - WebSocket pooling complexity
4. Created `execute_trade_fast()` to mirror manual trader
5. Result: 50ms trades instead of 5-10 seconds
