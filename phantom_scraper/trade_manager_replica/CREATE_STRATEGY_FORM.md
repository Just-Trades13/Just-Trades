# Create Strategy Form - Complete Field Extraction

**Date:** 2025-11-05  
**Source:** Live browser inspection of `/user/strat` page

## 📋 Form Fields Discovered

### Basic Information
1. **Strategy Name** - Text input
2. **Strategy Type** - Dropdown/Combobox (currently shows "Stock")
3. **Directional Strategy** - Dropdown (appears to be optional)

### Position Settings (Optional Section)
- **Initial Position Size** - Spinbutton (number input)
- **Add Position Size** - Spinbutton (number input)

### Stop Loss / Take Profit Settings (Optional Section)

#### Take Profit Target
- **TP Unit** - Dropdown/Combobox (e.g., "Ticks", "Percent", "Dollars")
- **Trim Unit** - Dropdown/Combobox
- **TP# 1 Value** - Spinbutton
- **Trim %** - Spinbutton
- **Add TP** button - Can add multiple TP levels

#### Stop Loss
- **Stop Loss Disabled** - Toggle/checkbox
- **Stop Loss Amount** - Spinbutton (disabled when stop loss is disabled)
- **SL Unit** - Dropdown/Combobox
- **SL Type** - Dropdown/Combobox

#### Averaging Down (Disabled Section)
- **Average Down Amount** - Spinbutton (value: 1)
- **Average Down Point** - Spinbutton (value: 0)

## 🔍 New API Endpoints Discovered

From the Create Strategy page network requests:

1. **`GET /api/strategies/?val=DirStrat`**
   - Purpose: Get strategies filtered by value (likely "Directional Strategy")
   - Query param: `val=DirStrat`

2. **`GET /api/trades/tickers/?strat=`**
   - Purpose: Get available tickers/symbols for a strategy
   - Query param: `strat=` (empty when creating new)

3. **`GET /api/trades/timeframes/?strat=`**
   - Purpose: Get available timeframes for a strategy
   - Query param: `strat=` (empty when creating new)

## 📝 Form Structure (From DOM)

The form appears to have:
- Strategy name input
- Strategy type selector (Stock, Futures, etc.)
- Optional sections that can be expanded:
  - Position Settings
  - Stop Loss / Take Profit Settings
  - Averaging Down (disabled)

## 🎯 Expected POST Endpoint

When the form is submitted, it likely calls:
- `POST /api/strategies/` (or similar)

**Need to capture:**
- Request body format
- Response format
- Required vs optional fields

## 🔄 Next Steps

1. Fill out the form with test data
2. Click submit button
3. Capture the POST request payload
4. Document the response format

