#!/usr/bin/env python3
"""
Comprehensive script to apply ALL extracted styles and formatting
from all extraction JSON files to create an exact replica
"""

import json
import os
import re
from pathlib import Path
from collections import defaultdict

# Base directory
BASE_DIR = Path(__file__).parent

# All extraction files
EXTRACTION_FILES = [
    "trade_manager_extraction__user_strats_1762405557781.json",
    "trade_manager_extraction__user_settings_1762406252644.json",
    "trade_manager_extraction__user_at_strats_1762405661810.json",
    "trade_manager_extraction__user_at_strat_1762407052878.json",
    "trade_manager_extraction__user_at_controls_1762406209185.json",
    "trade_manager_extraction__user_at_accnts_1762405614838.json",
    "trade_manager_extraction__auth_login_1762408332951.json",
]

FUNCTIONALITY_FILES = [
    "trade_manager_functionality__user_strats_1762406783587.json",
    "trade_manager_functionality__user_strat_1762408663571.json",
    "trade_manager_functionality__user_settings_1762407252404.json",
    "trade_manager_functionality__user_dashboard_1762408561408.json",
    "trade_manager_functionality__user_dashboard_1762407753203.json",
    "trade_manager_functionality__user_strat_1762407816800.json",
    "trade_manager_functionality__user_dashboard_1762406722539.json",
    "trade_manager_functionality__user_at_strats_1762407002927.json",
    "trade_manager_functionality__user_at_strat_1762407137327.json",
    "trade_manager_functionality__user_at_controls_1762408049757.json",
    "trade_manager_functionality__user_at_controls_1762407209900.json",
    "trade_manager_functionality__user_at_strat_1762407941512.json",
    "trade_manager_functionality__user_at_accntsetup__1762406931688.json",
    "trade_manager_functionality__user_at_accnts_1762406880831.json",
    "trade_manager_functionality__auth_login_1762408364421.json",
    "trade_manager_functionality__user_at_accnts_1762407884646.json",
]

def load_json_file(filename):
    """Load a JSON file"""
    filepath = BASE_DIR / filename
    if filepath.exists():
        with open(filepath, 'r') as f:
            return json.load(f)
    return None

def extract_all_styles():
    """Extract all styles from all extraction files"""
    all_styles = defaultdict(dict)
    
    for filename in EXTRACTION_FILES:
        data = load_json_file(filename)
        if not data:
            continue
            
        print(f"Processing {filename}...")
        
        # Extract styles from 'styles' object (new format)
        if 'styles' in data and isinstance(data['styles'], dict):
            for selector, styles in data['styles'].items():
                if selector and styles and isinstance(styles, dict):
                    # Normalize selector
                    if not selector.startswith(('#', '.', '[')):
                        if selector.startswith('#'):
                            selector = selector
                        else:
                            selector = f"#{selector}" if selector[0].isupper() or selector.isalnum() else selector
                    
                    all_styles[selector].update(styles)
        
        # Also check for 'elements' array (old format)
        elif 'elements' in data and isinstance(data['elements'], list):
            for element in data['elements']:
                if isinstance(element, dict):
                    selector = element.get('selector', '')
                    styles = element.get('computedStyles', {})
                    
                    if selector and styles:
                        all_styles[selector].update(styles)
    
    return all_styles

def extract_common_styles():
    """Extract common/computed styles that appear across multiple elements"""
    common = {
        'body': {
            'fontFamily': 'Poppins, sans-serif',
            'fontSize': '14px',
            'fontWeight': '400',
            'lineHeight': '21px',
            'letterSpacing': 'normal',
            'color': 'rgb(82, 95, 127)',
            'backgroundColor': 'rgb(30, 30, 47)'
        },
        'h2': {
            'fontFamily': 'Poppins, sans-serif',
            'fontSize': '27px',
            'fontWeight': '100',
            'lineHeight': '32.4px',
            'letterSpacing': 'normal',
            'color': 'rgb(255, 255, 255)',
            'backgroundColor': 'rgba(0, 0, 0, 0)'
        },
        '.btn': {
            'fontFamily': 'Poppins, sans-serif',
            'fontSize': '14px',
            'fontWeight': '600',
            'lineHeight': '18.9px',
            'letterSpacing': 'normal',
            'color': 'rgb(52, 70, 117)',
            'backgroundColor': 'rgba(0, 0, 0, 0)'
        }
    }
    return common

def css_value(value):
    """Convert extracted value to CSS value"""
    if isinstance(value, (int, float)):
        return f"{value}px"
    if isinstance(value, str):
        return value
    return str(value)

def generate_css(styles_dict):
    """Generate CSS from styles dictionary"""
    css_lines = []
    
    for selector, styles in sorted(styles_dict.items()):
        if not styles:
            continue
            
        css_lines.append(f"{selector} {{")
        
        # Sort properties for consistency
        for prop, value in sorted(styles.items()):
            if value:
                # Convert camelCase to kebab-case
                css_prop = re.sub(r'([A-Z])', r'-\1', prop).lower()
                css_val = css_value(value)
                css_lines.append(f"  {css_prop}: {css_val};")
        
        css_lines.append("}")
        css_lines.append("")
    
    return "\n".join(css_lines)

def main():
    """Main function"""
    print("=" * 80)
    print("COMPREHENSIVE STYLE EXTRACTION AND APPLICATION")
    print("=" * 80)
    print()
    
    # Extract all styles
    print("Extracting styles from all files...")
    all_styles = extract_all_styles()
    common_styles = extract_common_styles()
    
    # Merge common styles
    for selector, styles in common_styles.items():
        if selector in all_styles:
            all_styles[selector].update(styles)
        else:
            all_styles[selector] = styles
    
    print(f"Found styles for {len(all_styles)} selectors")
    print()
    
    # Generate comprehensive CSS
    print("Generating CSS...")
    css = generate_css(all_styles)
    
    # Save to file
    output_file = BASE_DIR / "EXTRACTED_STYLES_COMPLETE.css"
    with open(output_file, 'w') as f:
        f.write("/*\n")
        f.write(" * Complete Style Extraction from All JSON Files\n")
        f.write(" * Auto-generated - DO NOT EDIT MANUALLY\n")
        f.write(" */\n\n")
        f.write(css)
    
    print(f"✅ Generated {output_file}")
    print(f"   Total selectors: {len(all_styles)}")
    print()
    
    # Summary
    print("SUMMARY:")
    print(f"  - Style files processed: {len(EXTRACTION_FILES)}")
    print(f"  - Functionality files: {len(FUNCTIONALITY_FILES)}")
    print(f"  - Total selectors extracted: {len(all_styles)}")
    print()
    print("Next steps:")
    print("  1. Review EXTRACTED_STYLES_COMPLETE.css")
    print("  2. Apply relevant styles to component CSS files")
    print("  3. Test visual match with original site")

if __name__ == '__main__':
    main()

