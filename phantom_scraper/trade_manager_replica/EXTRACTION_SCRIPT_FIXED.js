// ============================================
// FIXED TRADE MANAGER EXTRACTION SCRIPT
// Copy and paste ALL of this into browser console
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

// Helper function to safely get className
function getClassName(el) {
    if (!el.className) return '';
    if (typeof el.className === 'string') return el.className;
    if (el.className.baseVal) return el.className.baseVal;
    return String(el.className);
}

function extractStyles() {
    const allElements = document.querySelectorAll('*');
    const styles = {};
    allElements.forEach((el, index) => {
        try {
            const className = getClassName(el);
            if (!el.id && !className) return;
            
            const selector = el.id ? '#' + el.id : '.' + className.split(' ')[0];
            if (!selector || selector === '.') return;
            
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
                display: computed.display
            };
        } catch(e) {
            // Skip elements that cause errors
        }
    });
    extractionData.styles = styles;
    console.log('✅ Styles extracted');
}

function extractMeasurements() {
    const measurements = {
        viewport: {
            width: window.innerWidth,
            height: window.innerHeight
        },
        elements: {}
    };
    document.querySelectorAll('[class], [id]').forEach(el => {
        try {
            const rect = el.getBoundingClientRect();
            const className = getClassName(el);
            const selector = el.id || (className ? className.split(' ')[0] : '');
            if (!selector) return;
            
            measurements.elements[selector] = {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
                top: rect.top,
                left: rect.left
            };
        } catch(e) {
            // Skip elements that cause errors
        }
    });
    extractionData.measurements = measurements;
    console.log('✅ Measurements extracted');
}

function extractElements() {
    const elements = {};
    
    // Dashboard specific
    const header = document.querySelector('h2, .dashboard-header, [class*="header"]');
    if (header) {
        try {
            const headerStyles = window.getComputedStyle(header);
            elements.header = {
                text: header.textContent.trim(),
                tag: header.tagName,
                classes: getClassName(header),
                color: headerStyles.color,
                fontSize: headerStyles.fontSize,
                fontWeight: headerStyles.fontWeight,
                fontFamily: headerStyles.fontFamily,
                margin: headerStyles.margin,
                padding: headerStyles.padding
            };
        } catch(e) {
            console.log('Error extracting header:', e);
        }
    }
    
    // Buttons
    document.querySelectorAll('button, .btn, [class*="button"]').forEach((btn, i) => {
        try {
            const btnStyles = window.getComputedStyle(btn);
            elements['button_' + i] = {
                text: btn.textContent.trim(),
                classes: getClassName(btn),
                backgroundColor: btnStyles.backgroundColor,
                color: btnStyles.color,
                fontSize: btnStyles.fontSize,
                padding: btnStyles.padding,
                borderRadius: btnStyles.borderRadius
            };
        } catch(e) {
            // Skip this button
        }
    });
    
    // Cards
    document.querySelectorAll('[class*="card"], [class*="summary"]').forEach((card, i) => {
        try {
            const cardStyles = window.getComputedStyle(card);
            elements['card_' + i] = {
                text: card.textContent.trim().substring(0, 100),
                classes: getClassName(card),
                backgroundColor: cardStyles.backgroundColor,
                background: cardStyles.background,
                padding: cardStyles.padding,
                borderRadius: cardStyles.borderRadius,
                boxShadow: cardStyles.boxShadow,
                border: cardStyles.border
            };
        } catch(e) {
            // Skip this card
        }
    });
    
    // Tables
    document.querySelectorAll('table').forEach((table, i) => {
        try {
            const tableStyles = window.getComputedStyle(table);
            elements['table_' + i] = {
                headers: Array.from(table.querySelectorAll('th')).map(th => th.textContent.trim()),
                rowCount: table.querySelectorAll('tr').length,
                classes: getClassName(table),
                color: tableStyles.color,
                fontSize: tableStyles.fontSize
            };
        } catch(e) {
            // Skip this table
        }
    });
    
    extractionData.elements = elements;
    console.log('✅ Elements extracted');
}

function monitorAPICalls() {
    const originalFetch = window.fetch;
    window.fetch = function() {
        const args = Array.from(arguments);
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
                }).catch(function() {});
                return response;
            });
        }
        return originalFetch.apply(this, args);
    };
    
    const originalXHR = window.XMLHttpRequest.prototype.open;
    window.XMLHttpRequest.prototype.open = function(method, url) {
        if (url && url.includes && url.includes('/api/')) {
            const self = this;
            this.addEventListener('load', function() {
                try {
                    const data = JSON.parse(self.responseText);
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
        return originalXHR.apply(this, arguments);
    };
    console.log('✅ API monitoring active');
}

function extractEverything() {
    console.log('🚀 Starting complete extraction...');
    extractStyles();
    extractMeasurements();
    extractElements();
    monitorAPICalls();
    console.log('✅ Extraction complete!');
    return extractionData;
}

function exportData() {
    const dataStr = JSON.stringify(extractionData, null, 2);
    const blob = new Blob([dataStr], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'trade_manager_extraction_' + window.location.pathname.replace(/\//g, '_') + '_' + Date.now() + '.json';
    a.click();
    console.log('✅ Data exported! File downloaded to your Downloads folder');
}

// Run extraction
extractEverything();

// Make available globally
window.extractTradeManager = {
    extract: extractEverything,
    export: exportData,
    data: extractionData
};

console.log('✅ Extraction script loaded!');
console.log('📋 On each page, type: window.extractTradeManager.export()');

