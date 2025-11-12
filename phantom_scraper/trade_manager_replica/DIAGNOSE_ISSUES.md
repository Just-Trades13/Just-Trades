# 🔍 Diagnostic Checklist

## Quick Questions:
1. **What page are you on?** (Dashboard, Login, Create Strategy, etc.)
2. **What specifically looks bad?** (No styling, broken layout, missing components?)
3. **What doesn't function?** (Buttons don't work, API calls fail, forms don't submit?)
4. **Browser console errors?** (Press F12 → Console tab, what errors do you see?)

## Common Issues & Fixes:

### Issue 1: No Styling / Looks Plain
**Symptoms:** White background, no colors, unstyled text

**Causes:**
- CSS files not loading
- Vite dev server not serving CSS
- Build process not bundling CSS

**Fix:**
```bash
# Stop frontend dev server (Ctrl+C)
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend"
rm -rf node_modules/.vite  # Clear Vite cache
npm run dev  # Restart
```

### Issue 2: API Calls Failing
**Symptoms:** Network errors, 404s, CORS errors in console

**Check:**
1. Is backend running? (Terminal 1 should show server logs)
2. Check browser console for API errors
3. Check Network tab (F12 → Network) for failed requests

**Fix:**
```bash
# Restart backend
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"
python3 app.py
```

### Issue 3: Components Not Rendering
**Symptoms:** Blank page, error messages

**Check browser console (F12) for:**
- React errors
- Import errors
- Missing module errors

**Fix:**
```bash
# Reinstall dependencies
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend"
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Issue 4: Login Not Working
**Symptoms:** Can't login, stuck on login page

**Check:**
- Backend is running
- Test user exists: `python3 SETUP_TEST_USER.py`
- Check browser console for errors

---

## 🚨 Quick Fix Commands

### Full Reset (if everything is broken):
```bash
# Terminal 1: Backend
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"
rm trade_manager.db
python3 SETUP_TEST_USER.py
python3 app.py

# Terminal 2: Frontend
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend"
rm -rf node_modules/.vite dist
npm install
npm run dev
```

### Check What's Running:
```bash
# Check if backend is running
lsof -i :5001

# Check if frontend is running
lsof -i :5173
```

---

## 📋 What to Report:

1. **Browser console errors** (F12 → Console, copy all red errors)
2. **Network tab errors** (F12 → Network, filter by "Failed", screenshot)
3. **Which page** you're on
4. **What you tried** to do
5. **Screenshot** of the broken page (if possible)

---

**Paste the output here and I'll fix it!**

