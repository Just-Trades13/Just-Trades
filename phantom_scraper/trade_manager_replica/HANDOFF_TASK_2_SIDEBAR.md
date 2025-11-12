# Task 2: Sidebar Navigation Exact Match

## 🎯 Goal
Make the sidebar navigation match the original Trade Manager site pixel-perfectly.

## 📍 Reference Sites
- **Original**: `https://trademanagergroup.com/user/dashboard`
- **Replica**: `http://localhost:5001/dashboard`

## 📁 Files to Modify
1. `frontend/src/components/Layout.css` - Sidebar styles
2. `frontend/src/components/Layout.jsx` - Sidebar structure (if needed)

## ✅ Task Checklist

### 1. Sidebar Container
- [ ] Width: `260px` (verify exact pixel value)
- [ ] Background gradient: `linear-gradient(180deg, #5e72e4 0%, #202230 100%)`
- [ ] Box shadow: verify exact shadow values
- [ ] Position: `fixed` with correct z-index
- [ ] Overflow: `overflow-y: auto` for scrolling

### 2. Logo Section
- [ ] Logo image: verify path `/client_specifics/img/logo.gif` exists
- [ ] Logo container padding: check exact values
- [ ] Logo image size: verify width/height
- [ ] Logo text "Just.Trades" styling: font-size, weight, color
- [ ] Border-bottom: verify color and thickness

### 3. Navigation Items
- [ ] List padding/margin: verify exact spacing
- [ ] Item padding: verify `15px 20px` matches
- [ ] Text color: `rgba(255, 255, 255, 0.7)` for inactive
- [ ] Font family: `Poppins` or verify exact font
- [ ] Font size: verify exact size
- [ ] Hover background: `rgba(255, 255, 255, 0.1)`
- [ ] Hover color: `#fff`

### 4. Active State
- [ ] Background: `rgba(255, 255, 255, 0.15)`
- [ ] Border-left: `4px solid #fff`
- [ ] Font weight: `600`
- [ ] Text color: `#fff`

### 5. Icons
- [ ] Icon class: `material-icons`
- [ ] Icon size: verify `20px` or exact value
- [ ] Icon margin-right: verify `15px`
- [ ] Icon alignment: center with text

### 6. Dropdown Menu (Trader)
- [ ] Collapse/expand animation: verify behavior
- [ ] Submenu indentation: verify margin-left
- [ ] Submenu items background: verify hover state
- [ ] "AM", "MT", "CC" mini-icons: verify styling
- [ ] Submenu text: verify font and spacing

### 7. Spacing & Layout
- [ ] Gap between nav items: verify exact margin
- [ ] Sidebar padding: verify top/bottom padding
- [ ] Content padding: verify wrapper padding

## 🔍 Comparison Steps
1. Open both sites side-by-side
2. Use browser DevTools to inspect original sidebar
3. Compare computed styles for each element
4. Document exact differences
5. Update replica CSS to match
6. Rebuild frontend: `cd frontend && npm run build`
7. Refresh and compare again

## 📝 Key Measurements to Capture
- Sidebar width (exact px)
- Logo padding (top, right, bottom, left)
- Logo image dimensions
- Nav item padding
- Nav item margin-bottom
- Icon size and margins
- Active border width and color
- Dropdown submenu indentation
- All font sizes and weights
- All colors (hex values)

## 🧪 Testing Checklist
After completion:
- [ ] Sidebar width matches exactly
- [ ] Gradient colors match pixel-perfect
- [ ] Logo positioned identically
- [ ] Nav items have same spacing
- [ ] Active state matches (border, background, font)
- [ ] Dropdown menu looks identical
- [ ] Icons align properly
- [ ] Hover effects match
- [ ] Responsive behavior matches (if applicable)

## 📌 Notes
- Take screenshots before/after for comparison
- Use browser DevTools to inspect exact computed styles
- Test all navigation states (active, hover, normal)
- Verify dropdown expand/collapse animation

## 🚀 Next Task
After completing this, move to **Task 3: Header/Navbar Exact Match**

