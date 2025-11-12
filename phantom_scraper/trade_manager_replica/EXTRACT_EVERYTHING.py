#!/usr/bin/env python3
"""
Complete Extraction Tool for Trade Manager
Extracts ALL styles, measurements, API responses, and functionality
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any
import base64

class TradeManagerExtractor:
    """Extract everything from Trade Manager site"""
    
    def __init__(self, har_file_path: str = None):
        self.har_file_path = har_file_path
        self.extracted_data = {
            "pages": {},
            "api_responses": {},
            "styles": {},
            "measurements": {},
            "functionality": {}
        }
    
    def extract_from_har(self):
        """Extract API responses from HAR file"""
        if not self.har_file_path or not Path(self.har_file_path).exists():
            print("⚠️  No HAR file found")
            return
        
        print("📡 Extracting API responses from HAR file...")
        
        with open(self.har_file_path, 'r', encoding='utf-8') as f:
            har_data = json.load(f)
        
        for entry in har_data.get('log', {}).get('entries', []):
            request = entry.get('request', {})
            response = entry.get('response', {})
            url = request.get('url', '')
            
            # Only capture API endpoints
            if '/api/' in url:
                api_path = self._extract_api_path(url)
                if api_path:
                    content = response.get('content', {})
                    text = content.get('text', '')
                    
                    # Try to parse JSON
                    try:
                        if content.get('encoding') == 'base64':
                            text = base64.b64decode(text).decode('utf-8')
                        data = json.loads(text)
                        self.extracted_data['api_responses'][api_path] = {
                            'method': request.get('method', 'GET'),
                            'url': url,
                            'status': response.get('status', 0),
                            'response': data,
                            'headers': response.get('headers', [])
                        }
                        print(f"✅ Extracted: {api_path}")
                    except:
                        pass
    
    def _extract_api_path(self, url: str) -> str:
        """Extract API path from full URL"""
        match = re.search(r'/api/([^?]+)', url)
        if match:
            return match.group(1)
        return None
    
    def generate_extraction_guide(self):
        """Generate browser console script to extract everything"""
        script = """
// ============================================
// COMPLETE TRADE MANAGER EXTRACTION SCRIPT
// Run this in browser console on trademanagergroup.com
// ============================================

const extractionData = {
    timestamp: new Date().toISOString(),
    url: window.location.href,
    page: window.location.pathname,
    styles: {},
    measurements: {},
    elements: {},
    apiCalls: []
};

// 1. Extract all computed styles from page
function extractStyles() {
    const allElements = document.querySelectorAll('*');
    const styles = {};
    
    allElements.forEach((el, index) => {
        if (el.id || el.className) {
            const selector = el.id ? `#${el.id}` : `.${el.className.split(' ')[0]}`;
            const computed = window.getComputedStyle(el);
            
            styles[selector] = {
                backgroundColor: computed.backgroundColor,
                color: computed.color,
                fontSize: computed.fontSize,
                fontWeight: computed.fontWeight,
                fontFamily: computed.fontFamily,
                padding: computed.padding,
                margin: computed.margin,
                width: computed.width,
                height: computed.height,
                borderRadius: computed.borderRadius,
                boxShadow: computed.boxShadow,
                border: computed.border,
                display: computed.display,
                position: computed.position,
                top: computed.top,
                left: computed.left,
                right: computed.right,
                bottom: computed.bottom
            };
        }
    });
    
    extractionData.styles = styles;
    console.log('✅ Styles extracted');
}

// 2. Extract measurements
function extractMeasurements() {
    const measurements = {
        viewport: {
            width: window.innerWidth,
            height: window.innerHeight
        },
        elements: {}
    };
    
    document.querySelectorAll('[class], [id]').forEach(el => {
        const rect = el.getBoundingClientRect();
        const selector = el.id || el.className.split(' ')[0];
        measurements.elements[selector] = {
            x: rect.x,
            y: rect.y,
            width: rect.width,
            height: rect.height,
            top: rect.top,
            left: rect.left,
            right: rect.right,
            bottom: rect.bottom
        };
    });
    
    extractionData.measurements = measurements;
    console.log('✅ Measurements extracted');
}

// 3. Extract element information
function extractElements() {
    const elements = {};
    
    // Dashboard specific
    const header = document.querySelector('h2, .dashboard-header, [class*="header"]');
    if (header) {
        elements.header = {
            text: header.textContent.trim(),
            tag: header.tagName,
            classes: header.className,
            styles: window.getComputedStyle(header)
        };
    }
    
    // Buttons
    document.querySelectorAll('button, .btn, [class*="button"]').forEach((btn, i) => {
        elements[`button_${i}`] = {
            text: btn.textContent.trim(),
            classes: btn.className,
            styles: window.getComputedStyle(btn)
        };
    });
    
    // Cards
    document.querySelectorAll('[class*="card"], [class*="summary"]').forEach((card, i) => {
        elements[`card_${i}`] = {
            text: card.textContent.trim().substring(0, 100),
            classes: card.className,
            styles: window.getComputedStyle(card)
        };
    });
    
    // Tables
    document.querySelectorAll('table').forEach((table, i) => {
        elements[`table_${i}`] = {
            headers: Array.from(table.querySelectorAll('th')).map(th => th.textContent.trim()),
            rowCount: table.querySelectorAll('tr').length,
            classes: table.className,
            styles: window.getComputedStyle(table)
        };
    });
    
    extractionData.elements = elements;
    console.log('✅ Elements extracted');
}

// 4. Monitor API calls
function monitorAPICalls() {
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        const url = args[0];
        if (typeof url === 'string' && url.includes('/api/')) {
            return originalFetch.apply(this, args).then(response => {
                response.clone().json().then(data => {
                    extractionData.apiCalls.push({
                        url: url,
                        method: 'GET',
                        response: data,
                        timestamp: new Date().toISOString()
                    });
                    console.log('📡 API call captured:', url);
                }).catch(() => {});
                return response;
            });
        }
        return originalFetch.apply(this, args);
    };
    
    // Also monitor XMLHttpRequest
    const originalXHR = window.XMLHttpRequest.prototype.open;
    window.XMLHttpRequest.prototype.open = function(method, url, ...args) {
        if (url.includes('/api/')) {
            this.addEventListener('load', function() {
                try {
                    const data = JSON.parse(this.responseText);
                    extractionData.apiCalls.push({
                        url: url,
                        method: method,
                        response: data,
                        timestamp: new Date().toISOString()
                    });
                    console.log('📡 API call captured:', url);
                } catch(e) {}
            });
        }
        return originalXHR.apply(this, [method, url, ...args]);
    };
    
    console.log('✅ API monitoring active');
}

// 5. Run all extractions
function extractEverything() {
    console.log('🚀 Starting complete extraction...');
    extractStyles();
    extractMeasurements();
    extractElements();
    monitorAPICalls();
    console.log('✅ Extraction complete!');
    console.log('📋 Data:', extractionData);
    return extractionData;
}

// 6. Export function
function exportData() {
    const dataStr = JSON.stringify(extractionData, null, 2);
    const blob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trade_manager_extraction_${window.location.pathname.replace(/\//g, '_')}_${Date.now()}.json`;
    a.click();
    console.log('✅ Data exported!');
}

// Auto-run
extractEverything();

// Export functions to window for manual use
window.extractTradeManager = {
    extract: extractEverything,
    export: exportData,
    data: extractionData
};

console.log('✅ Extraction script loaded!');
console.log('📋 Use window.extractTradeManager.export() to download data');
"""
        return script
    
    def save_extraction_script(self, output_path: str = "extract_from_browser.js"):
        """Save browser extraction script"""
        script = self.generate_extraction_guide()
        with open(output_path, 'w') as f:
            f.write(script)
        print(f"✅ Extraction script saved to: {output_path}")
        return output_path

if __name__ == '__main__':
    extractor = TradeManagerExtractor(
        har_file_path="../trademanagergroup.com.har"
    )
    
    # Extract from HAR
    extractor.extract_from_har()
    
    # Generate browser script
    script_path = extractor.save_extraction_script()
    
    # Save extracted data
    with open('extracted_data.json', 'w') as f:
        json.dump(extractor.extracted_data, f, indent=2)
    
    print("\n✅ Extraction complete!")
    print(f"📋 Browser script: {script_path}")
    print(f"📋 Extracted data: extracted_data.json")
    print("\n📝 Next steps:")
    print("1. Open trademanagergroup.com in browser")
    print("2. Open browser console (F12)")
    print(f"3. Copy/paste contents of {script_path}")
    print("4. Navigate to each page and run: window.extractTradeManager.export()")
    print("5. Share the downloaded JSON files with me!")

