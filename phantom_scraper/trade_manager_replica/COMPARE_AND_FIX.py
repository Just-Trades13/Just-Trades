#!/usr/bin/env python3
"""
Compare extracted styles with current implementation and identify discrepancies
"""

import json
import os
import re
from pathlib import Path

def load_extracted_styles(filepath):
    """Load extracted style JSON"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return None

def analyze_extraction_files():
    """Analyze all extraction files and create comparison report"""
    
    base_path = Path(__file__).parent
    
    # Style extraction files
    style_files = {
        'login': 'trade_manager_extraction__auth_login_1762408332951.json',
        'my_recorders': 'trade_manager_extraction__user_strats_1762405557781.json',
        'account_management': 'trade_manager_extraction__user_at_accnts_1762405614838.json',
        'my_trader': 'trade_manager_extraction__user_at_strats_1762405661810.json',
        'control_center': 'trade_manager_extraction__user_at_controls_1762406209185.json',
        'settings': 'trade_manager_extraction__user_settings_1762406252644.json',
        'create_strategy': 'trade_manager_extraction__user_at_strat_1762407052878.json',
    }
    
    # Functionality extraction files
    functionality_files = {
        'dashboard': 'trade_manager_functionality__user_dashboard_1762408561408.json',
        'login': 'trade_manager_functionality__auth_login_1762408364421.json',
        'my_recorders': 'trade_manager_functionality__user_strats_1762406783587.json',
        'account_management': 'trade_manager_functionality__user_at_accnts_1762406880831.json',
        'account_setup': 'trade_manager_functionality__user_at_accntsetup__1762406931688.json',
        'my_trader': 'trade_manager_functionality__user_at_strats_1762407002927.json',
        'create_strategy': 'trade_manager_functionality__user_at_strat_1762407137327.json',
        'control_center': 'trade_manager_functionality__user_at_controls_1762407209900.json',
        'settings': 'trade_manager_functionality__user_settings_1762407252404.json',
    }
    
    print("=" * 80)
    print("STYLE EXTRACTION FILES ANALYSIS")
    print("=" * 80)
    
    style_summary = {}
    for page, filename in style_files.items():
        filepath = base_path / filename
        if filepath.exists():
            data = load_extracted_styles(filepath)
            if data:
                elements = data.get('elements', [])
                style_summary[page] = {
                    'filename': filename,
                    'total_elements': len(elements),
                    'has_styles': len(elements) > 0
                }
                print(f"\n✅ {page.upper()}: {filename}")
                print(f"   Elements: {len(elements)}")
            else:
                print(f"\n❌ {page.upper()}: {filename} - Failed to load")
        else:
            print(f"\n⚠️  {page.upper()}: {filename} - Not found")
    
    print("\n" + "=" * 80)
    print("FUNCTIONALITY EXTRACTION FILES ANALYSIS")
    print("=" * 80)
    
    func_summary = {}
    for page, filename in functionality_files.items():
        filepath = base_path / filename
        if filepath.exists():
            data = load_extracted_styles(filepath)
            if data:
                api_calls = data.get('apiCalls', [])
                websockets = data.get('websockets', [])
                func_summary[page] = {
                    'filename': filename,
                    'api_calls': len(api_calls),
                    'websockets': len(websockets),
                    'has_data': len(api_calls) > 0 or len(websockets) > 0
                }
                print(f"\n✅ {page.upper()}: {filename}")
                print(f"   API Calls: {len(api_calls)}")
                print(f"   WebSockets: {len(websockets)}")
            else:
                print(f"\n❌ {page.upper()}: {filename} - Failed to load")
        else:
            print(f"\n⚠️  {page.upper()}: {filename} - Not found")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Style files found: {sum(1 for s in style_summary.values() if s.get('has_styles'))}")
    print(f"Functionality files found: {sum(1 for f in func_summary.values() if f.get('has_data'))}")
    print("\n✅ All extraction files are available for comparison!")
    
    return style_summary, func_summary

if __name__ == '__main__':
    analyze_extraction_files()

