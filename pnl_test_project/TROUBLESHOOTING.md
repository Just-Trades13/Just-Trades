# Troubleshooting Authentication Issues

## Error: "Incorrect username or password"

### Possible Causes:

1. **Wrong Password**
   - Passwords are case-sensitive
   - Check for typos
   - Verify password in Tradovate account

2. **Wrong Client ID/Secret**
   - Client ID "8580" might need to be "cid8580"
   - Client Secret might be incorrect
   - Client ID/Secret might not be registered for this account

3. **Account Type Mismatch**
   - Using demo credentials with live endpoint (or vice versa)
   - Check if account is demo or live

4. **Client ID Not Registered**
   - The Client ID "8580" might not be registered for your account
   - May need to register a new OAuth app

### Solutions:

#### Option 1: Try Without Client ID/Secret
Some accounts work without Client ID/Secret:
```bash
python3 test_pnl_tracking.py
# When asked "Use Client ID/Secret? (y/n):" answer "n"
```

#### Option 2: Try Different Client ID Format
The Client ID might need "cid" prefix:
- Try: `cid8580` instead of `8580`

#### Option 3: Verify Credentials
1. Log into Tradovate website directly
2. Verify username and password work
3. Check if account is demo or live

#### Option 4: Register New OAuth App
If Client ID/Secret don't work:
1. Log into Tradovate
2. Go to Application Settings → API Access
3. Register new OAuth app
4. Get new Client ID and Secret
5. Use those in the test

---

## Error: "The app is not registered"

### Cause:
- Trying to use Client ID/Secret that aren't registered
- Or using appId "Just.Trade" without registration

### Solution:
1. **Use Client ID/Secret** (if you have them registered)
2. **Or register the app** in Tradovate account settings
3. **Or try different appId** values (Tradovate, TradovateAPI, etc.)

---

## Quick Test Without Client ID/Secret

Try this first to verify username/password:

```bash
cd "/Users/mylesjadwin/Trading Projects/pnl_test_project"
python3 test_simple.py
```

Enter:
- Username: markjad58
- Password: Greens131393!
- Use Client ID/Secret? (y/n): n
- Use demo? (y/n): y

This will test just authentication without WebSockets.

---

## Next Steps

1. **Verify credentials work** on Tradovate website
2. **Try without Client ID/Secret** first
3. **If that fails**, check password is correct
4. **If Client ID/Secret needed**, verify they're correct for your account

