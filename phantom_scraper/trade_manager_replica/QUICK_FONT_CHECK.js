/**
 * Quick Font Check Script
 * Run this in the browser console to quickly see what fonts are being used
 */

console.log('🔤 FONT ANALYSIS');
console.log('='.repeat(80));

// Check loaded fonts
if (document.fonts && document.fonts.check) {
  console.log('\n✅ Loaded Fonts:');
  document.fonts.forEach(font => {
    console.log(`   - ${font.family} (${font.weight} ${font.style}) - Status: ${font.status}`);
  });
}

// Get all font families from computed styles
const fontFamilies = new Set();
document.querySelectorAll('*').forEach(el => {
  const computed = window.getComputedStyle(el);
  const fontFamily = computed.fontFamily;
  if (fontFamily && fontFamily !== 'initial' && fontFamily !== 'inherit') {
    fontFamilies.add(fontFamily);
  }
});

console.log('\n📋 Font Families Used (from computed styles):');
Array.from(fontFamilies).sort().forEach(font => {
  console.log(`   - ${font}`);
});

// Check for Google Fonts links
console.log('\n🌐 Google Fonts Links:');
const googleFontLinks = Array.from(document.querySelectorAll('link[href*="fonts.googleapis"]'));
googleFontLinks.forEach(link => {
  console.log(`   - ${link.href}`);
});

// Check for @font-face rules
console.log('\n📝 @font-face Rules:');
let fontFaceCount = 0;
Array.from(document.styleSheets).forEach(sheet => {
  try {
    Array.from(sheet.cssRules || []).forEach(rule => {
      if (rule instanceof CSSFontFaceRule) {
        fontFaceCount++;
        console.log(`   - Family: ${rule.style.fontFamily}`);
        console.log(`     Source: ${rule.style.src}`);
      }
    });
  } catch (e) {
    // Cross-origin
  }
});

if (fontFaceCount === 0) {
  console.log('   (No @font-face rules found)');
}

// Check key elements
console.log('\n🎯 Key Elements Font Stacks:');
['body', 'h1', 'h2', '.btn', '.sidebar'].forEach(selector => {
  const el = document.querySelector(selector);
  if (el) {
    const computed = window.getComputedStyle(el);
    console.log(`   ${selector}: ${computed.fontFamily}`);
  }
});

console.log('\n' + '='.repeat(80));

