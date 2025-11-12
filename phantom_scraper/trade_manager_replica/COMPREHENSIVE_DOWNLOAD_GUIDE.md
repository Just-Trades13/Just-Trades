# Comprehensive Trade Manager Site Download Guide

This guide provides multiple methods to download the entire Trade Manager site for replication.

## Method 1: wget (Recommended)

### Quick Download
```bash
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"
./DOWNLOAD_FULL_SITE.sh
```

### Manual wget Command
```bash
wget --mirror \
  --convert-links \
  --adjust-extension \
  --page-requisites \
  --no-parent \
  --user-agent="Mozilla/5.0" \
  --wait=1 \
  --recursive \
  --level=5 \
  --domains=trademanagergroup.com \
  --accept=html,css,js,png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot,ico \
  https://trademanagergroup.com
```

## Method 2: httrack (Alternative)

### Install httrack
```bash
# macOS
brew install httrack

# Linux
sudo apt-get install httrack
```

### Download with httrack
```bash
httrack https://trademanagergroup.com \
  -O trademanagergroup_httrack \
  -r5 \
  -*.pdf \
  -*.zip \
  -*.exe \
  -+*.css \
  -+*.js \
  -+*.png \
  -+*.jpg \
  -+*.gif \
  -+*.svg \
  -+*.woff \
  -+*.woff2 \
  -+*.ttf \
  -+*.eot
```

## Method 3: Browser Extension

1. Install "SingleFile" or "Save Page WE" browser extension
2. Navigate to each page:
   - `/auth/login`
   - `/user/dashboard`
   - `/user/at/strats`
   - `/user/at/accnts`
   - `/user/at/controls`
   - `/user/settings`
   - `/user/at/strat` (create strategy)
3. Save each page as HTML
4. Browser will save all assets automatically

## After Download

### Extract and Apply
```bash
cd "/Users/mylesjadwin/Trading Projects/phantom_scraper/trade_manager_replica"
python3 EXTRACT_AND_APPLY_ALL.py
```

### What Gets Extracted

1. **CSS Styles**
   - Body background colors
   - Component styles (.login-page, .dashboard, .sidebar)
   - Button styles
   - Form styles

2. **Assets**
   - Images (PNG, JPG, GIF, SVG)
   - Fonts (WOFF, WOFF2, TTF, EOT)
   - Icons

3. **HTML Structure**
   - Meta tags
   - Link tags (CSS, fonts)
   - Script tags

4. **JavaScript**
   - Main bundle analysis
   - Component structure
   - API endpoints

## Files Created

- `trademanagergroup_full/` - Full site download
- `download.log` - Download log
- `extracted_styles.json` - Extracted CSS styles
- `asset_mapping.json` - Asset file mapping

## Next Steps

1. Run the download script
2. Run the extraction script
3. Review extracted data
4. Apply to replica
5. Test and verify

