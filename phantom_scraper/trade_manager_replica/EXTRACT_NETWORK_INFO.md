# How to Extract Deep Information from Trade Manager

This guide will help you extract all the technical details about fonts, hosting, CDN, and assets from the original Trade Manager site.

## Method 1: Browser Script (Recommended)

1. **Open the original Trade Manager site** in your browser
2. **Open Developer Tools** (F12 or Cmd+Option+I)
3. **Go to the Console tab**
4. **Open the file** `EXTRACT_DEEP_INFO.js` in this folder
5. **Copy the entire script** and paste it into the console
6. **Press Enter**
7. **Copy the JSON output** that appears
8. **Save it** as `trade_manager_deep_info.json`

## Method 2: Network Tab (Manual)

1. **Open Developer Tools** (F12)
2. **Go to Network tab**
3. **Refresh the page** (Cmd+R or Ctrl+R)
4. **Filter by type:**
   - **Font**: Look for `.woff`, `.woff2`, `.ttf`, `.otf` files
   - **CSS**: Look for `.css` files
   - **JS**: Look for `.js` files
   - **XHR/Fetch**: Look for API calls
5. **For each resource:**
   - Click on it
   - Check the "Headers" tab for:
     - Request URL (where it's hosted)
     - Response Headers (server info)
   - Check the "Preview" tab to see the content
6. **Take screenshots** or copy the URLs

## Method 3: Sources Tab (For Fonts)

1. **Open Developer Tools** (F12)
2. **Go to Sources tab**
3. **Look for:**
   - `fonts.googleapis.com` - Google Fonts
   - Custom font files
   - CSS files with `@font-face` declarations
4. **Copy the font URLs**

## Method 4: Elements Tab (For Computed Styles)

1. **Open Developer Tools** (F12)
2. **Go to Elements tab**
3. **Select an element** (e.g., `<h1>` or `.sidebar`)
4. **Look at the "Computed" tab** on the right
5. **Find `font-family`** - this shows the actual font being used
6. **Note the font stack** (e.g., `"Poppins", "Helvetica Neue", sans-serif`)

## Method 5: HAR File Export

1. **Open Developer Tools** (F12)
2. **Go to Network tab**
3. **Refresh the page**
4. **Right-click** anywhere in the Network tab
5. **Select "Save all as HAR with content"**
6. **Save the file** - this contains ALL network requests
7. **Share the HAR file** - I can analyze it

## What to Look For

### Fonts
- ✅ Google Fonts URL (e.g., `fonts.googleapis.com/css2?family=Poppins`)
- ✅ Font weights being used (300, 400, 500, 600, 700)
- ✅ Custom font files (`.woff2`, `.woff`, `.ttf`)
- ✅ `@font-face` declarations in CSS

### Hosting
- ✅ Main domain (e.g., `trademanagergroup.com`)
- ✅ CDN domains (e.g., `cdn.trademanagergroup.com`)
- ✅ Third-party hosting (e.g., AWS, Cloudflare)

### CSS
- ✅ All stylesheet URLs
- ✅ Inline styles
- ✅ CSS framework (Bootstrap, Tailwind, etc.)
- ✅ Custom CSS files

### JavaScript
- ✅ Framework (React, Vue, Angular)
- ✅ Libraries (jQuery, Socket.IO, etc.)
- ✅ Custom JS files
- ✅ Bundle files

## Quick Check Script

Run this in the console to quickly see fonts:

```javascript
// Quick font check
console.log('Fonts:', Array.from(document.fonts).map(f => f.family));
console.log('CSS:', Array.from(document.styleSheets).map(s => s.href));
console.log('JS:', Array.from(document.scripts).map(s => s.src));
```

## After Extraction

1. **Save the JSON file** from Method 1
2. **Share it with me** - I'll analyze it
3. **Or share the HAR file** - I can extract everything from it

This will help us identify:
- Exact font loading method
- CDN/hosting setup
- Missing CSS/JS files
- Font rendering differences
- Any third-party dependencies

