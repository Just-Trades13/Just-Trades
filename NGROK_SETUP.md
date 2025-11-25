# Quick ngrok Setup (2 minutes)

## Step 1: Sign Up for Free ngrok Account

1. Go to: https://dashboard.ngrok.com/signup
2. Sign up with email (free account)
3. Verify your email

## Step 2: Get Your Authtoken

1. After signing in, go to: https://dashboard.ngrok.com/get-started/your-authtoken
2. Copy your authtoken (looks like: `2abc123xyz...`)

## Step 3: Install Authtoken

Run this command in Terminal (replace YOUR_TOKEN with your actual token):

```bash
ngrok config add-authtoken YOUR_TOKEN
```

## Step 4: Start ngrok

```bash
ngrok http 8082
```

You'll see your public URL like: `https://abc123.ngrok.io`

---

**Note:** Free ngrok URLs change each time you restart. For a permanent URL, use Render instead (see below).

