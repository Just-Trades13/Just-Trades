# Manual Redeploy on Render

If Render isn't picking up the new start command, try this:

## Option 1: Manual Redeploy
1. Go to Render dashboard → **"Events"** tab
2. Click **"Manual Deploy"** button
3. Select **"Deploy latest commit"**
4. This forces a fresh deployment with the latest code

## Option 2: Check Settings Again
1. Go to **Settings** tab
2. Scroll to **"Start Command"**
3. Make sure it says exactly:
   ```
   python3 -m gunicorn --bind 0.0.0.0:$PORT ultra_simple_server:app
   ```
4. Click **"Save Changes"** (even if it looks correct)
5. Go back to **"Events"** and manually redeploy

## Option 3: Disable render.yaml (if it's conflicting)
If Render is using `render.yaml` instead of UI settings:
1. In Settings, look for **"Auto-Deploy"** or **"Configuration Source"**
2. Make sure it's using **"UI Settings"** not **"render.yaml"**
3. Or temporarily rename `render.yaml` to `render.yaml.bak` in GitHub

## What Should Happen
After manual redeploy, you should see in logs:
```
==> Running 'python3 -m gunicorn --bind 0.0.0.0:$PORT ultra_simple_server:app'
```

Instead of:
```
==> Running 'gunicorn --bind 0.0.0.0:$PORT ultra_simple_server:app'
```

Try a manual redeploy first - that usually fixes it!

