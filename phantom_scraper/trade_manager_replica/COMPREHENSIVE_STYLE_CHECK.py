#!/usr/bin/env python3
"""
Comprehensive Style Checker
Compares all extraction JSON files with current CSS files to find missing styles
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

def normalize_css_value(value):
    """Normalize CSS values for comparison"""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        # Remove extra spaces
        value = re.sub(r'\s+', ' ', value.strip())
        # Normalize rgba/rgb
        value = re.sub(r'rgba\(([^)]+)\)', r'rgba(\1)', value)
        value = re.sub(r'rgb\(([^)]+)\)', r'rgb(\1)', value)
    return value

def camel_to_kebab(camel_str):
    """Convert camelCase to kebab-case"""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1-\2', camel_str)
    return re.sub('([a-z0-9])([A-Z])', r'\1-\2', s1).lower()

def load_extraction(filepath):
    """Load extraction JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('styles', {}) or data.get('elements', [])
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}

def parse_css_file(filepath):
    """Parse CSS file and extract all rules"""
    if not filepath.exists():
        return {}
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    rules = {}
    # Match CSS rules: selector { properties }
    pattern = r'([^{]+)\{([^}]+)\}'
    for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
        selector = match.group(1).strip()
        props_text = match.group(2).strip()
        
        # Parse properties
        properties = {}
        for prop_match in re.finditer(r'([^:;]+):([^;]+);', props_text):
            prop_name = prop_match.group(1).strip()
            prop_value = prop_match.group(2).strip()
            properties[prop_name] = prop_value
        
        if selector not in rules:
            rules[selector] = {}
        rules[selector].update(properties)
    
    return rules

def compare_styles(extracted, current_css):
    """Compare extracted styles with current CSS"""
    missing = {}
    different = {}
    
    for selector, styles in extracted.items():
        if selector not in current_css:
            missing[selector] = styles
        else:
            for prop, value in styles.items():
                css_prop = camel_to_kebab(prop)
                if css_prop not in current_css[selector]:
                    if selector not in missing:
                        missing[selector] = {}
                    missing[selector][css_prop] = normalize_css_value(value)
                else:
                    current_value = normalize_css_value(current_css[selector][css_prop])
                    extracted_value = normalize_css_value(value)
                    if current_value != extracted_value:
                        if selector not in different:
                            different[selector] = {}
                        different[selector][css_prop] = {
                            'current': current_value,
                            'extracted': extracted_value
                        }
    
    return missing, different

def main():
    print("=" * 80)
    print("COMPREHENSIVE STYLE CHECKER")
    print("=" * 80)
    print()
    
    all_missing = {}
    all_different = {}
    
    for extraction_file, css_file in EXTRACTION_TO_CSS.items():
        extraction_path = EXTRACTION_DIR / extraction_file
        css_path = CSS_DIR / css_file
        
        if not extraction_path.exists():
            print(f"⚠️  Extraction file not found: {extraction_file}")
            continue
        
        print(f"\n📄 Checking: {extraction_file} → {css_file}")
        print("-" * 80)
        
        # Load extraction data
        extracted_data = load_extraction(extraction_path)
        
        # Handle different extraction formats
        if isinstance(extracted_data, list):
            # Convert elements array to styles dict
            styles_dict = {}
            for elem in extracted_data:
                if 'computedStyles' in elem:
                    selector = elem.get('selector', '')
                    if selector:
                        styles_dict[selector] = elem['computedStyles']
            extracted_data = styles_dict
        
        # Parse current CSS
        current_css = parse_css_file(css_path)
        
        # Compare
        missing, different = compare_styles(extracted_data, current_css)
        
        if missing:
            all_missing[css_file] = missing
            print(f"❌ Missing {len(missing)} selectors:")
            for selector in list(missing.keys())[:10]:  # Show first 10
                print(f"   - {selector}")
            if len(missing) > 10:
                print(f"   ... and {len(missing) - 10} more")
        
        if different:
            all_different[css_file] = different
            print(f"⚠️  {len(different)} selectors have different values:")
            for selector in list(different.keys())[:5]:  # Show first 5
                print(f"   - {selector}")
                for prop, vals in list(different[selector].items())[:3]:
                    print(f"     {prop}: '{vals['current']}' → '{vals['extracted']}'")
            if len(different) > 5:
                print(f"   ... and {len(different) - 5} more")
        
        if not missing and not different:
            print("✅ All styles match!")
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Files with missing styles: {len(all_missing)}")
    print(f"Files with different values: {len(all_different)}")
    
    if all_missing or all_different:
        print("\n⚠️  ACTION REQUIRED: Styles need to be updated")
        return False
    else:
        print("\n✅ All styles match perfectly!")
        return True

if __name__ == '__main__':
    main()

