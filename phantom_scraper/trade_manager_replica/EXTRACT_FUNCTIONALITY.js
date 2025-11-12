// ============================================
// COMPREHENSIVE FUNCTIONALITY EXTRACTION SCRIPT
// ============================================
// This script extracts:
// - All API calls (fetch, XMLHttpRequest)
// - WebSocket connections
// - Event listeners
// - Form submissions
// - Component interactions
// - Data flows
// - Network requests/responses

(function() {
  'use strict';
  
  // Prevent duplicate execution
  if (window.functionalityExtractionActive) {
    console.log('⚠️ Extraction already running! Refresh page to restart.');
    return;
  }
  
  window.functionalityExtractionActive = true;
  console.log('🚀 Starting functionality extraction...');
  
  const extractionData = {
    timestamp: new Date().toISOString(),
    url: window.location.href,
    page: window.location.pathname,
    apiCalls: [],
    websockets: [],
    eventListeners: [],
    formSubmissions: [],
    componentData: {},
    networkRequests: [],
    localStorage: {},
    sessionStorage: {},
    cookies: {}
  };
  
  // ============================================
  // 1. INTERCEPT FETCH REQUESTS
  // ============================================
  const originalFetch = window.fetch;
  window.fetch = function(...args) {
    const url = args[0];
    const options = args[1] || {};
    
    const requestData = {
      type: 'fetch',
      url: typeof url === 'string' ? url : url.url || url.toString(),
      method: options.method || 'GET',
      headers: options.headers || {},
      body: options.body || null,
      timestamp: new Date().toISOString()
    };
    
    return originalFetch.apply(this, args)
      .then(response => {
        // Clone response to read it
        const clonedResponse = response.clone();
        
        requestData.status = response.status;
        requestData.statusText = response.statusText;
        requestData.headers = {};
        response.headers.forEach((value, key) => {
          requestData.headers[key] = value;
        });
        
        // Try to parse response body
        clonedResponse.text()
          .then(text => {
            try {
              requestData.response = JSON.parse(text);
            } catch (e) {
              requestData.response = text;
            }
            extractionData.apiCalls.push(requestData);
            console.log('📡 API Call:', requestData.method, requestData.url);
          })
          .catch(() => {
            extractionData.apiCalls.push(requestData);
          });
        
        return response;
      })
      .catch(error => {
        requestData.error = error.message;
        extractionData.apiCalls.push(requestData);
        throw error;
      });
  };
  
  // ============================================
  // 2. INTERCEPT XMLHttpRequest
  // ============================================
  const originalXHROpen = XMLHttpRequest.prototype.open;
  const originalXHRSend = XMLHttpRequest.prototype.send;
  
  XMLHttpRequest.prototype.open = function(method, url, ...rest) {
    this._method = method;
    this._url = url;
    return originalXHROpen.apply(this, [method, url, ...rest]);
  };
  
  XMLHttpRequest.prototype.send = function(data) {
    const requestData = {
      type: 'xhr',
      url: this._url,
      method: this._method || 'GET',
      body: data,
      timestamp: new Date().toISOString()
    };
    
    this.addEventListener('load', function() {
      requestData.status = this.status;
      requestData.statusText = this.statusText;
      requestData.response = this.responseText;
      requestData.responseType = this.responseType;
      
      try {
        requestData.responseJSON = JSON.parse(this.responseText);
      } catch (e) {
        // Not JSON
      }
      
      extractionData.apiCalls.push(requestData);
      console.log('📡 XHR Call:', requestData.method, requestData.url);
    });
    
    this.addEventListener('error', function() {
      requestData.error = 'Network error';
      extractionData.apiCalls.push(requestData);
    });
    
    return originalXHRSend.apply(this, [data]);
  };
  
  // ============================================
  // 3. INTERCEPT WEBSOCKET CONNECTIONS
  // ============================================
  const originalWebSocket = window.WebSocket;
  window.WebSocket = function(url, protocols) {
    const ws = new originalWebSocket(url, protocols || []);
    
    const wsData = {
      url: url,
      protocols: protocols || [],
      timestamp: new Date().toISOString(),
      messages: [],
      events: []
    };
    
    ws.addEventListener('open', function() {
      wsData.events.push({
        type: 'open',
        timestamp: new Date().toISOString()
      });
      console.log('🔌 WebSocket opened:', url);
    });
    
    ws.addEventListener('message', function(event) {
      wsData.messages.push({
        type: 'received',
        data: event.data,
        timestamp: new Date().toISOString()
      });
    });
    
    ws.addEventListener('error', function(error) {
      wsData.events.push({
        type: 'error',
        error: error.message || 'WebSocket error',
        timestamp: new Date().toISOString()
      });
    });
    
    ws.addEventListener('close', function(event) {
      wsData.events.push({
        type: 'close',
        code: event.code,
        reason: event.reason,
        timestamp: new Date().toISOString()
      });
    });
    
    // Intercept send method
    const originalSend = ws.send;
    ws.send = function(data) {
      wsData.messages.push({
        type: 'sent',
        data: data,
        timestamp: new Date().toISOString()
      });
      return originalSend.apply(this, [data]);
    };
    
    extractionData.websockets.push(wsData);
    return ws;
  };
  
  // ============================================
  // 4. EXTRACT EVENT LISTENERS
  // ============================================
  function extractEventListeners() {
    const listeners = [];
    
    // Check if getEventListeners is available (Chrome DevTools)
    if (typeof getEventListeners !== 'function') {
      console.warn('⚠️ getEventListeners not available - install Chrome DevTools or use Event Listener Inspector');
      extractionData.eventListeners = [];
      return;
    }
    
    const allElements = document.querySelectorAll('*');
    
    allElements.forEach((el, index) => {
      if (index > 1000) return; // Limit to prevent performance issues
      
      try {
        const elListeners = getEventListeners(el);
        if (elListeners && Object.keys(elListeners).length > 0) {
          const className = typeof el.className === 'string' 
            ? el.className 
            : (el.className.baseVal || String(el.className) || '');
          const id = el.id || '';
          const tag = el.tagName.toLowerCase();
          
          listeners.push({
            selector: id ? `#${id}` : (className ? `.${className.split(' ')[0]}` : tag),
            id: id,
            class: className,
            tag: tag,
            events: Object.keys(elListeners).map(eventType => ({
              type: eventType,
              listeners: elListeners[eventType].map(l => ({
                listener: (l.listener || '').toString().substring(0, 200),
                useCapture: l.useCapture || false,
                passive: l.passive || false
              }))
            }))
          });
        }
      } catch (e) {
        // Skip elements that can't be inspected
      }
    });
    
    extractionData.eventListeners = listeners;
    console.log('👂 Found', listeners.length, 'elements with event listeners');
  }
  
  // ============================================
  // 5. INTERCEPT FORM SUBMISSIONS
  // ============================================
  document.addEventListener('submit', function(event) {
    const form = event.target;
    const formData = new FormData(form);
    const formObject = {};
    
    for (let [key, value] of formData.entries()) {
      formObject[key] = value;
    }
    
    extractionData.formSubmissions.push({
      action: form.action || '',
      method: form.method || 'GET',
      data: formObject,
      timestamp: new Date().toISOString()
    });
    
    console.log('📝 Form submitted:', form.action || form.id || 'unknown');
  }, true);
  
  // ============================================
  // 6. EXTRACT COMPONENT DATA
  // ============================================
  function extractComponentData() {
    // React components (if React DevTools available)
    if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
      extractionData.componentData.react = {
        available: true,
        note: 'React DevTools detected - use React DevTools to inspect components'
      };
    }
    
    // Vue components
    if (window.__VUE_DEVTOOLS_GLOBAL_HOOK__) {
      extractionData.componentData.vue = {
        available: true,
        note: 'Vue DevTools detected - use Vue DevTools to inspect components'
      };
    }
    
    // Extract data attributes (select all elements, then filter)
    const allElements = document.querySelectorAll('*');
    const dataAttributes = {};
    allElements.forEach(el => {
      Array.from(el.attributes)
        .filter(attr => attr.name.startsWith('data-'))
        .forEach(attr => {
          if (!dataAttributes[attr.name]) {
            dataAttributes[attr.name] = [];
          }
          const className = typeof el.className === 'string' 
            ? el.className 
            : (el.className.baseVal || String(el.className) || '');
          const selector = el.id ? `#${el.id}` : (className ? `.${className.split(' ')[0]}` : el.tagName);
          dataAttributes[attr.name].push({
            value: attr.value,
            selector: selector
          });
        });
    });
    
    extractionData.componentData.dataAttributes = dataAttributes;
    
    // Extract IDs and classes for component mapping
    const components = {};
    document.querySelectorAll('*').forEach(el => {
      if (el.id) {
        const className = typeof el.className === 'string' 
          ? el.className 
          : (el.className.baseVal || String(el.className) || '');
        components[el.id] = {
          tag: el.tagName.toLowerCase(),
          classes: className,
          text: (el.textContent || '').substring(0, 100)
        };
      }
    });
    
    extractionData.componentData.components = components;
  }
  
  // ============================================
  // 7. EXTRACT STORAGE
  // ============================================
  function extractStorage() {
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        extractionData.localStorage[key] = localStorage.getItem(key);
      }
    } catch (e) {
      extractionData.localStorage.error = e.message;
    }
    
    try {
      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        extractionData.sessionStorage[key] = sessionStorage.getItem(key);
      }
    } catch (e) {
      extractionData.sessionStorage.error = e.message;
    }
    
    extractionData.cookies = document.cookie;
  }
  
  // ============================================
  // 8. MONITOR MUTATIONS (Dynamic Content)
  // ============================================
  const mutationObserver = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
      if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
        mutation.addedNodes.forEach(function(node) {
          if (node.nodeType === 1) { // Element node
            // Check for new API calls or dynamic content
            const scripts = node.querySelectorAll ? node.querySelectorAll('script') : [];
            scripts.forEach(script => {
              if (script.src) {
                extractionData.networkRequests.push({
                  type: 'script',
                  url: script.src,
                  timestamp: new Date().toISOString()
                });
              }
            });
          }
        });
      }
    });
  });
  
  mutationObserver.observe(document.body, {
    childList: true,
    subtree: true
  });
  
  // ============================================
  // EXPORT FUNCTION
  // ============================================
  window.extractFunctionality = {
    getData: function() {
      return extractionData;
    },
    
    export: function() {
      // Final extraction
      extractEventListeners();
      extractComponentData();
      extractStorage();
      
      const dataStr = JSON.stringify(extractionData, null, 2);
      const dataBlob = new Blob([dataStr], { type: 'application/json' });
      const url = URL.createObjectURL(dataBlob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `trade_manager_functionality_${window.location.pathname.replace(/\//g, '_')}_${Date.now()}.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      
      console.log('✅ Functionality data exported!');
      console.log('📊 Summary:');
      console.log('  - API Calls:', extractionData.apiCalls.length);
      console.log('  - WebSockets:', extractionData.websockets.length);
      console.log('  - Event Listeners:', extractionData.eventListeners.length);
      console.log('  - Form Submissions:', extractionData.formSubmissions.length);
    },
    
    log: function() {
      console.log('📊 Current Extraction Data:', extractionData);
      return extractionData;
    }
  };
  
  console.log('✅ Functionality extraction script loaded!');
  console.log('📋 Usage:');
  console.log('  - window.extractFunctionality.log() - View current data');
  console.log('  - window.extractFunctionality.export() - Download JSON file');
  console.log('  - Navigate pages and interact to capture API calls');
  console.log('  - Run export() after testing functionality');
  
  // Initial extraction
  extractComponentData();
  extractStorage();
  
})();

