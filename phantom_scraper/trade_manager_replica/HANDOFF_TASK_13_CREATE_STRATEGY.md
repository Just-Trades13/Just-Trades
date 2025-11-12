# Task 13: Create/Edit Strategy Page Exact Match

## 🎯 Goal
Make the Create/Edit Strategy page match the original exactly, including form layout, field styling, validation, and buttons.

## 📍 Reference Sites
- **Original**: `https://trademanagergroup.com/user/recorders/create` (or similar)
- **Replica**: `http://localhost:5001/recorders/create` or `/recorders/edit/:id`

## 📁 Files to Modify
1. `frontend/src/pages/CreateStrategy.jsx` - Page structure
2. `frontend/src/pages/CreateStrategy.css` - Page styles

## ✅ Task Checklist

### 1. Page Container
- [ ] Background: verify `#000000` or exact color
- [ ] Padding: verify exact values

### 2. Page Header
- [ ] Title: verify "Create Strategy" or "Edit Strategy" based on mode
- [ ] Font styling: verify matches other pages
- [ ] Back button: verify if back link/button exists

### 3. Form Container
- [ ] Background: verify gradient or solid color
- [ ] Padding: verify exact values
- [ ] Border-radius: verify exact value
- [ ] Box-shadow: verify shadow values
- [ ] Border: verify if border present

### 4. Form Fields
- [ ] Strategy name: verify input styling
- [ ] Symbol: verify dropdown/input styling
- [ ] Timeframe: verify dropdown styling
- [ ] Account: verify dropdown styling
- [ ] Entry rules: verify input/textarea styling
- [ ] Exit rules: verify input/textarea styling
- [ ] Risk management: verify input styling
- [ ] All field labels: verify font styling
- [ ] All field spacing: verify margins

### 5. Input Styling
- [ ] Background: verify `#0f172a` or exact color
- [ ] Border: verify `1px solid rgba(255, 255, 255, 0.1)`
- [ ] Border-radius: verify `4px`
- [ ] Padding: verify `10px 15px`
- [ ] Color: verify text color `#f2f2f2`
- [ ] Font family: verify `Poppins`
- [ ] Focus state: verify border color change

### 6. Textarea Fields
- [ ] Same styling as inputs
- [ ] Min-height: verify if set
- [ ] Resize: verify if resizable

### 7. Select/Dropdown Fields
- [ ] Same styling as inputs
- [ ] Dropdown arrow: verify styling
- [ ] Option styling: verify hover states

### 8. Form Buttons
- [ ] Save/Submit button: verify styling
- [ ] Cancel button: verify styling
- [ ] Button container: verify layout
- [ ] Button spacing: verify gap
- [ ] Button colors: verify exact colors

### 9. Validation
- [ ] Error messages: verify styling
- [ ] Error colors: verify `#fd5d93` or exact color
- [ ] Required field indicators: verify if asterisks present
- [ ] Inline validation: verify if real-time validation

### 10. Form Layout
- [ ] Grid/Columns: verify if multi-column layout
- [ ] Field grouping: verify if fields are grouped
- [ ] Section dividers: verify if sections separated

## 🔍 Comparison Steps
1. Navigate to Create Strategy page on original site
2. Open replica Create Strategy page
3. Compare page header
4. Compare form container
5. Compare each form field
6. Compare input styling
7. Compare button styling
8. Test form validation
9. Document exact differences
10. Update CreateStrategy.jsx and CreateStrategy.css
11. Rebuild: `cd frontend && npm run build`
12. Refresh and verify

## 📝 Key Measurements to Capture
- Page container padding
- Header font-size
- Form container styling
- Input field styling (all properties)
- Label font-size and spacing
- Button styling
- Error message styling
- Field spacing
- All spacing values

## 🧪 Testing Checklist
After completion:
- [ ] Page header matches
- [ ] Form container matches
- [ ] All form fields match
- [ ] Input styling matches
- [ ] Button styling matches
- [ ] Validation messages match
- [ ] Form layout matches
- [ ] Responsive behavior matches

## 📌 Notes
- Form fields should match Dashboard filter styling
- Verify if form has auto-save functionality
- Check if there are any tooltips or help text
- Verify if Edit mode pre-fills all fields

## 🚀 Next Task
After completing this, move to **Task 14: Final Polish & Testing**

