# Render Setup - Get Permanent URL (15 minutes)

## Why Render is Better:
- ✅ **Permanent URL** (never changes)
- ✅ **Free tier** available
- ✅ **Auto-deploys** when you push to GitHub
- ✅ **No authentication needed** for basic setup
- ✅ **Works 24/7** (wakes up automatically)

## Step-by-Step:

### 1. Sign Up (2 minutes)
- Go to: https://render.com
- Click "Get Started for Free"
- Sign up with GitHub (easiest) or email

### 2. Create Web Service (5 minutes)
- Click "New +" → "Web Service"
- Click "Connect account" next to GitHub
- Authorize Render to access your repos
- Select: **`Just-Trades13/Just-Trades.`**

### 3. Configure (Auto-detected!)
Render will automatically detect:
- ✅ `render.yaml` file (already configured!)
- ✅ Python 3
- ✅ Build command: `pip install -r requirements.txt`
- ✅ Start command: `gunicorn ultra_simple_server:app`

**Just verify these settings:**
- **Name:** `just-trades` (or any name)
- **Region:** Choose closest to you
- **Branch:** `main`
- **Root Directory:** Leave blank (or `/`)

### 4. Deploy (5-10 minutes)
- Click "Create Web Service"
- Wait for build to complete
- Your site will be live at: `just-trades.onrender.com`

### 5. Access Your Site
Once deployed, you can:
- Access from anywhere: `https://just-trades.onrender.com`
- Share with friends
- Access from your phone
- It stays up 24/7!

---

## Free Tier Notes:
- Spins down after 15 minutes of inactivity
- Wakes up automatically on first request (takes ~30 seconds)
- Perfect for personal use and testing!

---

## Already Done ✅
- ✅ Code pushed to GitHub
- ✅ `render.yaml` configured
- ✅ `Procfile` ready
- ✅ `requirements.txt` included
- ✅ Server configured for production

**You're ready to deploy!**

