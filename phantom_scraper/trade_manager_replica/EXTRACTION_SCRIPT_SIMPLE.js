// ============================================
// SIMPLE TRADE MANAGER EXTRACTION SCRIPT
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

function extractStyles() {
    const allElements = document.querySelectorAll('*');
    const styles = {};
    allElements.forEach((el, index) => {
        if (el.id || el.className) {
            const className = typeof el.className === 'string' ? el.className : (el.className.baseVal || String(el.className) || '');
            const selector = el.id ? '#' + el.id : (className ? '.' + className.split(' ')[0] : '');
            if (!selector) return;
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
        const rect = el.getBoundingClientRect();
        const className = typeof el.className === 'string' ? el.className : (el.className.baseVal || String(el.className) || '');
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
    });
    extractionData.measurements = measurements;
    console.log('✅ Measurements extracted');
}

function extractElements() {
    const elements = {};
    const header = document.querySelector('h2, .dashboard-header, [class*="header"]');
    if (header) {
        const headerStyles = window.getComputedStyle(header);
        elements.header = {
            text: header.textContent.trim(),
            tag: header.tagName,
            classes: header.className,
            color: headerStyles.color,
            fontSize: headerStyles.fontSize,
            fontWeight: headerStyles.fontWeight,
            fontFamily: headerStyles.fontFamily,
            margin: headerStyles.margin,
            padding: headerStyles.padding
        };
    }
    document.querySelectorAll('button, .btn, [class*="button"]').forEach((btn, i) => {
        const btnStyles = window.getComputedStyle(btn);
        elements['button_' + i] = {
            text: btn.textContent.trim(),
            classes: btn.className,
            backgroundColor: btnStyles.backgroundColor,
            color: btnStyles.color,
            fontSize: btnStyles.fontSize,
            padding: btnStyles.padding,
            borderRadius: btnStyles.borderRadius
        };
    });
    document.querySelectorAll('[class*="card"], [class*="summary"]').forEach((card, i) => {
        const cardStyles = window.getComputedStyle(card);
        elements['card_' + i] = {
            text: card.textContent.trim().substring(0, 100),
            classes: card.className,
            backgroundColor: cardStyles.backgroundColor,
            background: cardStyles.background,
            padding: cardStyles.padding,
            borderRadius: cardStyles.borderRadius,
            boxShadow: cardStyles.boxShadow,
            border: cardStyles.border
        };
    });
    document.querySelectorAll('table').forEach((table, i) => {
        const tableStyles = window.getComputedStyle(table);
        elements['table_' + i] = {
            headers: Array.from(table.querySelectorAll('th')).map(th => th.textContent.trim()),
            rowCount: table.querySelectorAll('tr').length,
            classes: table.className,
            color: tableStyles.color,
            fontSize: tableStyles.fontSize
        };
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
        if (url.includes('/api/')) {
            var self = this;
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
    console.log('✅ Data exported!');
}

extractEverything();

window.extractTradeManager = {
    extract: extractEverything,
    export: exportData,
    data: extractionData
};

console.log('✅ Extraction script loaded!');
console.log('📋 Use window.extractTradeManager.export() to download data');

