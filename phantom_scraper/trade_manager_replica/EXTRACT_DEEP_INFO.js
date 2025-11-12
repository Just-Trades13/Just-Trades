/**
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

