[Error] Failed to load resource: the server responded with a status of 400 (Bad Request) (main.js'%20%%7D, line 0)
[Error] Notification prompting can only be done from a user gesture.
	(anonymous function) (main.ee199c5c.js:2:3748996)
[Error] ❌ Notification permission denied.
	(anonymous function) (main.ee199c5c.js:2:3749237)
[Log] Stat configuration updated: – {message: "Stat config saved successfully"} (main.ee199c5c.js, line 2)
> /**
 * Deep Information Extraction Script
 * Extracts: fonts, CSS sources, JS sources, hosting info, CDN usage, etc.
 * 
 * INSTRUCTIONS:
 * 1. Open the original Trade Manager site in your browser
 * 2. Open Developer Tools (F12)
 * 3. Go to Console tab
 * 4. Paste this entire script
 * 5. Press Enter
 * 6. Copy the output JSON
 * 7. Save it as a file
 */

(function() {
  console.log('🔍 Starting Deep Information Extraction...');
  
  const extractionData = {
    timestamp: new Date().toISOString(),
    url: window.location.href,
    hostname: window.location.hostname,
    
    // Font Information
    fonts: {
      computed: [],
      loaded: [],
      fontFace: []
    },
    
    // CSS Sources
    css: {
      stylesheets: [],
      inline: [],
      computed: {}
    },
    
    // JavaScript Sources
    javascript: {
      scripts: [],
      modules: [],
      libraries: []
    },
    
    // Network Information
    network: {
      resources: [],
      cdn: [],
      hosting: {}
    },
    
    // Meta Information
    meta: {
      viewport: '',
      charset: '',
      description: '',
      keywords: '',
      author: ''
    },
    
    // Performance API
    performance: {
      timing: {},
      navigation: {},
      resources: []
    }
  };
  
  // Extract all fonts
  try {
    if (document.fonts && document.fonts.check) {
      document.fonts.forEach(font => {
        extractionData.fonts.loaded.push({
          family: font.family,
          style: font.style,
          weight: font.weight,
          status: font.status,
          loaded: font.loaded
        });
      });
    }
    
    // Get computed fonts from all elements
    const allElements = document.querySelectorAll('*');
    const fontFamilies = new Set();
    allElements.forEach(el => {
      const computed = window.getComputedStyle(el);
      const fontFamily = computed.fontFamily;
      if (fontFamily && fontFamily !== 'initial' && fontFamily !== 'inherit') {
        fontFamilies.add(fontFamily);
      }
    });
    extractionData.fonts.computed = Array.from(fontFamilies);
    
    // Extract @font-face rules
    const styleSheets = Array.from(document.styleSheets);
    styleSheets.forEach(sheet => {
      try {
        const rules = Array.from(sheet.cssRules || []);
        rules.forEach(rule => {
          if (rule instanceof CSSFontFaceRule) {
            extractionData.fonts.fontFace.push({
              family: rule.style.fontFamily,
              src: rule.style.src,
              weight: rule.style.fontWeight,
              style: rule.style.fontStyle,
              display: rule.style.fontDisplay
            });
          }
        });
      } catch (e) {
        // Cross-origin stylesheet
      }
    });
  } catch (e) {
    console.error('Error extracting fonts:', e);
  }
  
  // Extract CSS sources
  try {
    const styleSheets = Array.from(document.styleSheets);
    styleSheets.forEach((sheet, index) => {
      try {
        extractionData.css.stylesheets.push({
          index: index,
          href: sheet.href || 'inline',
          type: sheet.type,
          disabled: sheet.disabled,
          title: sheet.title,
          ownerNode: sheet.ownerNode ? {
            tagName: sheet.ownerNode.tagName,
            id: sheet.ownerNode.id,
            className: sheet.ownerNode.className,
            src: sheet.ownerNode.src,
            href: sheet.ownerNode.href
          } : null
        });
      } catch (e) {
        extractionData.css.stylesheets.push({
          index: index,
          error: 'Cross-origin or inaccessible',
          href: sheet.href || 'unknown'
        });
      }
    });
    
    // Extract inline styles
    const inlineStyles = document.querySelectorAll('style');
    inlineStyles.forEach((style, index) => {
      extractionData.css.inline.push({
        index: index,
        type: style.type,
        media: style.media,
        text: style.textContent.substring(0, 500) // First 500 chars
      });
    });
  } catch (e) {
    console.error('Error extracting CSS:', e);
  }
  
  // Extract JavaScript sources
  try {
    const scripts = Array.from(document.scripts);
    scripts.forEach((script, index) => {
      extractionData.javascript.scripts.push({
        index: index,
        src: script.src || 'inline',
        type: script.type,
        async: script.async,
        defer: script.defer,
        module: script.type === 'module',
        text: script.src ? null : script.textContent.substring(0, 200) // First 200 chars if inline
      });
    });
  } catch (e) {
    console.error('Error extracting JavaScript:', e);
  }
  
  // Extract meta information
  try {
    const metaTags = document.querySelectorAll('meta');
    metaTags.forEach(meta => {
      const name = meta.getAttribute('name') || meta.getAttribute('property');
      const content = meta.getAttribute('content');
      if (name && content) {
        extractionData.meta[name] = content;
      }
    });
    
    const viewport = document.querySelector('meta[name="viewport"]');
    if (viewport) {
      extractionData.meta.viewport = viewport.getAttribute('content');
    }
    
    const charset = document.querySelector('meta[charset]');
    if (charset) {
      extractionData.meta.charset = charset.getAttribute('charset');
    }
  } catch (e) {
    console.error('Error extracting meta:', e);
  }
  
  // Extract Performance API data
  try {
    if (window.performance && window.performance.timing) {
      const timing = window.performance.timing;
      extractionData.performance.timing = {
        navigationStart: timing.navigationStart,
        domainLookupStart: timing.domainLookupStart,
        domainLookupEnd: timing.domainLookupEnd,
        connectStart: timing.connectStart,
        connectEnd: timing.connectEnd,
        requestStart: timing.requestStart,
        responseStart: timing.responseStart,
        responseEnd: timing.responseEnd,
        domLoading: timing.domLoading,
        domInteractive: timing.domInteractive,
        domContentLoadedEventStart: timing.domContentLoadedEventStart,
        domContentLoadedEventEnd: timing.domContentLoadedEventEnd,
        loadEventStart: timing.loadEventStart,
        loadEventEnd: timing.loadEventEnd
      };
    }
    
    if (window.performance && window.performance.navigation) {
      extractionData.performance.navigation = {
        type: window.performance.navigation.type,
        redirectCount: window.performance.navigation.redirectCount
      };
    }
    
    if (window.performance && window.performance.getEntriesByType) {
      const resources = window.performance.getEntriesByType('resource');
      extractionData.performance.resources = resources.map(resource => ({
        name: resource.name,
        type: resource.initiatorType,
        duration: resource.duration,
        size: resource.transferSize,
        domain: new URL(resource.name).hostname
      }));
    }
  } catch (e) {
    console.error('Error extracting performance:', e);
  }
  
  // Analyze CDN and hosting
  try {
    const domains = new Set();
    const cdnPatterns = [
      'cdn', 'cloudflare', 'cloudfront', 'jsdelivr', 'unpkg', 
      'googleapis', 'fonts', 'bootstrap', 'jquery', 'cdnjs'
    ];
    
    // Get all resource URLs
    const allResources = [];
    
    // From stylesheets
    extractionData.css.stylesheets.forEach(sheet => {
      if (sheet.href && sheet.href !== 'inline') {
        try {
          const url = new URL(sheet.href);
          domains.add(url.hostname);
          allResources.push({
            url: sheet.href,
            type: 'stylesheet',
            domain: url.hostname,
            isCDN: cdnPatterns.some(pattern => url.hostname.includes(pattern))
          });
        } catch (e) {}
      }
    });
    
    // From scripts
    extractionData.javascript.scripts.forEach(script => {
      if (script.src && script.src !== 'inline') {
        try {
          const url = new URL(script.src);
          domains.add(url.hostname);
          allResources.push({
            url: script.src,
            type: 'script',
            domain: url.hostname,
            isCDN: cdnPatterns.some(pattern => url.hostname.includes(pattern))
          });
        } catch (e) {}
      }
    });
    
    // From performance resources
    if (extractionData.performance.resources) {
      extractionData.performance.resources.forEach(resource => {
        try {
          const url = new URL(resource.name);
          domains.add(url.hostname);
          const isCDN = cdnPatterns.some(pattern => url.hostname.includes(pattern));
          if (isCDN) {
            extractionData.network.cdn.push({
              url: resource.name,
              type: resource.type,
              domain: url.hostname
            });
          }
        } catch (e) {}
      });
    }
    
    extractionData.network.resources = allResources;
    extractionData.network.hosting = {
      mainDomain: window.location.hostname,
      allDomains: Array.from(domains),
      cdnCount: extractionData.network.cdn.length
    };
  } catch (e) {
    console.error('Error analyzing CDN:', e);
  }
  
  // Detect common libraries
  try {
    const libraries = [];
    
    // Check for React
    if (window.React || window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
      libraries.push({ name: 'React', detected: true });
    }
    
    // Check for Vue
    if (window.Vue || window.__VUE__) {
      libraries.push({ name: 'Vue', detected: true });
    }
    
    // Check for jQuery
    if (window.jQuery || window.$) {
      libraries.push({ name: 'jQuery', version: window.jQuery?.fn?.jquery || 'unknown' });
    }
    
    // Check for Bootstrap
    if (window.bootstrap || document.querySelector('[class*="bootstrap"]')) {
      libraries.push({ name: 'Bootstrap', detected: true });
    }
    
    // Check for Material UI
    if (window.material || document.querySelector('[class*="material"]')) {
      libraries.push({ name: 'Material UI', detected: true });
    }
    
    // Check for Socket.IO
    if (window.io || window.socket) {
      libraries.push({ name: 'Socket.IO', detected: true });
    }
    
    extractionData.javascript.libraries = libraries;
  } catch (e) {
    console.error('Error detecting libraries:', e);
  }
  
  // Extract all link tags (for fonts, stylesheets, etc.)
  try {
    const links = Array.from(document.querySelectorAll('link'));
    const linkData = [];
    links.forEach(link => {
      linkData.push({
        rel: link.rel,
        href: link.href,
        type: link.type,
        media: link.media,
        crossorigin: link.crossOrigin,
        integrity: link.integrity
      });
    });
    extractionData.network.links = linkData;
  } catch (e) {
    console.error('Error extracting links:', e);
  }
  
  // Get computed styles for key elements
  try {
    const keySelectors = ['body', 'h1', 'h2', 'h3', '.btn', '.sidebar', '.main-panel'];
    keySelectors.forEach(selector => {
      const element = document.querySelector(selector);
      if (element) {
        const computed = window.getComputedStyle(element);
        extractionData.css.computed[selector] = {
          fontFamily: computed.fontFamily,
          fontSize: computed.fontSize,
          fontWeight: computed.fontWeight,
          fontStyle: computed.fontStyle,
          lineHeight: computed.lineHeight,
          letterSpacing: computed.letterSpacing,
          color: computed.color,
          backgroundColor: computed.backgroundColor
        };
      }
    });
  } catch (e) {
    console.error('Error extracting computed styles:', e);
  }
  
  console.log('✅ Extraction Complete!');
  console.log('📋 Copy the JSON below and save it as a file:');
  console.log('='.repeat(80));
  
  const output = JSON.stringify(extractionData, null, 2);
  console.log(output);
  
  // Also log a summary
  console.log('\n📊 SUMMARY:');
  console.log(`- Fonts Loaded: ${extractionData.fonts.loaded.length}`);
  console.log(`- Font Families Used: ${extractionData.fonts.computed.length}`);
  console.log(`- @font-face Rules: ${extractionData.fonts.fontFace.length}`);
  console.log(`- Stylesheets: ${extractionData.css.stylesheets.length}`);
  console.log(`- JavaScript Files: ${extractionData.javascript.scripts.length}`);
  console.log(`- CDN Resources: ${extractionData.network.cdn.length}`);
  console.log(`- Total Domains: ${extractionData.network.hosting.allDomains.length}`);
  console.log(`- Main Domain: ${extractionData.network.hosting.mainDomain}`);
  
  return extractionData;
})();


[Log] 🔍 Starting Deep Information Extraction...
[Log] ✅ Extraction Complete!
[Log] 📋 Copy the JSON below and save it as a file:
[Log] ================================================================================
[Log] {
  "timestamp": "2025-11-06T06:57:43.291Z",
  "url": "https://trademanagergroup.com/user/dashboard",
  "hostname": "trademanagergroup.com",
  "fonts": {
    "computed": [
      "sans-serif",
      "Poppins, sans-serif",
      "Nucleo"
    ],
    "loaded": [
      {
        "family": "Material Icons",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "300",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "300",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "300",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "300",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "300",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "300",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "300",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "300",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "300",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "500",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "500",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "500",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "500",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "500",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "500",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "500",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "500",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "500",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Roboto Slab",
        "style": "normal",
        "weight": "700",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Font Awesome 5 Brands",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Font Awesome 5 Free",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Font Awesome 5 Free",
        "style": "normal",
        "weight": "900",
        "status": "unloaded",
        "loaded": {}
      },
      {
        "family": "Nucleo",
        "style": "normal",
        "weight": "400",
        "status": "loaded",
        "loaded": {}
      },
      {
        "family": "fcicons",
        "style": "normal",
        "weight": "400",
        "status": "unloaded",
        "loaded": {}
      }
    ],
    "fontFace": [
      {
        "family": "Nucleo",
        "src": "url(\"/static/media/nucleo.bd5cce8bf40be5947637.eot\") format(\"embedded-opentype\"), url(\"/static/media/nucleo.6dfb4833e3a0132fd1fc.woff2\") format(\"woff2\"), url(\"/static/media/nucleo.5c65ef4d6434bb8062a3.woff\") format(\"woff\"), url(\"/static/media/nucleo.35b08447277ca7bf9f09.ttf\") format(\"truetype\")",
        "weight": "400",
        "style": "normal",
        "display": ""
      },
      {
        "family": "fcicons",
        "src": "url(\"data:application/x-font-ttf;charset=utf-8;base64,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\") format(\"truetype\")",
        "weight": "400",
        "style": "normal",
        "display": ""
      }
    ]
  },
  "css": {
    "stylesheets": [
      {
        "index": 0,
        "href": "inline",
        "type": "text/css",
        "disabled": false,
        "title": null,
        "ownerNode": {
          "tagName": "STYLE",
          "id": "",
          "className": ""
        }
      },
      {
        "index": 1,
        "href": "https://fonts.googleapis.com/css?family=Roboto:300,400,500,700|Roboto+Slab:400,700|Material+Icons",
        "type": "text/css",
        "disabled": false,
        "title": null,
        "ownerNode": {
          "tagName": "LINK",
          "id": "",
          "className": "",
          "href": "https://fonts.googleapis.com/css?family=Roboto:300,400,500,700|Roboto+Slab:400,700|Material+Icons"
        }
      },
      {
        "index": 2,
        "href": "https://use.fontawesome.com/releases/v5.0.10/css/all.css",
        "type": "text/css",
        "disabled": false,
        "title": null,
        "ownerNode": {
          "tagName": "LINK",
          "id": "",
          "className": "",
          "href": "https://use.fontawesome.com/releases/v5.0.10/css/all.css"
        }
      },
      {
        "index": 3,
        "href": "https://trademanagergroup.com/static/css/main.edcc780c.css",
        "type": "text/css",
        "disabled": false,
        "title": null,
        "ownerNode": {
          "tagName": "LINK",
          "id": "",
          "className": "",
          "href": "https://trademanagergroup.com/static/css/main.edcc780c.css"
        }
      },
      {
        "index": 4,
        "href": "inline",
        "type": "text/css",
        "disabled": false,
        "title": null,
        "ownerNode": {
          "tagName": "STYLE",
          "id": "",
          "className": ""
        }
      }
    ],
    "inline": [
      {
        "index": 0,
        "type": "text/css",
        "media": "",
        "text": ":root{--toastify-color-light: #fff;--toastify-color-dark: #121212;--toastify-color-info: #3498db;--toastify-color-success: #07bc0c;--toastify-color-warning: #f1c40f;--toastify-color-error: hsl(6, 78%, 57%);--toastify-color-transparent: rgba(255, 255, 255, .7);--toastify-icon-color-info: var(--toastify-color-info);--toastify-icon-color-success: var(--toastify-color-success);--toastify-icon-color-warning: var(--toastify-color-warning);--toastify-icon-color-error: var(--toastify-color-error);--toas"
      },
      {
        "index": 1,
        "type": "",
        "media": "",
        "text": ""
      }
    ],
    "computed": {
      "body": {
        "fontFamily": "Poppins, sans-serif",
        "fontSize": "14px",
        "fontWeight": "400",
        "fontStyle": "normal",
        "lineHeight": "21px",
        "letterSpacing": "normal",
        "color": "rgb(82, 95, 127)",
        "backgroundColor": "rgb(30, 30, 47)"
      },
      "h2": {
        "fontFamily": "Poppins, sans-serif",
        "fontSize": "27px",
        "fontWeight": "100",
        "fontStyle": "normal",
        "lineHeight": "32.399998px",
        "letterSpacing": "normal",
        "color": "rgb(255, 255, 255)",
        "backgroundColor": "rgba(0, 0, 0, 0)"
      },
      ".btn": {
        "fontFamily": "Poppins, sans-serif",
        "fontSize": "14px",
        "fontWeight": "600",
        "fontStyle": "normal",
        "lineHeight": "18.9px",
        "letterSpacing": "normal",
        "color": "rgb(52, 70, 117)",
        "backgroundColor": "rgba(0, 0, 0, 0)"
      },
      ".sidebar": {
        "fontFamily": "Poppins, sans-serif",
        "fontSize": "14px",
        "fontWeight": "400",
        "fontStyle": "normal",
        "lineHeight": "21px",
        "letterSpacing": "normal",
        "color": "rgb(82, 95, 127)",
        "backgroundColor": "rgba(0, 0, 0, 0)"
      },
      ".main-panel": {
        "fontFamily": "Poppins, sans-serif",
        "fontSize": "14px",
        "fontWeight": "400",
        "fontStyle": "normal",
        "lineHeight": "21px",
        "letterSpacing": "normal",
        "color": "rgb(82, 95, 127)",
        "backgroundColor": "rgba(0, 0, 0, 0)"
      }
    }
  },
  "javascript": {
    "scripts": [
      {
        "index": 0,
        "src": "https://www.google-analytics.com/analytics.js",
        "type": "text/javascript",
        "async": true,
        "defer": false,
        "module": false,
        "text": null
      },
      {
        "index": 1,
        "src": "https://www.gstatic.com/recaptcha/releases/naPR4A6FAh-yZLuCX253WaZq/recaptcha__en.js",
        "type": "text/javascript",
        "async": true,
        "defer": false,
        "module": false,
        "text": null
      },
      {
        "index": 2,
        "src": "https://www.googletagmanager.com/gtag/js?id=UA-XXXXX-Y",
        "type": "",
        "async": true,
        "defer": false,
        "module": false,
        "text": null
      },
      {
        "index": 3,
        "src": "inline",
        "type": "",
        "async": false,
        "defer": false,
        "module": false,
        "text": "function gtag(){dataLayer.push(arguments)}window.dataLayer=window.dataLayer||[],gtag(\"js\",new Date),gtag(\"config\",\"UA-XXXXX-Y\")"
      },
      {
        "index": 4,
        "src": "inline",
        "type": "application/ld+json",
        "async": true,
        "defer": false,
        "module": false,
        "text": "{\n      \"@context\": \"http://schema.org\",\n      \"@type\": \"WebSite\",\n      \"name\": \"Trade Manager\",\n      \"url\": \"https://trademanagergroup.com\"\n    }"
      },
      {
        "index": 5,
        "src": "https://www.google.com/recaptcha/api.js?render=6LdKDy0rAAAAAJvcuPDHVOK897TZCfbE40-noXib",
        "type": "",
        "async": false,
        "defer": false,
        "module": false,
        "text": null
      },
      {
        "index": 6,
        "src": "https://trademanagergroup.com/static/js/main.ee199c5c.js",
        "type": "",
        "async": false,
        "defer": true,
        "module": false,
        "text": null
      },
      {
        "index": 7,
        "src": "https://trademanagergroup.com/user/%7B%%20static%20'js/main.js'%20%%7D",
        "type": "",
        "async": false,
        "defer": false,
        "module": false,
        "text": null
      }
    ],
    "modules": [],
    "libraries": []
  },
  "network": {
    "resources": [
      {
        "url": "https://fonts.googleapis.com/css?family=Roboto:300,400,500,700|Roboto+Slab:400,700|Material+Icons",
        "type": "stylesheet",
        "domain": "fonts.googleapis.com",
        "isCDN": true
      },
      {
        "url": "https://use.fontawesome.com/releases/v5.0.10/css/all.css",
        "type": "stylesheet",
        "domain": "use.fontawesome.com",
        "isCDN": false
      },
      {
        "url": "https://trademanagergroup.com/static/css/main.edcc780c.css",
        "type": "stylesheet",
        "domain": "trademanagergroup.com",
        "isCDN": false
      },
      {
        "url": "https://www.google-analytics.com/analytics.js",
        "type": "script",
        "domain": "www.google-analytics.com",
        "isCDN": false
      },
      {
        "url": "https://www.gstatic.com/recaptcha/releases/naPR4A6FAh-yZLuCX253WaZq/recaptcha__en.js",
        "type": "script",
        "domain": "www.gstatic.com",
        "isCDN": false
      },
      {
        "url": "https://www.googletagmanager.com/gtag/js?id=UA-XXXXX-Y",
        "type": "script",
        "domain": "www.googletagmanager.com",
        "isCDN": false
      },
      {
        "url": "https://www.google.com/recaptcha/api.js?render=6LdKDy0rAAAAAJvcuPDHVOK897TZCfbE40-noXib",
        "type": "script",
        "domain": "www.google.com",
        "isCDN": false
      },
      {
        "url": "https://trademanagergroup.com/static/js/main.ee199c5c.js",
        "type": "script",
        "domain": "trademanagergroup.com",
        "isCDN": false
      },
      {
        "url": "https://trademanagergroup.com/user/%7B%%20static%20'js/main.js'%20%%7D",
        "type": "script",
        "domain": "trademanagergroup.com",
        "isCDN": false
      }
    ],
    "cdn": [
      {
        "url": "https://fonts.googleapis.com/css?family=Roboto:300,400,500,700|Roboto+Slab:400,700|Material+Icons",
        "type": "link",
        "domain": "fonts.googleapis.com"
      }
    ],
    "hosting": {
      "mainDomain": "trademanagergroup.com",
      "allDomains": [
        "fonts.googleapis.com",
        "use.fontawesome.com",
        "trademanagergroup.com",
        "www.google-analytics.com",
        "www.gstatic.com",
        "www.googletagmanager.com",
        "www.google.com"
      ],
      "cdnCount": 1
    },
    "links": [
      {
        "rel": "canonical",
        "href": "https://trademanagergroup.com/",
        "type": "",
        "media": "",
        "crossorigin": null,
        "integrity": ""
      },
      {
        "rel": "apple-touch-icon",
        "href": "https://trademanagergroup.com/favicon.png",
        "type": "",
        "media": "",
        "crossorigin": null,
        "integrity": ""
      },
      {
        "rel": "manifest",
        "href": "https://trademanagergroup.com/manifest.json",
        "type": "",
        "media": "",
        "crossorigin": null,
        "integrity": ""
      },
      {
        "rel": "shortcut icon",
        "href": "https://trademanagergroup.com/favicon.png",
        "type": "",
        "media": "",
        "crossorigin": null,
        "integrity": ""
      },
      {
        "rel": "apple-touch-icon",
        "href": "https://trademanagergroup.com/favicon.png",
        "type": "",
        "media": "",
        "crossorigin": null,
        "integrity": ""
      },
      {
        "rel": "preload",
        "href": "https://fonts.googleapis.com/css?family=Roboto:300,400,500,700|Roboto+Slab:400,700|Material+Icons",
        "type": "",
        "media": "",
        "crossorigin": null,
        "integrity": ""
      },
      {
        "rel": "stylesheet",
        "href": "https://fonts.googleapis.com/css?family=Roboto:300,400,500,700|Roboto+Slab:400,700|Material+Icons",
        "type": "",
        "media": "",
        "crossorigin": null,
        "integrity": ""
      },
      {
        "rel": "stylesheet",
        "href": "https://use.fontawesome.com/releases/v5.0.10/css/all.css",
        "type": "",
        "media": "",
        "crossorigin": null,
        "integrity": ""
      },
      {
        "rel": "stylesheet",
        "href": "https://trademanagergroup.com/static/css/main.edcc780c.css",
        "type": "",
        "media": "",
        "crossorigin": null,
        "integrity": ""
      }
    ]
  },
  "meta": {
    "viewport": "width=device-width,initial-scale=1,shrink-to-fit=no",
    "charset": "utf-8",
    "description": "Trade Manager - Automated Trading Software",
    "keywords": "trade, manager, artificial, automated, finance, stocks, trading",
    "author": "Trade Manager",
    "csrf-token": "{%",
    "theme-color": "#000000",
    "og:title": "Trade Manager",
    "og:description": "Trade while you sleep",
    "og:image": "/favicon.png",
    "og:url": "https://trademanagergroup.com",
    "og:type": "website",
    "twitter:card": "summary_large_image",
    "twitter:title": "Trade Manager",
    "twitter:description": "Manage your trades effectively with Trade Manager",
    "twitter:image": "/favicon.png",
    "mobile-web-app-capable": "yes",
    "apple-mobile-web-app-capable": "yes",
    "apple-mobile-web-app-status-bar-style": "black-translucent",
    "apple-mobile-web-app-title": "Trade Manager"
  },
  "performance": {
    "timing": {
      "navigationStart": 1762412259082,
      "domainLookupStart": 1762412259085,
      "domainLookupEnd": 1762412259086,
      "connectStart": 1762412259086,
      "connectEnd": 1762412259153,
      "requestStart": 1762412259155,
      "responseStart": 1762412259182,
      "responseEnd": 1762412259182,
      "domLoading": 1762412259324,
      "domInteractive": 1762412259436,
      "domContentLoadedEventStart": 1762412259570,
      "domContentLoadedEventEnd": 1762412259570,
      "loadEventStart": 1762412259913,
      "loadEventEnd": 1762412259913
    },
    "navigation": {
      "type": 1,
      "redirectCount": 0
    },
    "resources": [
      {
        "name": "https://fonts.googleapis.com/css?family=Roboto:300,400,500,700|Roboto+Slab:400,700|Material+Icons",
        "type": "link",
        "duration": 1,
        "size": 0,
        "domain": "fonts.googleapis.com"
      },
      {
        "name": "https://trademanagergroup.com/manifest.json",
        "type": "other",
        "duration": 25,
        "size": 589,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://use.fontawesome.com/releases/v5.0.10/css/all.css",
        "type": "link",
        "duration": 1,
        "size": 0,
        "domain": "use.fontawesome.com"
      },
      {
        "name": "https://www.googletagmanager.com/gtag/js?id=UA-XXXXX-Y",
        "type": "script",
        "duration": 0,
        "size": 0,
        "domain": "www.googletagmanager.com"
      },
      {
        "name": "https://www.google.com/recaptcha/api.js?render=6LdKDy0rAAAAAJvcuPDHVOK897TZCfbE40-noXib",
        "type": "script",
        "duration": 0,
        "size": 0,
        "domain": "www.google.com"
      },
      {
        "name": "https://trademanagergroup.com/static/js/main.ee199c5c.js",
        "type": "script",
        "duration": 1,
        "size": 0,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/static/css/main.edcc780c.css",
        "type": "link",
        "duration": 16,
        "size": 0,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://www.gstatic.com/recaptcha/releases/naPR4A6FAh-yZLuCX253WaZq/recaptcha__en.js",
        "type": "script",
        "duration": 179,
        "size": 0,
        "domain": "www.gstatic.com"
      },
      {
        "name": "https://trademanagergroup.com/user/%7B%%20static%20'js/main.js'%20%%7D",
        "type": "script",
        "duration": 82,
        "size": 0,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/api/system/csrf-token",
        "type": "fetch",
        "duration": 114,
        "size": 381,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/client_specifics/config.json",
        "type": "fetch",
        "duration": 87.00000000000011,
        "size": 1035,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://www.google.com/recaptcha/api2/anchor?ar=1&k=6LdKDy0rAAAAAJvcuPDHVOK897TZCfbE40-noXib&co=aHR0cHM6Ly90cmFkZW1hbmFnZXJncm91cC5jb206NDQz&hl=en&v=naPR4A6FAh-yZLuCX253WaZq&size=invisible&anchor-ms=20000&execute-ms=15000&cb=2f9kls2ojl6u",
        "type": "iframe",
        "duration": 148.9999999999999,
        "size": 0,
        "domain": "www.google.com"
      },
      {
        "name": "https://www.google-analytics.com/analytics.js",
        "type": "script",
        "duration": 1,
        "size": 0,
        "domain": "www.google-analytics.com"
      },
      {
        "name": "https://trademanagergroup.com/api/auth/check-auth/",
        "type": "fetch",
        "duration": 45,
        "size": 536,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/client_specifics/img/logo.gif",
        "type": "img",
        "duration": 0,
        "size": 0,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/api/trades/?usageType=true",
        "type": "fetch",
        "duration": 100,
        "size": 302,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/api/profiles/get-stat-config",
        "type": "fetch",
        "duration": 189,
        "size": 324,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/api/profiles/get-favorites",
        "type": "fetch",
        "duration": 189,
        "size": 664,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/api/profiles/get-widget-info/?usageType=true",
        "type": "fetch",
        "duration": 1546,
        "size": 46018,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/api/trades/open/?usageType=true",
        "type": "fetch",
        "duration": 67.99999999999989,
        "size": 302,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/api/profiles/get-favorites",
        "type": "fetch",
        "duration": 145,
        "size": 664,
        "domain": "trademanagergroup.com"
      },
      {
        "name": "https://trademanagergroup.com/api/profiles/update-stat-config/",
        "type": "fetch",
        "duration": 54,
        "size": 345,
        "domain": "trademanagergroup.com"
      }
    ]
  }
}
[Log] 
📊 SUMMARY:
[Log] - Fonts Loaded: 56
[Log] - Font Families Used: 3
[Log] - @font-face Rules: 2
[Log] - Stylesheets: 5
[Log] - JavaScript Files: 8
[Log] - CDN Resources: 1
[Log] - Total Domains: 7
[Log] - Main Domain: trademanagergroup.com
< {timestamp: "2025-11-06T06:57:43.291Z", url: "https://trademanagergroup.com/user/dashboard", hostname: "trademanagergroup.com", fonts: Object, css: Object, …}