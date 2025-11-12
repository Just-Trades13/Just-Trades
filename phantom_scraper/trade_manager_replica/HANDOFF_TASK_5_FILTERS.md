# Task 5: Filter Dropdowns Exact Match

## 🎯 Goal
Make the dashboard filter dropdowns match the original exactly, including all styling, spacing, and the "Show All Card" link.

## 📍 Reference Sites
- **Original**: `https://trademanagergroup.com/user/dashboard`
- **Replica**: `http://localhost:5001/dashboard`

## 📁 Files to Modify
1. `frontend/src/pages/Dashboard.jsx` - Filter structure
2. `frontend/src/pages/Dashboard.css` - Filter styles

## ✅ Task Checklist

### 1. Filters Container
- [ ] Display: verify `flex` layout
- [ ] Gap: verify exact gap between items (likely `15px`)
- [ ] Flex-wrap: verify `wrap` or `nowrap`
- [ ] Margin-bottom: verify exact spacing (likely `30px`)
- [ ] Alignment: verify alignment values

### 2. Select Dropdowns (User, Strategy, Symbol, TimeFrame)
- [ ] Background color: verify exact dark blue (likely `#0f172a`)
- [ ] Border: verify `1px solid rgba(255, 255, 255, 0.1)`
- [ ] Border radius: verify exact value (likely `4px`)
- [ ] Padding: verify exact values (likely `10px 15px`)
- [ ] Color: verify text color (likely `#f2f2f2`)
- [ ] Font family: verify `Poppins`
- [ ] Font size: verify exact size (likely `14px`)
- [ ] Min-width: verify if set (likely `150px`)
- [ ] Height: verify if custom height
- [ ] Focus state: verify border color change (likely `#5e72e4`)
- [ ] Focus outline: verify `none`

### 3. Dropdown Options
- [ ] Option background: verify default option styling
- [ ] Option color: verify text color
- [ ] Hover state: verify option hover styling

### 4. "Show All Card" Link
- [ ] Text: verify "Show All Card" or exact text
- [ ] Color: verify exact color (likely `#5e72e4`)
- [ ] Text decoration: verify `none`
- [ ] Margin-left: verify spacing (likely `15px`)
- [ ] Font size: verify if different from selects
- [ ] Font weight: verify if bold
- [ ] Display: verify `flex` and `align-items: center`
- [ ] Hover state: verify hover effect

### 5. Labels (if present)
- [ ] Label text: verify if labels exist above dropdowns
- [ ] Label styling: verify font, size, color
- [ ] Label spacing: verify margin-bottom

### 6. Spacing & Layout
- [ ] Gap between filters: verify exact spacing
- [ ] Alignment: verify vertical alignment
- [ ] Responsive: verify mobile wrapping behavior

## 🔍 Comparison Steps
1. Open both sites side-by-side
2. Inspect filter section with DevTools
3. Compare each dropdown's computed styles
4. Test focus states
5. Compare "Show All Card" link
6. Document exact differences
7. Update Dashboard.css
8. Rebuild: `cd frontend && npm run build`
9. Refresh and verify

## 📝 Key Measurements to Capture
- Container gap (exact px)
- Container margin-bottom
- Select background-color (hex)
- Select border color and width
- Select padding (all sides)
- Select border-radius
- Select font-size
- Select min-width
- Focus border-color (hex)
- "Show All Card" color (hex)
- "Show All Card" margin-left
- All spacing values

## 🧪 Testing Checklist
After completion:
- [ ] Filter container layout matches
- [ ] All dropdowns match styling exactly
- [ ] Dropdown focus states match
- [ ] "Show All Card" link matches
- [ ] Spacing between elements matches
- [ ] Responsive behavior matches

## 📌 Notes
- Current dropdown options are placeholder - verify actual options in original
- Check if dropdowns have any icons or special styling
- Verify dropdown arrow styling if custom

## 🚀 Next Task
After completing this, move to **Task 6: Summary Cards Exact Match**

