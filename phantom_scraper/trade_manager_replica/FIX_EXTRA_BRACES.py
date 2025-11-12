#!/usr/bin/env python3
"""
Fix extra closing braces in CSS files added by the extraction script
"""

from pathlib import Path
import re

BASE_DIR = Path(__file__).parent

CSS_FILES = [
    "frontend/src/index.css",
    "frontend/src/pages/MyRecorders.css",
    "frontend/src/pages/CreateStrategy.css",
    "frontend/src/pages/ControlCenter.css",
    "frontend/src/pages/AccountManagement.css",
    "frontend/src/pages/Settings.css",
    "frontend/src/pages/Login.css",
    "frontend/src/components/Layout.css",
]

def fix_extra_braces(filepath):
    """Remove extra closing braces after CSS rules"""
    full_path = BASE_DIR / filepath
    
    if not full_path.exists():
        return 0
    
    with open(full_path, 'r') as f:
        content = f.read()
    
    # Pattern: find lines that are just "}" followed by another "}" on the next line
    # This happens when the extraction script adds an extra brace
    lines = content.split('\n')
    fixed_lines = []
    removed_count = 0
    i = 0
    
    while i < len(lines):
        current = lines[i].strip()
        # Check if this is a closing brace and next line is also a closing brace
        if current == '}' and i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line == '}':
                # Skip the extra brace
                fixed_lines.append(lines[i])
                i += 2  # Skip both braces, but we only add one
                removed_count += 1
                continue
        
        fixed_lines.append(lines[i])
        i += 1
    
    if removed_count > 0:
        with open(full_path, 'w') as f:
            f.write('\n'.join(fixed_lines))
        print(f"  ✅ Fixed {filepath}: Removed {removed_count} extra braces")
        return removed_count
    
    return 0

def main():
    """Main function"""
    print("=" * 80)
    print("FIXING EXTRA CLOSING BRACES IN CSS FILES")
    print("=" * 80)
    print()
    
    total_removed = 0
    
    for css_file in CSS_FILES:
        removed = fix_extra_braces(css_file)
        total_removed += removed
    
    print()
    print("=" * 80)
    print(f"✅ COMPLETE! Removed {total_removed} extra braces total")
    print("=" * 80)

if __name__ == '__main__':
    main()

