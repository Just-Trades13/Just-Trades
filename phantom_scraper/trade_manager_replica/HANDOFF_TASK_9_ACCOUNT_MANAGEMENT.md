# Task 9: Account Management Page Exact Match

## 🎯 Goal
Make the Account Management page match the original exactly, including header, account cards, search, and bulk actions.

## 📍 Reference Sites
- **Original**: `https://trademanagergroup.com/user/accounts` (or similar)
- **Replica**: `http://localhost:5001/trader/accounts`

## 📁 Files to Modify
1. `frontend/src/pages/AccountManagement.jsx` - Page structure
2. `frontend/src/pages/AccountManagement.css` - Page styles

## ✅ Task Checklist

### 1. Page Container
- [ ] Background: verify `#000000` or exact color
- [ ] Padding: verify exact values

### 2. Page Header
- [ ] Title: verify "Account Management" or exact text
- [ ] Subtitle: verify if description text exists
- [ ] Font styling: verify matches other pages
- [ ] Button: verify if "Add Account" button exists

### 3. Search Bar
- [ ] Input field: verify styling
- [ ] Placeholder: verify placeholder text
- [ ] Position: verify alignment
- [ ] Icon: verify if search icon present

### 4. Bulk Actions
- [ ] Container: verify positioning
- [ ] "Bulk Delete" button: verify styling
- [ ] "Clear Trades" button: verify styling
- [ ] Button spacing: verify margins
- [ ] Disabled state: verify when no selection

### 5. Account Cards/List
- [ ] Card container: verify styling (matches summary cards?)
- [ ] Checkbox: verify styling and position
- [ ] Account name: verify font styling
- [ ] Account info: verify what details are shown
- [ ] Action buttons: verify "Edit Account Credentials" and "Refresh SubAccount"
- [ ] Button styling: verify exact colors and sizes
- [ ] Card spacing: verify gap between cards
- [ ] Hover effect: verify card hover state

### 6. Empty State
- [ ] Message: verify "No accounts" text
- [ ] Styling: verify text styling

### 7. Modal/Dialog (if present)
- [ ] Edit modal: verify styling if edit opens modal
- [ ] Form fields: verify input styling
- [ ] Submit button: verify styling

## 🔍 Comparison Steps
1. Navigate to Account Management page on original site
2. Open replica Account Management page
3. Compare page header
4. Compare search bar
5. Compare bulk action buttons
6. Compare account cards/list
7. Compare action buttons
8. Test checkbox selection
9. Test bulk actions
10. Document exact differences
11. Update AccountManagement.jsx and AccountManagement.css
12. Rebuild: `cd frontend && npm run build`
13. Refresh and verify

## 📝 Key Measurements to Capture
- Page container padding
- Header font-size and spacing
- Search input styling
- Bulk action button styling
- Account card styling (gradient, padding, border-radius)
- Checkbox size and styling
- Action button styling
- Card gap/spacing
- All spacing values

## 🧪 Testing Checklist
After completion:
- [ ] Page header matches
- [ ] Search bar matches
- [ ] Bulk action buttons match
- [ ] Account cards match
- [ ] Checkboxes match
- [ ] Action buttons match
- [ ] Hover effects match
- [ ] Empty state matches
- [ ] Responsive behavior matches

## 📌 Notes
- Account cards might use same gradient as summary cards
- Verify if accounts are cards or table format
- Check if there are account status indicators
- Verify button text exactly: "Edit Account Credentials" and "Refresh SubAccount"

## 🚀 Next Task
After completing this, move to **Task 10: My Trader Page**

