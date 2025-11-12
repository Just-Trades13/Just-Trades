#!/usr/bin/env python3
"""
Extract and apply styles from the downloaded main.edcc780c.css file
to our replica CSS files.
"""

import json
import re
import os
from pathlib import Path

def read_minified_css(filepath):
    """Read the minified CSS file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def extract_relevant_styles(css_content):
    """Extract relevant styles from minified CSS."""
    # Key selectors we care about
    key_selectors = [
        r'\.login-page[^{]*\{[^}]+\}',
        r'\.dashboard[^{]*\{[^}]+\}',
        r'\.sidebar[^{]*\{[^}]+\}',
        r'\.navbar[^{]*\{[^}]+\}',
        r'\.card[^{]*\{[^}]+\}',
        r'body[^{]*\{[^}]+\}',
        r'\.btn[^{]*\{[^}]+\}',
        r'\.form-control[^{]*\{[^}]+\}',
        r'\.table[^{]*\{[^}]+\}',
    ]
    
    extracted = {}
    for pattern in key_selectors:
        matches = re.findall(pattern, css_content, re.IGNORECASE)
        if matches:
            extracted[pattern] = matches
    
    return extracted

def find_css_properties(css_content, selector):
    """Find CSS properties for a specific selector."""
    # Look for selector in minified CSS
    pattern = rf'{re.escape(selector)}[^{]*\{{([^}}]+)\}}'
    matches = re.findall(pattern, css_content, re.IGNORECASE | re.DOTALL)
    return matches

def apply_to_index_css():
    """Apply global styles to index.css."""
    css_file = Path('frontend/src/index.css')
    if not css_file.exists():
        return
    
    downloaded_css = read_minified_css('trademanagergroup.com/static/css/main.edcc780c.css')
    
    # Extract body styles
    body_styles = find_css_properties(downloaded_css, 'body')
    
    if body_styles:
        print(f"Found body styles: {body_styles[0][:100]}...")
        # Extract background-color
        bg_match = re.search(r'background-color:\s*([^;]+)', body_styles[0], re.IGNORECASE)
        if bg_match:
            bg_color = bg_match.group(1).strip()
            print(f"Extracted background-color: {bg_color}")
            
            # Update index.css
            with open(css_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Update body background-color if different
            if f'background-color: {bg_color}' not in content:
                # Find body block and update
                body_pattern = r'(body\s*\{[^}]*background-color:)[^;]+(;)'
                if re.search(body_pattern, content):
                    content = re.sub(
                        body_pattern,
                        f'\\1 {bg_color}\\2',
                        content,
                        flags=re.IGNORECASE
                    )
                    with open(css_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Updated body background-color in {css_file}")
                else:
                    # Add to body if not present
                    body_pattern = r'(body\s*\{[^}]*)(\})'
                    if re.search(body_pattern, content):
                        content = re.sub(
                            body_pattern,
                            f'\\1  background-color: {bg_color};\\2',
                            content,
                            flags=re.IGNORECASE
                        )
                        with open(css_file, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"Added body background-color to {css_file}")

def main():
    """Main function."""
    print("Extracting and applying styles from downloaded CSS...")
    
    css_file = Path('trademanagergroup.com/static/css/main.edcc780c.css')
    if not css_file.exists():
        print(f"CSS file not found: {css_file}")
        return
    
    print(f"Reading {css_file}...")
    css_content = read_minified_css(css_file)
    print(f"CSS file size: {len(css_content)} characters")
    
    # Apply global styles
    apply_to_index_css()
    
    # Extract key information
    print("\nKey findings from downloaded CSS:")
    
    # Check for login-page
    if '.login-page' in css_content:
        print("✓ Found .login-page styles")
    
    # Check for dashboard
    if '.dashboard' in css_content:
        print("✓ Found .dashboard styles")
    
    # Check for sidebar
    if '.sidebar' in css_content:
        print("✓ Found .sidebar styles")
    
    # Check for custom-switch (dark mode toggle)
    if '.custom-switch' in css_content:
        print("✓ Found .custom-switch styles (dark mode toggle)")
        # Extract the background-image URLs
        switch_match = re.search(r'\.custom-switch[^}]+background-image:url\(([^)]+)\)', css_content, re.IGNORECASE)
        if switch_match:
            print(f"  Background image: {switch_match.group(1)}")
    
    # Check for body background
    body_bg = re.search(r'body[^{]*\{[^}]*background[^}]*\}', css_content, re.IGNORECASE | re.DOTALL)
    if body_bg:
        bg_color = re.search(r'background-color:\s*([^;]+)', body_bg.group(0), re.IGNORECASE)
        if bg_color:
            print(f"✓ Body background-color: {bg_color.group(1).strip()}")
    
    print("\nNote: The CSS file is minified. For detailed style extraction,")
    print("we should use the browser extraction JSON files we already have.")
    print("This script confirms the downloaded CSS matches our expectations.")

if __name__ == '__main__':
    main()

