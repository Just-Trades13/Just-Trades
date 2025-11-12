#!/usr/bin/env python3
"""
Analyze HAR file to extract fonts, CSS, JS, and hosting information
"""

import json
import sys
from urllib.parse import urlparse
from collections import defaultdict

def analyze_har(har_file):
    """Analyze HAR file and extract key information"""
    
    with open(har_file, 'r') as f:
        har = json.load(f)
    
    entries = har['log']['entries']
    
    analysis = {
        'fonts': [],
        'css': [],
        'javascript': [],
        'api_calls': [],
        'domains': defaultdict(int),
        'cdn_domains': [],
        'hosting': {},
        'font_faces': []
    }
    
    cdn_patterns = ['cdn', 'cloudflare', 'cloudfront', 'jsdelivr', 'unpkg', 
                   'googleapis', 'fonts', 'bootstrap', 'jquery', 'cdnjs',
                   'fontawesome', 'maxcdn']
    
    for entry in entries:
        request = entry['request']
        response = entry.get('response', {})
        url = request['url']
        parsed = urlparse(url)
        domain = parsed.netloc
        
        analysis['domains'][domain] += 1
        
        # Check if CDN
        is_cdn = any(pattern in domain.lower() for pattern in cdn_patterns)
        if is_cdn:
            analysis['cdn_domains'].append(domain)
        
        mime_type = response.get('content', {}).get('mimeType', '')
        
        # Categorize by type
        if 'font' in mime_type or url.endswith(('.woff', '.woff2', '.ttf', '.otf', '.eot')):
            analysis['fonts'].append({
                'url': url,
                'domain': domain,
                'mime_type': mime_type,
                'size': response.get('content', {}).get('size', 0),
                'is_cdn': is_cdn
            })
            
            # Try to extract font info from headers
            headers = response.get('headers', [])
            for header in headers:
                if header['name'].lower() == 'content-disposition':
                    analysis['fonts'][-1]['filename'] = header['value']
        
        elif 'css' in mime_type or url.endswith('.css'):
            analysis['css'].append({
                'url': url,
                'domain': domain,
                'mime_type': mime_type,
                'size': response.get('content', {}).get('size', 0),
                'is_cdn': is_cdn
            })
            
            # Extract font-face from CSS content
            content = response.get('content', {}).get('text', '')
            if '@font-face' in content:
                # Extract font-face rules
                import re
                font_faces = re.findall(r'@font-face\s*\{[^}]*\}', content, re.DOTALL)
                for ff in font_faces:
                    family_match = re.search(r'font-family:\s*["\']?([^;"\']+)', ff)
                    src_match = re.search(r'src:\s*([^;]+)', ff)
                    if family_match and src_match:
                        analysis['font_faces'].append({
                            'family': family_match.group(1),
                            'src': src_match.group(1),
                            'from_css': url
                        })
        
        elif 'javascript' in mime_type or url.endswith('.js'):
            analysis['javascript'].append({
                'url': url,
                'domain': domain,
                'mime_type': mime_type,
                'size': response.get('content', {}).get('size', 0),
                'is_cdn': is_cdn
            })
        
        elif '/api/' in url or 'api' in domain.lower():
            analysis['api_calls'].append({
                'url': url,
                'method': request['method'],
                'domain': domain,
                'status': response.get('status', 0)
            })
    
    # Determine main hosting
    main_domain = max(analysis['domains'].items(), key=lambda x: x[1])[0]
    analysis['hosting'] = {
        'main_domain': main_domain,
        'total_domains': len(analysis['domains']),
        'cdn_domains': list(set(analysis['cdn_domains'])),
        'unique_domains': list(analysis['domains'].keys())
    }
    
    return analysis

def print_analysis(analysis):
    """Print formatted analysis"""
    print("=" * 80)
    print("HAR FILE ANALYSIS")
    print("=" * 80)
    
    print(f"\n📡 HOSTING:")
    print(f"   Main Domain: {analysis['hosting']['main_domain']}")
    print(f"   Total Domains: {analysis['hosting']['total_domains']}")
    print(f"   CDN Domains: {len(analysis['hosting']['cdn_domains'])}")
    for cdn in analysis['hosting']['cdn_domains']:
        print(f"      - {cdn}")
    
    print(f"\n🔤 FONTS:")
    print(f"   Total Font Files: {len(analysis['fonts'])}")
    for font in analysis['fonts']:
        print(f"   - {font['url']}")
        print(f"     Domain: {font['domain']}")
        print(f"     Size: {font['size']} bytes")
        print(f"     CDN: {font['is_cdn']}")
    
    print(f"\n📝 @FONT-FACE RULES:")
    print(f"   Total: {len(analysis['font_faces'])}")
    for ff in analysis['font_faces']:
        print(f"   - Family: {ff['family']}")
        print(f"     Source: {ff['src']}")
        print(f"     From CSS: {ff['from_css']}")
    
    print(f"\n🎨 CSS:")
    print(f"   Total Stylesheets: {len(analysis['css'])}")
    for css in analysis['css'][:10]:  # Show first 10
        print(f"   - {css['url']}")
    
    print(f"\n📜 JAVASCRIPT:")
    print(f"   Total Scripts: {len(analysis['javascript'])}")
    for js in analysis['javascript'][:10]:  # Show first 10
        print(f"   - {js['url']}")
    
    print(f"\n🔌 API CALLS:")
    print(f"   Total: {len(analysis['api_calls'])}")
    for api in analysis['api_calls'][:20]:  # Show first 20
        print(f"   - {api['method']} {api['url']} ({api['status']})")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 ANALYZE_HAR.py <har_file_path>")
        print("\nExample:")
        print("  python3 ANALYZE_HAR.py trademanager.har")
        sys.exit(1)
    
    har_file = sys.argv[1]
    
    try:
        analysis = analyze_har(har_file)
        print_analysis(analysis)
        
        # Save detailed analysis
        output_file = har_file.replace('.har', '_analysis.json')
        with open(output_file, 'w') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"\n✅ Detailed analysis saved to: {output_file}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

