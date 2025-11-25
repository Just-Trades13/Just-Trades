# TradingView Symbol Conversion Guide

## Overview

TradingView uses continuous contract symbols (e.g., `MNQ1!`) while Tradovate requires actual contract symbols (e.g., `MNQZ5`). This guide explains how the system handles this conversion for both manual trading and automated TradingView alerts.

## Symbol Formats

### TradingView Format
- **Format**: `BASE1!` (continuous contract)
- **Examples**: `MNQ1!`, `MES1!`, `ES1!`, `NQ1!`
- **Meaning**: Front month continuous contract

### Tradovate Format
- **Format**: `BASEMONTHYEAR` (actual contract)
- **Examples**: `MNQZ5`, `MESZ5`, `ESZ5`, `NQZ5`
- **Meaning**: Specific contract with expiry (Z5 = December 2025)

## Conversion Function

**Location**: `ultra_simple_server.py` - `convert_tradingview_to_tradovate_symbol()`

**How it works**:
1. Checks if symbol is already in Tradovate format (has month code like Z5, H6)
2. Strips TradingView suffix (`1!`, `2!`, etc.)
3. Maps base symbol to front month contract
4. Falls back to `BASEZ5` if not in map

**Supported Symbols**:
- `MNQ` → `MNQZ5` (Micro E-mini Nasdaq)
- `MES` → `MESZ5` (Micro E-mini S&P 500)
- `ES` → `ESZ5` (E-mini S&P 500)
- `NQ` → `NQZ5` (E-mini Nasdaq)
- `YM` → `YMZ5` (E-mini Dow)
- `RTY` → `RTYZ5` (E-mini Russell 2000)
- `CL` → `CLZ5` (Crude Oil)
- `GC` → `GCZ5` (Gold)

## Current Implementation

### Manual Trader
✅ **Working**: 
- User selects `MNQ1!` from dropdown
- System converts to `MNQZ5` for order
- Stores BOTH symbols in database:
  - `original_symbol`: `MNQ1!` (TradingView format)
  - `tradovate_symbol`: `MNQZ5` (converted format)
  - `symbol`: `MNQZ5` (for backward compatibility)

### Position Tracking
✅ **Working**:
- Positions recorded with both symbol formats
- Matching for closing uses both formats
- Display can show either format

### TradingView Webhooks (Future)
⚠️ **Needs Implementation**:
- Webhook endpoints exist but may not use conversion
- Need to ensure all TradingView alerts go through conversion
- Need to store both formats for tracking

## How to Use for TradingView Alerts

### Step 1: Webhook Receives Alert
```json
{
  "symbol": "MNQ1!",
  "action": "buy",
  "quantity": 1
}
```

### Step 2: Convert Symbol
```python
from ultra_simple_server import convert_tradingview_to_tradovate_symbol

original_symbol = alert_data['symbol']  # "MNQ1!"
tradovate_symbol = convert_tradingview_to_tradovate_symbol(original_symbol)  # "MNQZ5"
```

### Step 3: Place Order
```python
order_data = {
    "symbol": tradovate_symbol,  # Use converted symbol
    "action": "Buy",
    "orderQty": 1
}
```

### Step 4: Record Position
```python
# Store BOTH formats
recorded_position = {
    "original_symbol": original_symbol,  # "MNQ1!" (for display/matching)
    "tradovate_symbol": tradovate_symbol,  # "MNQZ5" (for API calls)
    "symbol": tradovate_symbol  # Main symbol (for backward compatibility)
}
```

## Database Schema

The `recorded_positions` table stores:
- `symbol`: Converted Tradovate symbol (MNQZ5) - main field
- `original_symbol`: Original TradingView symbol (MNQ1!) - for display
- `tradovate_symbol`: Converted symbol (MNQZ5) - for API calls
- `contract_id`: Tradovate contract ID (if available)

## Display Considerations

When displaying positions to users:
- **Show original symbol** (`MNQ1!`) if user is familiar with TradingView
- **Show converted symbol** (`MNQZ5`) if user needs Tradovate contract info
- **Show both** for clarity: `MNQ1! (MNQZ5)`

## Matching Positions

When closing positions, the system tries multiple matching strategies:
1. **Exact match**: `MNQZ5` == `MNQZ5`
2. **Base match**: `MNQ` matches `MNQZ5`
3. **Contract ID match**: Match by Tradovate contract ID (future)

## Important Notes

1. **Contract Expiry**: The conversion uses front month contracts (Z5 = December 2025). These need to be updated as contracts expire.

2. **Symbol Map**: The `symbol_map` in `convert_tradingview_to_tradovate_symbol()` may need updates:
   - When contracts expire (Z5 → H6 → M6 → U6)
   - When adding new symbols

3. **Fallback**: If a symbol isn't in the map, it falls back to `BASEZ5`. This may not always be correct.

4. **Already Converted**: The function checks if a symbol is already in Tradovate format and returns it as-is.

## Future Enhancements

1. **Dynamic Contract Detection**: Instead of hardcoded Z5, detect the actual front month contract from Tradovate API
2. **Contract Expiry Tracking**: Automatically update contract codes as they expire
3. **Symbol Validation**: Verify converted symbols exist in Tradovate before placing orders
4. **Multi-Contract Support**: Handle back month contracts (MNQ2!, MNQ3!, etc.)

## Testing

To test symbol conversion:
```python
from ultra_simple_server import convert_tradingview_to_tradovate_symbol

# Test cases
assert convert_tradingview_to_tradovate_symbol("MNQ1!") == "MNQZ5"
assert convert_tradingview_to_tradovate_symbol("MES1!") == "MESZ5"
assert convert_tradingview_to_tradovate_symbol("MNQZ5") == "MNQZ5"  # Already converted
```

## Integration Checklist

When implementing TradingView webhook integration:

- [ ] Ensure webhook receives TradingView symbols (MNQ1!)
- [ ] Convert symbols before placing orders
- [ ] Store both original and converted symbols
- [ ] Display original symbol to user (familiar format)
- [ ] Use converted symbol for API calls
- [ ] Match positions using both formats
- [ ] Update contract codes as they expire
- [ ] Test with various TradingView symbols

