#!/usr/bin/env python3
"""
Apply extracted styles to component CSS files based on selector patterns
"""

import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
EXTRACTED_CSS = BASE_DIR / "EXTRACTED_STYLES_COMPLETE.css"

# Component mapping: selector patterns -> CSS file
COMPONENT_MAPPING = {
    'MyRecorders': {
        'file': 'frontend/src/pages/MyRecorders.css',
        'patterns': [
            r'\.recorders-',
            r'\.strategy-',
            r'\.action-',
            r'#tooltip_(edit|refresh|remove)',
            r'\.page-link',
            r'\.pagination',
        ]
    },
    'Dashboard': {
        'file': 'frontend/src/pages/Dashboard.css',
        'patterns': [
            r'\.dashboard-',
            r'\.chart-',
            r'\.calendar-',
            r'\.status-badge',
            r'\.summary-card',
        ]
    },
    'MyTrader': {
        'file': 'frontend/src/pages/MyTrader.css',
        'patterns': [
            r'\.my-trader-',
            r'\.strategy-list',
            r'\.toggle-',
        ]
    },
    'CreateStrategy': {
        'file': 'frontend/src/pages/CreateStrategy.css',
        'patterns': [
            r'\.strategy-form',
            r'\.form-section',
            r'\.form-group',
            r'#(Strat_Name|Position_Size|TakeProfit|Alternate_Name)',
        ]
    },
    'ControlCenter': {
        'file': 'frontend/src/pages/ControlCenter.css',
        'patterns': [
            r'\.control-center',
            r'\.manual-trader',
            r'#Control_Panel',
        ]
    },
    'AccountManagement': {
        'file': 'frontend/src/pages/AccountManagement.css',
        'patterns': [
            r'\.account-',
            r'\.account-card',
            r'#(clearBtn|deleteBtn)',
        ]
    },
    'Settings': {
        'file': 'frontend/src/pages/Settings.css',
        'patterns': [
            r'\.settings-',
            r'#(confirmPassword|newPassword)',
        ]
    },
    'Login': {
        'file': 'frontend/src/pages/Login.css',
        'patterns': [
            r'\.login-',
            r'#g-recaptcha',
        ]
    },
    'Layout': {
        'file': 'frontend/src/components/Layout.css',
        'patterns': [
            r'\.sidebar',
            r'\.main-panel',
            r'\.navbar-',
            r'\.nav',
            r'\.wrapper',
        ]
    },
    'Global': {
        'file': 'frontend/src/index.css',
        'patterns': [
            r'^body',
            r'^h2',
            r'^\.btn',
            r'^\.form-control',
            r'\.tim-icons',
        ]
    }
}

def load_extracted_css():
    """Load the extracted CSS file"""
    if not EXTRACTED_CSS.exists():
        print(f"❌ {EXTRACTED_CSS} not found!")
        return {}
    
    with open(EXTRACTED_CSS, 'r') as f:
        content = f.read()
    
    # Parse CSS into selector -> rules dict
    styles = {}
    current_selector = None
    current_rules = []
    
    for line in content.split('\n'):
        line = line.strip()
        
        if not line or line.startswith('/*'):
            continue
        
        # Selector line
        if line and not line.startswith(' ') and '{' in line:
            if current_selector:
                styles[current_selector] = '\n'.join(current_rules)
            
            current_selector = line.split('{')[0].strip()
            current_rules = []
        
        # Rule line
        elif line and current_selector:
            current_rules.append(line)
    
    # Add last selector
    if current_selector:
        styles[current_selector] = '\n'.join(current_rules)
    
    return styles

def match_selectors(styles, patterns):
    """Match selectors to patterns"""
    matched = {}
    
    for selector, rules in styles.items():
        for pattern in patterns:
            if re.search(pattern, selector, re.IGNORECASE):
                matched[selector] = rules
                break
    
    return matched

def apply_styles_to_component(component_name, component_info, all_styles):
    """Apply matched styles to a component CSS file"""
    filepath = BASE_DIR / component_info['file']
    
    if not filepath.exists():
        print(f"⚠️  {filepath} not found, skipping...")
        return
    
    # Match selectors
    matched = match_selectors(all_styles, component_info['patterns'])
    
    if not matched:
        print(f"  No styles matched for {component_name}")
        return
    
    print(f"  ✅ Found {len(matched)} matched selectors")
    
    # Read existing file
    with open(filepath, 'r') as f:
        existing = f.read()
    
    # Generate new styles section
    new_section = f"\n/* Extracted styles for {component_name} */\n"
    for selector, rules in sorted(matched.items()):
        new_section += f"{selector} {{\n"
        new_section += f"{rules}\n"
        new_section += "}\n\n"
    
    # Append to file (or create new section)
    if "/* Extracted styles" not in existing:
        with open(filepath, 'a') as f:
            f.write(new_section)
        print(f"  ✅ Appended styles to {component_info['file']}")
    else:
        print(f"  ⚠️  Styles already exist in {component_info['file']}, skipping append")

def main():
    """Main function"""
    print("=" * 80)
    print("APPLYING EXTRACTED STYLES TO COMPONENT FILES")
    print("=" * 80)
    print()
    
    # Load extracted styles
    print("Loading extracted CSS...")
    all_styles = load_extracted_css()
    print(f"✅ Loaded {len(all_styles)} selectors")
    print()
    
    # Apply to each component
    print("Applying styles to components...")
    for component_name, component_info in COMPONENT_MAPPING.items():
        print(f"\n{component_name}:")
        apply_styles_to_component(component_name, component_info, all_styles)
    
    print()
    print("=" * 80)
    print("✅ COMPLETE!")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Review updated CSS files")
    print("  2. Test visual match")
    print("  3. Remove any duplicate/conflicting styles")

if __name__ == '__main__':
    main()

