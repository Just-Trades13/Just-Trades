#!/usr/bin/env python3
"""
Apply extracted styles to match original Trade Manager site exactly
This script reads extraction files and creates/updates CSS files
"""

import json
import os
from pathlib import Path

# Mapping of extraction files to CSS files
EXTRACTION_MAP = {
    'login': {
        'extraction': 'trade_manager_extraction__auth_login_1762408332951.json',
        'css': 'frontend/src/pages/Login.css',
        'page': 'Login'
    },
    'my_recorders': {
        'extraction': 'trade_manager_extraction__user_strats_1762405557781.json',
        'css': 'frontend/src/pages/MyRecorders.css',
        'page': 'MyRecorders'
    },
    'account_management': {
        'extraction': 'trade_manager_extraction__user_at_accnts_1762405614838.json',
        'css': 'frontend/src/pages/AccountManagement.css',
        'page': 'AccountManagement'
    },
    'my_trader': {
        'extraction': 'trade_manager_extraction__user_at_strats_1762405661810.json',
        'css': 'frontend/src/pages/MyTrader.css',
        'page': 'MyTrader'
    },
    'control_center': {
        'extraction': 'trade_manager_extraction__user_at_controls_1762406209185.json',
        'css': 'frontend/src/pages/ControlCenter.css',
        'page': 'ControlCenter'
    },
    'settings': {
        'extraction': 'trade_manager_extraction__user_settings_1762406252644.json',
        'css': 'frontend/src/pages/Settings.css',
        'page': 'Settings'
    },
    'create_strategy': {
        'extraction': 'trade_manager_extraction__user_at_strat_1762407052878.json',
        'css': 'frontend/src/pages/CreateStrategy.css',
        'page': 'CreateStrategy'
    }
}

def process_extraction_file(extraction_path, output_path):
    """Process a single extraction file"""
    print(f"\n📄 Processing: {extraction_path}")
    
    if not os.path.exists(extraction_path):
        print(f"   ❌ File not found: {extraction_path}")
        return False
    
    try:
        with open(extraction_path, 'r') as f:
            data = json.load(f)
        
        styles = data.get('styles', {})
        if not styles:
            print(f"   ⚠️  No styles found in extraction file")
            return False
        
        # Generate CSS
        css_content = []
        css_content.append("/**")
        css_content.append(f" * Styles extracted from: {os.path.basename(extraction_path)}")
        css_content.append(" * Auto-generated from Trade Manager extraction")
        css_content.append(" */\n")
        
        for selector, props in sorted(styles.items()):
            css_content.append(f"{selector} {{")
            for prop, value in sorted(props.items()):
                # Convert camelCase to kebab-case for CSS
                css_prop = prop
                replacements = {
                    'backgroundColor': 'background-color',
                    'fontSize': 'font-size',
                    'fontWeight': 'font-weight',
                    'fontFamily': 'font-family',
                    'borderRadius': 'border-radius',
                    'boxShadow': 'box-shadow',
                    'textAlign': 'text-align',
                    'textTransform': 'text-transform',
                    'letterSpacing': 'letter-spacing',
                    'lineHeight': 'line-height',
                    'marginTop': 'margin-top',
                    'marginBottom': 'margin-bottom',
                    'marginLeft': 'margin-left',
                    'marginRight': 'margin-right',
                    'paddingTop': 'padding-top',
                    'paddingBottom': 'padding-bottom',
                    'paddingLeft': 'padding-left',
                    'paddingRight': 'padding-right',
                    'borderTop': 'border-top',
                    'borderBottom': 'border-bottom',
                    'borderLeft': 'border-left',
                    'borderRight': 'border-right',
                    'borderWidth': 'border-width',
                    'borderColor': 'border-color',
                    'borderStyle': 'border-style',
                    'minWidth': 'min-width',
                    'maxWidth': 'max-width',
                    'minHeight': 'min-height',
                    'maxHeight': 'max-height'
                }
                for key, val in replacements.items():
                    css_prop = css_prop.replace(key, val)
                
                css_content.append(f"  {css_prop}: {value};")
            css_content.append("}\n")
        
        css_text = "\n".join(css_content)
        
        # Write CSS file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(css_text)
        
        print(f"   ✅ Generated: {output_path}")
        print(f"   📊 Styles: {len(styles)} selectors")
        return True
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def main():
    """Main function to process all extraction files"""
    base_path = Path(__file__).parent
    
    print("=" * 80)
    print("APPLYING EXTRACTED STYLES")
    print("=" * 80)
    
    success_count = 0
    total_count = len(EXTRACTION_MAP)
    
    for page_name, config in EXTRACTION_MAP.items():
        extraction_path = base_path / config['extraction']
        css_path = base_path / config['css']
        
        if process_extraction_file(str(extraction_path), str(css_path)):
            success_count += 1
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: {success_count}/{total_count} files processed successfully")
    print("=" * 80)
    
    if success_count == total_count:
        print("\n✅ All styles applied successfully!")
        print("\n⚠️  NOTE: These are auto-generated. You may need to:")
        print("   1. Merge with existing styles")
        print("   2. Add responsive breakpoints")
        print("   3. Add hover/focus states")
    else:
        print(f"\n⚠️  {total_count - success_count} files failed to process")

if __name__ == '__main__':
    main()

