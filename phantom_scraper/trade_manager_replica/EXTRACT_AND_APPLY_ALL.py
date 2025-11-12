#!/usr/bin/env python3
"""
Comprehensive extraction and application script
Extracts styles, assets, and structure from downloaded site
and applies them to our replica.
"""

import json
import os
import re
import shutil
from pathlib import Path

def find_downloaded_files():
    """Find all downloaded files."""
    # Check multiple possible locations, prefer the one with more files
    candidates = []
    for dir_name in ['trademanagergroup_full', 'trademanagergroup.com']:
        test_dir = Path(dir_name)
        if test_dir.exists() and test_dir.is_dir():
            file_count = len(list(test_dir.rglob('*')))
            candidates.append((file_count, test_dir))
    
    if not candidates:
        return None, None, None, None
    
    # Use the directory with the most files
    base_dir = max(candidates, key=lambda x: x[0])[1]
    print(f"   Using directory: {base_dir} ({max(candidates, key=lambda x: x[0])[0]} items)")
    
    css_files = list(base_dir.rglob('*.css'))
    js_files = list(base_dir.rglob('*.js'))
    html_files = list(base_dir.rglob('*.html'))
    image_files = []
    for ext in ['*.png', '*.jpg', '*.jpeg', '*.gif', '*.svg']:
        image_files.extend(base_dir.rglob(ext))
    
    return css_files, js_files, html_files, image_files

def extract_css_styles(css_file):
    """Extract key CSS styles from minified CSS."""
    try:
        with open(css_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract key selectors
        styles = {}
        
        # Body styles
        body_match = re.search(r'body[^{]*\{([^}]+)\}', content, re.IGNORECASE)
        if body_match:
            styles['body'] = body_match.group(1)
        
        # Login page
        login_match = re.search(r'\.login-page[^{]*\{([^}]+)\}', content, re.IGNORECASE)
        if login_match:
            styles['.login-page'] = login_match.group(1)
        
        # Dashboard
        dashboard_match = re.search(r'\.dashboard[^{]*\{([^}]+)\}', content, re.IGNORECASE)
        if dashboard_match:
            styles['.dashboard'] = dashboard_match.group(1)
        
        # Sidebar
        sidebar_match = re.search(r'\.sidebar[^{]*\{([^}]+)\}', content, re.IGNORECASE)
        if sidebar_match:
            styles['.sidebar'] = sidebar_match.group(1)
        
        return styles
    except Exception as e:
        print(f"Error reading {css_file}: {e}")
        return {}

def copy_assets(image_files, target_dir):
    """Copy image assets to frontend public directory."""
    target = Path('frontend/public/static/media')
    target.mkdir(parents=True, exist_ok=True)
    
    copied = 0
    for img_file in image_files:
        try:
            dest = target / img_file.name
            if not dest.exists():
                shutil.copy2(img_file, dest)
                copied += 1
        except Exception as e:
            print(f"Error copying {img_file}: {e}")
    
    return copied

def apply_body_background(styles):
    """Apply body background color to index.css."""
    if 'body' not in styles:
        return False
    
    body_styles = styles['body']
    bg_match = re.search(r'background-color:\s*([^;]+)', body_styles, re.IGNORECASE)
    
    if bg_match:
        bg_color = bg_match.group(1).strip()
        index_css = Path('frontend/src/index.css')
        
        if index_css.exists():
            with open(index_css, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update body background-color
            pattern = r'(body\s*\{[^}]*background-color:\s*)[^;]+(;)'
            if re.search(pattern, content):
                content = re.sub(pattern, f'\\1 {bg_color}\\2', content, flags=re.IGNORECASE)
            else:
                # Add if not present
                pattern = r'(body\s*\{[^}]*)(\})'
                content = re.sub(pattern, f'\\1  background-color: {bg_color};\\2', content, flags=re.IGNORECASE)
            
            with open(index_css, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ Updated body background-color to {bg_color}")
            return True
    
    return False

def analyze_html_structure(html_files):
    """Analyze HTML structure to understand page layout."""
    structures = {}
    
    for html_file in html_files[:5]:  # Limit to first 5 files
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract meta tags
            meta_tags = re.findall(r'<meta[^>]+>', content, re.IGNORECASE)
            
            # Extract link tags (CSS, fonts, etc.)
            link_tags = re.findall(r'<link[^>]+>', content, re.IGNORECASE)
            
            # Extract script tags
            script_tags = re.findall(r'<script[^>]*>', content, re.IGNORECASE)
            
            structures[html_file.name] = {
                'meta': len(meta_tags),
                'links': len(link_tags),
                'scripts': len(script_tags)
            }
        except Exception as e:
            print(f"Error reading {html_file}: {e}")
    
    return structures

def main():
    """Main function."""
    print("🔍 Analyzing downloaded Trade Manager site...")
    print("=" * 60)
    
    css_files, js_files, html_files, image_files = find_downloaded_files()
    
    if not css_files:
        print("❌ No downloaded files found!")
        print("💡 Run DOWNLOAD_FULL_SITE.sh first")
        return
    
    print(f"📄 Found {len(css_files)} CSS files")
    print(f"📜 Found {len(js_files)} JS files")
    print(f"🌐 Found {len(html_files)} HTML files")
    print(f"🖼️  Found {len(image_files)} image files")
    print("")
    
    # Extract styles from main CSS
    print("🎨 Extracting CSS styles...")
    main_css = None
    for css_file in css_files:
        if 'main' in css_file.name.lower():
            main_css = css_file
            break
    
    if main_css:
        print(f"   Analyzing: {main_css}")
        styles = extract_css_styles(main_css)
        if styles:
            print(f"   ✅ Extracted {len(styles)} key style blocks")
            apply_body_background(styles)
    else:
        print("   ⚠️  Main CSS file not found")
    
    # Copy assets
    print("")
    print("📦 Copying assets...")
    copied = copy_assets(image_files, 'frontend/public/static/media')
    print(f"   ✅ Copied {copied} new image files")
    
    # Analyze HTML structure
    print("")
    print("📋 Analyzing HTML structure...")
    structures = analyze_html_structure(html_files)
    for filename, info in structures.items():
        print(f"   {filename}: {info['meta']} meta, {info['links']} links, {info['scripts']} scripts")
    
    print("")
    print("=" * 60)
    print("✅ Analysis complete!")
    print("")
    print("📝 Next steps:")
    print("   1. Review extracted styles")
    print("   2. Compare with current implementation")
    print("   3. Apply any missing styles")
    print("   4. Test the replica")

if __name__ == '__main__':
    main()

