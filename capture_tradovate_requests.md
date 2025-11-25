# How to Capture Tradovate API Requests from Trade Manager

## Step-by-Step Guide

### 1. Open Trade Manager in Browser
- Go to https://trademanagergroup.com
- Log in to your account

### 2. Open Browser Developer Tools
- **Chrome/Edge**: Press `F12` or `Cmd+Option+I` (Mac) / `Ctrl+Shift+I` (Windows)
- **Safari**: Enable Developer menu first: Preferences → Advanced → "Show Develop menu"
  - Then press `Cmd+Option+I`

### 3. Go to Network Tab
- Click on the **Network** tab in Developer Tools
- Make sure it's recording (red circle should be active)

### 4. Filter for Tradovate API Calls
In the filter box at the top of the Network tab, type:
```
tradovateapi.com
```
This will show ONLY requests to Tradovate's API.

### 5. Navigate to Positions/Contracts Page
- In Trade Manager, go to the page that shows your positions or contracts
- Watch the Network tab - you should see requests appear

### 6. Look for These Specific Requests:
- `/contract` - Contract information
- `/position` - Position data  
- `/md/getQuote` - Market data/quotes
- Any request containing `contractId` or `4086418` (your contract ID)

### 7. Capture the Request Details
For each relevant request:

**Option A: Copy as cURL**
- Right-click on the request
- Select "Copy" → "Copy as cURL"
- Paste it here

**Option B: Screenshot**
- Click on the request
- Look at the "Headers" tab - screenshot the Request Headers
- Look at the "Payload" tab (if POST) - screenshot the request body
- Look at the "Response" tab - screenshot the JSON response

**Option C: Manual Copy**
- Click on the request
- In the "Headers" tab, copy:
  - Request URL (full URL)
  - Request Method (GET/POST)
  - Authorization header (if present)
- In the "Payload" tab (if POST), copy the JSON body
- In the "Response" tab, copy the JSON response

### 8. What to Look For Specifically:
1. **Contract Info Request**:
   - URL format (e.g., `/contract?id=4086418` or `/contract/item`)
   - Request method (GET or POST)
   - Headers (especially Authorization)
   - Response structure (what fields contain the symbol name)

2. **Position Request**:
   - How positions are fetched
   - What fields are returned
   - How P&L is included

3. **Quote Request**:
   - How market data is fetched
   - Response format

### Alternative: Check Trade Manager's API Responses
If Trade Manager doesn't make direct calls to Tradovate (it might proxy through their backend):

1. In Network tab, filter for:
   ```
   trademanagergroup.com/api
   ```

2. Look for requests like:
   - `/api/trades/open/` (you already captured this one)
   - `/api/positions/`
   - `/api/contracts/`
   - Any endpoint that returns position or contract data

3. Check the Response tab - see what data structure Trade Manager returns
   - Does it include contract symbols?
   - Does it include P&L?
   - What format is the data in?

### What to Send Me:
1. The full Request URL
2. Request Method (GET/POST)
3. Request Headers (especially Authorization)
4. Request Body (if POST)
5. Response Body (the JSON data)

This will help me understand exactly how to call Tradovate's API correctly!

