# Contract Rollover Handling

## Overview

Futures contracts expire and roll over to the next month. For example:
- December 2025 (Z5) expires → March 2026 (H6) becomes front month
- March 2026 (H6) expires → June 2026 (M6) becomes front month

The system now **automatically handles rollovers** by dynamically detecting the front month contract from Tradovate API.

## How It Works

### Dynamic Contract Detection

1. **API Call**: When converting a TradingView symbol (e.g., `MNQ1!`), the system:
   - Fetches all contracts from Tradovate API (`/contract/list`)
   - Filters contracts matching the base symbol (e.g., `MNQ`)
   - Finds the contract with the nearest expiration date (front month)
   - Returns the front month contract symbol (e.g., `MNQZ5` → `MNQH6`)

2. **Caching**: Results are cached for 1 hour to avoid excessive API calls
   - Cache key: `{base_symbol}_{demo/live}`
   - Cache duration: 3600 seconds (1 hour)
   - Automatically refreshes when cache expires

3. **Fallback**: If API is unavailable, uses hardcoded map as fallback
   - Ensures system continues working even if API is down
   - Fallback map may need manual updates if contracts expire

### Example Flow

```
User/TradingView sends: "MNQ1!"
↓
System checks cache (if available, returns cached value)
↓
If not cached, calls Tradovate API: GET /contract/list
↓
Filters contracts: Finds all MNQ contracts
↓
Sorts by expiration date: Finds earliest (front month)
↓
Returns: "MNQH6" (or current front month)
↓
Caches result for 1 hour
```

## Benefits

✅ **Automatic Rollover**: No manual updates needed when contracts expire
✅ **Always Current**: Always uses the actual front month contract
✅ **Performance**: Caching reduces API calls
✅ **Reliability**: Fallback ensures system works even if API fails

## When Rollover Happens

Contracts typically roll over:
- **Before expiration**: Usually 1-2 weeks before contract expires
- **Liquidity**: When front month contract loses liquidity
- **Market convention**: Varies by contract (check Tradovate for specific dates)

## Cache Management

The cache automatically:
- **Refreshes**: Every 1 hour (3600 seconds)
- **Expires**: Old cache entries are replaced
- **Per-environment**: Separate cache for demo and live

To manually clear cache (if needed):
```python
# In ultra_simple_server.py
_contract_cache.clear()
_cache_timestamp.clear()
```

## Fallback Map

If API is unavailable, the system uses this hardcoded map:
```python
symbol_map = {
    'MNQ': 'MNQZ5',  # December 2025 (fallback)
    'MES': 'MESZ5',
    'ES': 'ESZ5',
    # ... etc
}
```

**Note**: This fallback map may need manual updates when contracts expire. The system will log a warning when using fallback.

## Testing Rollover

To test that rollover works:

1. **Check current front month**:
   ```python
   from ultra_simple_server import convert_tradingview_to_tradovate_symbol
   symbol = convert_tradingview_to_tradovate_symbol("MNQ1!", access_token=token, demo=True)
   print(symbol)  # Should show current front month (e.g., MNQH6)
   ```

2. **Verify API detection**:
   - Check server logs for "Dynamically detected front month contract"
   - Should see actual contract from Tradovate API

3. **Test after rollover**:
   - When contract expires, system should automatically detect new front month
   - No code changes needed

## Monitoring

Watch for these log messages:
- `✅ Dynamically detected front month contract: MNQ → MNQH6` - API detection working
- `Using fallback contract map: MNQ → MNQZ5` - Using fallback (API unavailable)
- `Using cached contract for MNQ: MNQH6` - Using cached value

## Future Enhancements

Potential improvements:
1. **Expiration date tracking**: Proactively roll over before expiration
2. **Multiple contract support**: Handle back month contracts (MNQ2!, MNQ3!)
3. **Rollover notifications**: Alert when contracts are about to expire
4. **Position migration**: Automatically roll over open positions

## Important Notes

1. **API Rate Limits**: Caching helps, but be mindful of Tradovate rate limits
2. **Contract Expiry**: System detects front month automatically, but positions may need manual rollover
3. **Symbol Format**: Always uses Tradovate format (MNQH6) for orders, stores both formats for tracking

