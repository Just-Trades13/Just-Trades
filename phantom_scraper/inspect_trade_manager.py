#!/usr/bin/env python3
"""
Trade Manager Architecture Inspector

This script helps you inspect Trade Manager's architecture by:
1. Parsing HAR files to extract API endpoints
2. Analyzing network traffic patterns
3. Identifying separate services
4. Generating architecture documentation
"""

import json
import sys
from collections import defaultdict
from typing import Dict, List, Set
from urllib.parse import urlparse

def parse_har_file(har_path: str) -> Dict:
    """Parse HAR file and return structured data"""
    try:
        with open(har_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ HAR file not found: {har_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing HAR file: {e}")
        sys.exit(1)

def extract_endpoints(har_data: Dict) -> Dict[str, Set[str]]:
    """Extract all API endpoints from HAR file"""
    endpoints = defaultdict(set)
    
    for entry in har_data.get('log', {}).get('entries', []):
        request = entry.get('request', {})
        url = request.get('url', '')
        method = request.get('method', 'GET')
        
        parsed = urlparse(url)
        path = parsed.path
        
        # Categorize endpoints
        if '/api/' in path:
            endpoints['api'].add(f"{method} {path}")
        elif path.startswith('/ws/') or 'websocket' in path.lower():
            endpoints['websocket'].add(path)
        elif '/static/' in path:
            endpoints['static'].add(path)
        else:
            endpoints['other'].add(path)
    
    return endpoints

def analyze_servers(har_data: Dict) -> Dict[str, Set[str]]:
    """Analyze server headers to identify different services"""
    servers = defaultdict(set)
    
    for entry in har_data.get('log', {}).get('entries', []):
        response = entry.get('response', {})
        headers = response.get('headers', [])
        
        for header in headers:
            if header.get('name', '').lower() == 'server':
                server = header.get('value', '')
                url = entry.get('request', {}).get('url', '')
                servers[server].add(urlparse(url).netloc)
    
    return servers

def analyze_websocket_connections(har_data: Dict) -> List[Dict]:
    """Find WebSocket connections"""
    ws_connections = []
    
    for entry in har_data.get('log', {}).get('entries', []):
        request = entry.get('request', {})
        url = request.get('url', '')
        
        # Check for WebSocket upgrade headers
        headers = request.get('headers', [])
        has_upgrade = any(
            h.get('name', '').lower() == 'upgrade' and 
            'websocket' in h.get('value', '').lower()
            for h in headers
        )
        
        if has_upgrade or 'ws://' in url or 'wss://' in url:
            ws_connections.append({
                'url': url,
                'method': request.get('method'),
                'headers': {h['name']: h['value'] for h in headers}
            })
    
    return ws_connections

def analyze_authentication(har_data: Dict) -> Dict:
    """Analyze authentication patterns"""
    auth_info = {
        'csrf_tokens': set(),
        'session_cookies': set(),
        'auth_endpoints': set(),
        'auth_headers': set()
    }
    
    for entry in har_data.get('log', {}).get('entries', []):
        request = entry.get('request', {})
        url = request.get('url', '')
        path = urlparse(url).path
        
        # Check for auth endpoints
        if '/auth/' in path or '/login' in path:
            auth_info['auth_endpoints'].add(path)
        
        # Check headers for auth tokens
        headers = request.get('headers', [])
        for header in headers:
            name = header.get('name', '').lower()
            value = header.get('value', '')
            
            if 'csrf' in name or 'xsrf' in name:
                auth_info['csrf_tokens'].add(f"{name}: {value[:20]}...")
            if 'authorization' in name:
                auth_info['auth_headers'].add(f"{name}: {value[:20]}...")
        
        # Check cookies
        cookies = request.get('cookies', [])
        for cookie in cookies:
            name = cookie.get('name', '').lower()
            if 'session' in name or 'token' in name:
                auth_info['session_cookies'].add(name)
    
    return auth_info

def generate_report(har_path: str):
    """Generate comprehensive architecture report"""
    print("=" * 80)
    print("🔍 Trade Manager Architecture Inspector")
    print("=" * 80)
    print()
    
    # Parse HAR file
    print(f"📂 Parsing HAR file: {har_path}")
    har_data = parse_har_file(har_path)
    print(f"✅ Found {len(har_data.get('log', {}).get('entries', []))} network entries")
    print()
    
    # Extract endpoints
    print("📊 API Endpoints Analysis")
    print("-" * 80)
    endpoints = extract_endpoints(har_data)
    
    print(f"\n🔌 API Endpoints ({len(endpoints['api'])}):")
    for endpoint in sorted(endpoints['api']):
        print(f"   {endpoint}")
    
    if endpoints['websocket']:
        print(f"\n🔌 WebSocket Connections ({len(endpoints['websocket'])}):")
        for ws in sorted(endpoints['websocket']):
            print(f"   {ws}")
    
    print()
    
    # Analyze servers
    print("🖥️  Server Analysis")
    print("-" * 80)
    servers = analyze_servers(har_data)
    
    for server, domains in servers.items():
        print(f"\n📡 Server: {server}")
        for domain in sorted(domains):
            print(f"   - {domain}")
    
    print()
    
    # WebSocket analysis
    print("🔌 WebSocket Analysis")
    print("-" * 80)
    ws_connections = analyze_websocket_connections(har_data)
    
    if ws_connections:
        print(f"Found {len(ws_connections)} WebSocket connections:")
        for i, ws in enumerate(ws_connections, 1):
            print(f"\n   Connection {i}:")
            print(f"   URL: {ws['url']}")
            print(f"   Method: {ws['method']}")
    else:
        print("   No WebSocket connections found in HAR file")
        print("   (WebSocket connections may not be captured in HAR)")
    
    print()
    
    # Authentication analysis
    print("🔐 Authentication Analysis")
    print("-" * 80)
    auth = analyze_authentication(har_data)
    
    if auth['auth_endpoints']:
        print(f"\n🔑 Auth Endpoints:")
        for endpoint in sorted(auth['auth_endpoints']):
            print(f"   - {endpoint}")
    
    if auth['csrf_tokens']:
        print(f"\n🔑 CSRF Tokens Found: {len(auth['csrf_tokens'])}")
        for token in list(auth['csrf_tokens'])[:3]:  # Show first 3
            print(f"   - {token}")
    
    if auth['session_cookies']:
        print(f"\n🍪 Session Cookies:")
        for cookie in sorted(auth['session_cookies']):
            print(f"   - {cookie}")
    
    print()
    
    # Summary
    print("📋 Summary")
    print("-" * 80)
    print(f"Total API Endpoints: {len(endpoints['api'])}")
    print(f"WebSocket Connections: {len(endpoints['websocket'])}")
    print(f"Different Servers: {len(servers)}")
    print(f"Auth Endpoints: {len(auth['auth_endpoints'])}")
    print()
    
    # Recommendations
    print("💡 Recommendations")
    print("-" * 80)
    print("1. Use browser DevTools Network tab for real-time inspection")
    print("2. Filter by 'WS' to see WebSocket connections")
    print("3. Check 'Response Headers' for server identification")
    print("4. Look for different subdomains (may indicate separate services)")
    print("5. Monitor WebSocket messages in DevTools for event types")
    print()
    
    print("=" * 80)
    print("✅ Analysis Complete")
    print("=" * 80)

if __name__ == "__main__":
    har_path = "trademanagergroup.com.har"
    
    if len(sys.argv) > 1:
        har_path = sys.argv[1]
    
    generate_report(har_path)

