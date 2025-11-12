# 🚨 Quick Fix Guide

## Most Common Issues:

### 1. **CSS Not Loading**
**Symptoms:** White background, no styling

**Fix:**
```bash
# Clear Vite cache and restart
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend"
rm -rf node_modules/.vite
npm run dev
```

### 2. **API Errors / Nothing Loading**
**Symptoms:** Empty pages, "Loading..." forever

**Fix:**
```bash
# Check backend is running (Terminal 1)
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"
python3 app.py

# Check browser console (F12) for errors
```

### 3. **Components Not Rendering**
**Symptoms:** Blank page, React errors

**Fix:**
```bash
# Reinstall frontend dependencies
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica/frontend"
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### 4. **Database Errors**
**Symptoms:** Login fails, can't create strategies

**Fix:**
```bash
# Recreate database and test user
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"
rm trade_manager.db
python3 SETUP_TEST_USER.py
```

---

## 🔍 What to Check Right Now:

1. **Open Browser Console (F12):**
   - Look for red errors
   - Check Network tab for failed requests
   - Share the errors with me

2. **Check Backend Terminal:**
   - Should show server running
   - Look for error messages
   - Share any errors

3. **Check Frontend Terminal:**
   - Should show Vite dev server running
   - Look for compilation errors
   - Share any errors

---

## 📸 Tell Me:

1. **What page are you on?** (Dashboard, Login, etc.)
2. **What specifically looks bad?** (describe or screenshot)
3. **What doesn't work?** (buttons, forms, navigation?)
4. **Browser console errors?** (copy/paste red errors)
5. **Backend terminal errors?** (copy/paste any errors)

---

**I'll fix it once I know what's broken!**

