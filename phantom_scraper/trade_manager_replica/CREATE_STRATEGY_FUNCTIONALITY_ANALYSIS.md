# Create/Edit Strategy Functionality Analysis

## Extracted Data Summary

**File**: `trade_manager_functionality__user_at_strat_1762407137327.json`  
**Page**: `/user/at/strat` (Create/Edit Strategy - Trader)  
**Timestamp**: 2025-11-06T05:32:09.877Z

**Style Extraction File**: `trade_manager_extraction__user_at_strat_1762407052878.json`  
**Style Extraction Timestamp**: 2025-11-06T05:30:43.626Z

## ✅ What Was Captured

### 1. Interactive Elements

**Primary Actions:**
- **Create/Update Button**: `.create-update-btn` (class: `btn btn-info disabled`)
  - Currently disabled (form validation required)
  - Click handler: React synthetic event (`function Zn(){}`)
  - Text: "Create Trader"
  - Purpose: Submit form to create or update strategy

**Form Fields:**
- **Strategy Name Input**: `#strategyName` (React Select component)
  - Placeholder: "Enter strategy name"
  - Validation: Required field
  - Click handler: React synthetic event

- **Strategy Type Select**: `#strategyType` (React Select component)
  - Options: Stock, Futures, Options
  - Click handler: React synthetic event

**Accordion Sections (Expandable):**
- **Positional Settings**: `.text-info.btn.btn-link` with text "➕ Positional Settings (Optional)"
  - Collapsible section
  - Click handler: React synthetic event
  - Contains: Initial Position Size, Add Position Size inputs

- **Stop Loss / Take Profit Settings**: `.text-info.btn.btn-link` with text "➕ Stop Loss / Take Profit Settings (Optional)"
  - Collapsible section
  - Click handler: React synthetic event
  - Contains: TP Units, Trim Units, Take Profit Targets
  - **Add TP Button**: `.tp-add-btn` (class: `btn btn-secondary btn-sm`)
    - Background: `rgb(40, 199, 111)` (green)
    - Click handler: React synthetic event

- **Filter Settings**: `.text-info.btn.btn-link` with text "➕ Filter Settings (Optional)"
  - Collapsible section
  - Click handler: React synthetic event
  - Contains: Ticker, Timeframe, Delay, Max Cons, Premium Filter, Directional Strategy filters

- **Miscellaneous Settings**: `.text-info.btn.btn-link` with text "➕ Miscellaneous Settings (Optional)"
  - Collapsible section
  - Click handler: React synthetic event
  - Contains: Nickname, Description, Discord Channel inputs

**Account Routing Table:**
- **Account Table**: `.account-table` (class: `account-settings`)
  - Virtual scrolling list (`.account-virtuoso`)
  - Multiple account rows (`.account-row`)
  - Each row contains:
    - Account name/selector
    - Enable toggle switch
    - Max Cons input (`.account-input`)
    - Custom Ticker input (`.account-input`)
    - Multiplier input (`.account-input`)
  - Input fields: Multiple `.account-input` elements with click handlers
  - Background: `rgb(30, 30, 47)`
  - Border radius: `8px`

**Form Inputs:**
- Multiple `.account-input` fields throughout the form
- React Select components (`#react-select-2-input`, `#react-select-3-input`, etc.)
- Time picker components (`.react-time-picker`)
- Standard form controls (`.form-control`)

### 2. Event Listeners

**React Synthetic Events:**
- Click handlers on all interactive elements (`function Zn(){}`)
- Input change handlers on form fields
- Keyboard event handlers (Escape key for tooltips/walkthroughs)

**Form Validation:**
- Invalid event listeners on form inputs
- Validation feedback elements (`.invalid-feedback`)

**Navigation:**
- Standard navigation event listeners (sidebar, navbar, etc.)

### 3. Component Structure

**Page Header:**
- **Title**: "Create New Trader" (class: `mb-1`)
  - Font size: `32px`
  - Font weight: `600`
  - Color: `rgb(255, 255, 255)`
  - Badge: "TRADER" badge (orange: `rgb(255, 141, 114)`)

**Card Sections:**
- **Account Routing Card**: `.mb-3.card`
  - Background: `rgb(39, 41, 61)`
  - Border radius: `4.5712px`
  - Box shadow: `rgba(0, 0, 0, 0.1) 0px 1px 20px 0px`
  - Padding: `15px` (via `.card-body`)

- **Positional Settings Card**: `.mb-3.accordion-positional.card`
  - Same styling as Account Routing Card
  - Collapsible accordion

- **SL/TP Settings Card**: `.mb-3.accordion-sltp.card`
  - Same styling as Account Routing Card
  - Collapsible accordion

- **Filter Settings Card**: `.mb-3.accordion-filter.card`
  - Same styling as Account Routing Card
  - Collapsible accordion

- **Miscellaneous Settings Card**: `.mb-3.accordion-misc.card`
  - Same styling as Account Routing Card
  - Collapsible accordion

**Validation Error Box:**
- `.validation-error-box`
  - Background: `rgb(68, 34, 52)`
  - Color: `rgb(255, 226, 230)`
  - Border radius: `8px`
  - Padding: `16px 20px`
  - Contains error header and error list

### 4. Missing: API Calls

**Same pattern as previous pages** - no API calls captured because:
- Script ran after page load (API calls happened before interceptors were set up)
- Page is mostly form-based (API calls happen on submit)

**Expected API Calls:**
- **GET** `/api/strategies/{id}/` - Load strategy for editing
- **POST** `/api/strategies/create/` - Create new strategy
- **PUT** `/api/strategies/{id}/update/` - Update existing strategy
- **GET** `/api/accounts/get-all-at-accounts/` - Load accounts for routing table
- **GET** `/api/trades/tickers/` - Load available tickers
- **GET** `/api/trades/timeframes/` - Load available timeframes
- **POST** `/api/strategies/validate/` - Validate strategy configuration (before submit)

### 5. Storage Data

**LocalStorage:**
- Similar auth structure as other pages
- User preferences: `lastTicker`, `lastStrategy`

**SessionStorage:**
- Auth data without sessionId

**Cookies:**
- CSRF token

## 📋 Key Features Identified

### 1. Form Validation
- Real-time validation on form fields
- Error display box (`.validation-error-box`) shows validation errors
- Submit button disabled until form is valid
- Required field indicators

### 2. Accordion Sections
- Collapsible sections for optional settings
- Visual indicators (➕) for expandable sections
- Help links in each section

### 3. Account Routing Table
- Virtual scrolling for performance (react-virtuoso)
- Multiple account configuration per strategy
- Enable/disable toggles per account
- Custom settings per account (Max Cons, Ticker, Multiplier)

### 4. Complex Form Structure
- Strategy name (React Select for search/autocomplete)
- Strategy type selection
- Account routing configuration
- Positional settings (optional)
- SL/TP settings (optional, supports multiple TP targets)
- Filter settings (optional)
- Miscellaneous settings (optional)

### 5. React Select Integration
- Multiple React Select components for dropdowns
- Custom styling for dark theme
- Search/autocomplete functionality

## 🎨 Style Extraction Highlights

### Key Colors:
- **Primary Button**: `rgb(29, 140, 248)` (info blue)
- **Success Button**: `rgb(40, 199, 111)` (green for Add TP)
- **Danger Button**: `rgb(253, 93, 147)` (pink/red)
- **Card Background**: `rgb(39, 41, 61)`
- **Account Table Background**: `rgb(30, 30, 47)`
- **Input Background**: `rgb(42, 46, 60)` or `rgba(0, 0, 0, 0)`
- **Input Border**: `rgb(43, 53, 83)` or `rgb(68, 68, 68)`

### Typography:
- **Header**: `32px`, `600` weight, Poppins font
- **Body Text**: `14px`, `400` weight, Poppins font
- **Labels**: `12px` or `13.6px`, `400-600` weight
- **Input Text**: `12px`, `400` weight

### Spacing:
- **Card Padding**: `15px`
- **Section Margin**: `30px 0px 16px`
- **Input Padding**: `10px 18px` or `8px 11.2px`
- **Button Padding**: `11px 40px` (primary) or `5px 15px` (small)

### Border Radius:
- **Cards**: `4.5712px`
- **Buttons**: `6.856px` (primary) or `4.5712px` (small)
- **Inputs**: `6.856px` or `6px` or `8px`
- **Account Table**: `8px`

### Shadows:
- **Cards**: `rgba(0, 0, 0, 0.1) 0px 1px 20px 0px`
- **Filter/Misc Settings**: `rgba(0, 0, 0, 0.3) 0px 0px 10px 0px`

## 🔧 Implementation Notes

### Current Component Status:
- Basic CreateStrategy component exists (`CreateStrategy.jsx`)
- Simplified form structure (missing many features)
- Missing: Account routing table, accordion sections, complex validation

### Required Updates:
1. **Add Account Routing Table**
   - Virtual scrolling list component
   - Enable/disable toggles per account
   - Input fields for Max Cons, Custom Ticker, Multiplier

2. **Add Accordion Sections**
   - Positional Settings (optional)
   - SL/TP Settings (optional, with multiple TP targets)
   - Filter Settings (optional)
   - Miscellaneous Settings (optional)

3. **Enhance Form Validation**
   - Real-time validation
   - Error display box
   - Disable submit until valid

4. **Update Styling**
   - Apply extracted styles to match exact visual appearance
   - React Select custom styling for dark theme
   - Time picker styling

5. **Add API Integration**
   - Load accounts for routing table
   - Load strategy data for editing
   - Submit form with all configuration data

## 📝 Next Steps

1. **Update CreateStrategy Component**
   - Add accordion sections
   - Add account routing table
   - Implement form validation
   - Add error handling

2. **Apply Extracted Styles**
   - Update `CreateStrategy.css` with extracted styles
   - Match colors, spacing, typography exactly

3. **Implement API Calls**
   - Add endpoints for strategy creation/update
   - Add endpoints for loading accounts, tickers, timeframes

4. **Test Functionality**
   - Form validation
   - Account routing configuration
   - Accordion expand/collapse
   - Form submission

## 🔗 Related Files

- `frontend/src/pages/CreateStrategy.jsx` - Current component (needs major updates)
- `frontend/src/pages/CreateStrategy.css` - Styles (needs updates)
- `frontend/src/services/api.js` - API service (may need new endpoints)

