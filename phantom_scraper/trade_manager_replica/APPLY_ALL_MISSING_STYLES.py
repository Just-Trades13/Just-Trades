#!/usr/bin/env python3
"""
Apply All Missing Styles
Reads extraction JSON files and applies missing styles to CSS files
"""

import json
import os
import re
from pathlib import Path

# Map extraction files to CSS files
EXTRACTION_TO_CSS = {
    'trade_manager_extraction__user_strats_1762405557781.json': 'MyRecorders.css',
    'trade_manager_extraction__user_at_accnts_1762405614838.json': 'AccountManagement.css',
    'trade_manager_extraction__user_at_strats_1762405661810.json': 'MyTrader.css',
    'trade_manager_extraction__user_at_controls_1762406209185.json': 'ControlCenter.css',
    'trade_manager_extraction__user_settings_1762406252644.json': 'Settings.css',
    'trade_manager_extraction__auth_login_1762408332951.json': 'Login.css',
    'trade_manager_extraction__user_at_strat_1762407052878.json': 'CreateStrategy.css',
}

BASE_DIR = Path(__file__).parent
EXTRACTION_DIR = BASE_DIR
CSS_DIR = BASE_DIR / 'frontend' / 'src' / 'pages'

def camel_to_kebab(camel_str):
    """Convert camelCase to kebab-case"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', camel_str)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()

def format_css_value(value):
    """Format CSS value properly"""
    if isinstance(value, (int, float)):
        if value == 0:
            return '0'
        return str(value)
    if isinstance(value, str):
        # Remove extra spaces
        value = value.strip()
        # Handle empty strings
        if value == '':
            return 'none'
    return value

def load_extraction(filepath):
    """Load extraction JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('styles', {})
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}

def read_css_file(filepath):
    """Read CSS file content"""
    if not filepath.exists():
        return ''
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def write_css_file(filepath, content):
    """Write CSS file content"""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def css_property_to_string(prop, value):
    """Convert CSS property and value to string"""
    return f"  {prop}: {format_css_value(value)};"

def apply_missing_styles(extraction_file, css_file):
    """Apply missing styles from extraction to CSS file"""
    extraction_path = EXTRACTION_DIR / extraction_file
    css_path = CSS_DIR / css_file
    
    if not extraction_path.exists():
        print(f"⚠️  Extraction file not found: {extraction_file}")
        return False
    
    print(f"\n📄 Processing: {extraction_file} → {css_file}")
    
    # Load extraction data
    extracted_data = load_extraction(extraction_path)
    if not extracted_data:
        print(f"   No styles found in extraction file")
        return False
    
    # Read current CSS
    css_content = read_css_file(css_path)
    
    # Filter out global selectors that shouldn't be in page CSS
    global_selectors = ['#root', '.wrapper', '.Toastify', '.rna-container', 
                       '.navbar-minimize-fixed', '.minimize-sidebar', '.sidebar',
                       '.sidebar-wrapper', '.logo', '.simple-text', '.logo-img',
                       '.nav', '.main-panel', '.navbar-absolute', '.container-fluid',
                       '.navbar-wrapper', '.navbar-minimize', '.navbar-toggle',
                       '.navbar-toggler', '.navbar-toggler-bar', '.navbar-brand',
                       '.ml-auto', '.text-white', '.dropdown', '.d-flex',
                       '.rounded-circle', '.ml-2', '.dropdown-dark', '.dropdown-item',
                       '.separator', '.content', '.footer', '.grecaptcha-badge',
                       '.grecaptcha-logo', '.grecaptcha-error']
    
    # Find page-specific selectors
    page_selectors = {}
    for selector, styles in extracted_data.items():
        # Skip global selectors and malformed selectors
        if selector in global_selectors or selector.startswith('.[object') or selector.startswith('#tooltip'):
            continue
        
        # Convert styles to CSS format
        css_props = []
        for prop, value in styles.items():
            css_prop = camel_to_kebab(prop)
            css_value = format_css_value(value)
            css_props.append(css_property_to_string(css_prop, css_value))
        
        if css_props:
            page_selectors[selector] = '\n'.join(css_props)
    
    if not page_selectors:
        print(f"   No page-specific styles to add")
        return False
    
    # Check which selectors are missing
    missing_selectors = {}
    for selector, props in page_selectors.items():
        # Check if selector exists in CSS
        pattern = re.escape(selector) + r'\s*\{'
        if not re.search(pattern, css_content):
            missing_selectors[selector] = props
    
    if not missing_selectors:
        print(f"   ✅ All page-specific styles already present")
        return True
    
    print(f"   Adding {len(missing_selectors)} missing selectors...")
    
    # Append missing styles to CSS file
    css_content += '\n\n/* Missing styles from extraction */\n'
    for selector, props in missing_selectors.items():
        css_content += f'\n{selector} {{\n{props}\n}}\n'
    
    # Write updated CSS
    write_css_file(css_path, css_content)
    print(f"   ✅ Added {len(missing_selectors)} selectors to {css_file}")
    
    return True

def main():
    print("=" * 80)
    print("APPLY ALL MISSING STYLES")
    print("=" * 80)
    
    applied = 0
    for extraction_file, css_file in EXTRACTION_TO_CSS.items():
        if apply_missing_styles(extraction_file, css_file):
            applied += 1
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: Applied styles to {applied} files")
    print("=" * 80)

if __name__ == '__main__':
    main()

