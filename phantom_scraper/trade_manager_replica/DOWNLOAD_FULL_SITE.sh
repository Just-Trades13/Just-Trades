#!/bin/bash
# Comprehensive download script for Trade Manager site
# This will download the entire site with all assets

BASE_URL="https://trademanagergroup.com"
DOWNLOAD_DIR="trademanagergroup_full"

echo "🚀 Starting comprehensive download of Trade Manager site..."
echo "This may take several minutes..."

# Create download directory
mkdir -p "$DOWNLOAD_DIR"
cd "$DOWNLOAD_DIR"

# Comprehensive wget command with all options
wget \
  --mirror \
  --convert-links \
  --adjust-extension \
  --page-requisites \
  --no-parent \
  --no-host-directories \
  --cut-dirs=0 \
  --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" \
  --wait=1 \
  --random-wait \
  --limit-rate=200k \
  --recursive \
  --level=5 \
  --domains=trademanagergroup.com \
  --exclude-domains=www.google.com,www.googletagmanager.com,fonts.googleapis.com,use.fontawesome.com \
  --accept=html,css,js,png,jpg,jpeg,gif,svg,woff,woff2,ttf,eot,ico,json \
  --reject=pdf,zip,exe \
  --span-hosts \
  --backup-converted \
  --no-clobber \
  "$BASE_URL" 2>&1 | tee download.log

echo ""
echo "✅ Download complete!"
echo "📁 Files downloaded to: $DOWNLOAD_DIR"
echo ""
echo "📊 Summary:"
find . -type f | wc -l | xargs echo "Total files:"
du -sh . | awk '{print "Total size: " $1}'
echo ""
echo "🔍 Key files:"
find . -name "*.css" -type f | head -5
find . -name "*.js" -type f | head -5
find . -name "*.html" -type f | head -5

