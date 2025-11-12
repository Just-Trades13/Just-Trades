# Task 4: Dashboard Header & Button Exact Match

## 🎯 Goal
Make the dashboard page header section match exactly, including the "Dashboard" title and "VIEWING RECORDED STRATS" button.

## 📍 Reference Sites
- **Original**: `https://trademanagergroup.com/user/dashboard`
- **Replica**: `http://localhost:5001/dashboard`

## 📁 Files to Modify
1. `frontend/src/pages/Dashboard.jsx` - Header structure
2. `frontend/src/pages/Dashboard.css` - Header styles

## ✅ Task Checklist

### 1. Dashboard Header Container
- [ ] Display: verify `flex` layout
- [ ] Justify-content: verify `space-between`
- [ ] Align-items: verify `center`
- [ ] Margin-bottom: verify exact spacing (likely `30px`)
- [ ] Padding: verify if any padding needed

### 2. "Dashboard" Title (h2)
- [ ] Font family: verify `Poppins` or exact font
- [ ] Font size: verify exact size (likely `26px`)
- [ ] Font weight: verify `700` or exact value
- [ ] Color: verify `#ffffff` or exact color
- [ ] Letter spacing: verify `-0.5px` or exact value
- [ ] Margin: verify `0` or exact values
- [ ] Line height: verify if custom

### 3. "VIEWING RECORDED STRATS" Button
- [ ] Background color: verify exact blue (likely `#5e72e4`)
- [ ] Hover background: verify darker blue
- [ ] Text color: verify `#ffffff`
- [ ] Font family: verify `Poppins`
- [ ] Font size: verify exact size (likely `14px`)
- [ ] Font weight: verify `600`
- [ ] Text transform: verify `uppercase`
- [ ] Letter spacing: verify exact value (likely `0.5px`)
- [ ] Padding: verify exact values (likely `10px 20px`)
- [ ] Border: verify `none` or exact border
- [ ] Border radius: verify exact value (likely `6px`)
- [ ] Cursor: verify `pointer`
- [ ] Transition: verify hover transition

### 4. Spacing & Layout
- [ ] Gap between title and button: verify spacing
- [ ] Button alignment: verify right alignment
- [ ] Container width: verify full width or max-width

## 🔍 Comparison Steps
1. Open both sites side-by-side
2. Inspect header section with DevTools
3. Compare title and button computed styles
4. Document exact differences
5. Update Dashboard.css
6. Rebuild: `cd frontend && npm run build`
7. Refresh and compare

## 📝 Key Measurements to Capture
- Header margin-bottom (exact px)
- Title font-size
- Title font-weight
- Title letter-spacing
- Title color (hex)
- Button background-color (hex)
- Button hover background (hex)
- Button padding (all sides)
- Button border-radius
- Button font-size
- Button letter-spacing
- All spacing values

## 🧪 Testing Checklist
After completion:
- [ ] Header layout matches exactly
- [ ] "Dashboard" title matches styling
- [ ] Button matches color and size
- [ ] Button hover effect matches
- [ ] Spacing between elements matches
- [ ] Responsive behavior matches

## 📌 Notes
- Button text is already correct: "VIEWING RECORDED STRATS"
- Verify button is not a link, just a styled button
- Check if button has any click functionality in original

## 🚀 Next Task
After completing this, move to **Task 5: Filter Dropdowns Exact Match**

