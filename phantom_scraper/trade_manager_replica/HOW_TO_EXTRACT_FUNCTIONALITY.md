# How to Extract Functionality from Trade Manager

This guide explains how to extract all functionality, API calls, WebSocket connections, and event handlers from the Trade Manager website.

## Step 1: Open the Extraction Script

```bash
# View the script
cat EXTRACT_FUNCTIONALITY.js

# Or open in your editor
open EXTRACT_FUNCTIONALITY.js
```

## Step 2: Open Trade Manager Website

1. Open your browser and go to: `https://trademanagergroup.com`
2. **Log in** to your account
3. Open the **Browser Console**:
   - Press `F12` (Windows/Linux) or `Cmd+Option+I` (Mac)
   - Click on the **Console** tab

## Step 3: Paste the Script

1. Copy the **entire contents** of `EXTRACT_FUNCTIONALITY.js`
2. Paste it into the browser console
3. Press `Enter`
4. You should see: `✅ Functionality extraction script loaded!`

## Step 4: Navigate and Interact

The script will now **automatically capture**:

- ✅ **All API calls** (fetch, XMLHttpRequest)
- ✅ **WebSocket connections** and messages
- ✅ **Event listeners** on elements
- ✅ **Form submissions** with data
- ✅ **LocalStorage** and **SessionStorage**
- ✅ **Cookies**

**To capture functionality:**

1. **Navigate through pages**: Dashboard → My Recorders → My Trader → etc.
2. **Click buttons**: Create Strategy, Edit, Delete, etc.
3. **Fill out forms**: Settings, Account Management, etc.
4. **Interact with features**: Toggle switches, dropdowns, etc.
5. **Wait for API calls**: Some actions may trigger delayed requests

## Step 5: Export the Data

After you've tested all functionality:

1. In the console, run:
   ```javascript
   window.extractFunctionality.export()
   ```

2. This will **download a JSON file** with all captured data

3. The file will be named like: `trade_manager_functionality_user_dashboard_1234567890.json`

## Step 6: View Current Data (Optional)

To see what's been captured so far without exporting:

```javascript
window.extractFunctionality.log()
```

This shows:
- Number of API calls captured
- WebSocket connections
- Event listeners found
- Form submissions
- etc.

## Step 7: Repeat for Each Page

For best results, extract functionality for each page separately:

1. **Dashboard page**: Navigate, click buttons, export
2. **My Recorders page**: Navigate, create/edit/delete strategies, export
3. **My Trader page**: Navigate, interact, export
4. **Account Management**: Add/edit accounts, export
5. **Control Center**: Use manual trader, export
6. **Settings**: Update settings, export

## What Gets Captured

### API Calls
```json
{
  "type": "fetch",
  "url": "/api/dashboard/summary/",
  "method": "GET",
  "headers": {...},
  "status": 200,
  "response": {...}
}
```

### WebSocket Connections
```json
{
  "url": "wss://trademanagergroup.com/ws",
  "messages": [
    {"type": "sent", "data": "...", "timestamp": "..."},
    {"type": "received", "data": "...", "timestamp": "..."}
  ],
  "events": [...]
}
```

### Event Listeners
```json
{
  "selector": "#createStrategyBtn",
  "events": [
    {
      "type": "click",
      "listeners": [
        {"listener": "function() {...}", "useCapture": false}
      ]
    }
  ]
}
```

### Form Submissions
```json
{
  "action": "/api/strategy/create",
  "method": "POST",
  "data": {
    "name": "My Strategy",
    "ticker": "MES1!"
  }
}
```

## Tips

1. **Keep console open**: The script logs all captured API calls
2. **Test thoroughly**: Click buttons, fill forms, navigate pages
3. **Wait for responses**: Some API calls are delayed
4. **Check WebSocket**: Make sure WebSocket connections are active
5. **Multiple exports**: Export after each major interaction
6. **Refresh if needed**: If script stops working, refresh page and re-paste

## Troubleshooting

**Script not working?**
- Make sure you pasted the **entire script** (not just the filename)
- Refresh the page and try again
- Check console for errors

**No API calls captured?**
- Make sure you're **logged in**
- **Interact with the page** (click buttons, submit forms)
- Some pages may not have API calls until you interact

**WebSocket not captured?**
- Make sure WebSocket is **connected** (check Network tab)
- Wait a few seconds after page load
- Some pages may not use WebSocket

## Next Steps

After extracting functionality data:

1. **Share the JSON files** with me
2. I'll analyze the API endpoints, request/response formats
3. I'll replicate the functionality in the replica
4. I'll implement the same API calls and WebSocket connections

