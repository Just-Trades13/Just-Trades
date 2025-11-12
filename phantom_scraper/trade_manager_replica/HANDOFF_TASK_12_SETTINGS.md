# Task 12: Settings Page Exact Match

## 🎯 Goal
Make the Settings page match the original exactly, including all sections: username change, password change, notifications, and Discord integration.

## 📍 Reference Sites
- **Original**: `https://trademanagergroup.com/user/settings` (or similar)
- **Replica**: `http://localhost:5001/settings`

## 📁 Files to Modify
1. `frontend/src/pages/Settings.jsx` - Page structure
2. `frontend/src/pages/Settings.css` - Page styles

## ✅ Task Checklist

### 1. Page Container
- [ ] Background: verify `#000000` or exact color
- [ ] Padding: verify exact values

### 2. Page Header
- [ ] Title: verify "Settings" or exact text
- [ ] Font styling: verify matches other pages

### 3. Settings Container
- [ ] Background: verify gradient or solid color
- [ ] Padding: verify exact values
- [ ] Border-radius: verify exact value
- [ ] Box-shadow: verify shadow values
- [ ] Border: verify if border present

### 4. Sign Out Section
- [ ] Link/button: verify "Sign Out" text and styling
- [ ] Position: verify where it's located
- [ ] Color: verify link color
- [ ] Hover: verify hover effect

### 5. Change Username Section
- [ ] Title: verify "Change Your Username" or exact text
- [ ] Input field: verify styling matches form controls
- [ ] Current username: verify if displayed
- [ ] Update button: verify styling
- [ ] Button text: verify "Update" or exact text

### 6. Change Password Section
- [ ] Title: verify "Change Password" or exact text
- [ ] Current password: verify if field exists
- [ ] New password: verify input styling
- [ ] Confirm password: verify input styling
- [ ] Password strength indicator: verify styling
  - [ ] Weak/Medium/Strong colors
  - [ ] Strength bar or text
- [ ] Update button: verify styling

### 7. Notifications Section
- [ ] Title: verify section title
- [ ] Toggle switches: verify styling (not checkboxes)
- [ ] "Push Notification" toggle: verify label and switch
- [ ] "Discord DM" toggle: verify label and switch
- [ ] Toggle colors: verify on/off state colors

### 8. Discord Integration
- [ ] Discord status: verify if shows "Linked" or "Not Linked"
- [ ] Discord avatar: verify if avatar displayed when linked
- [ ] Link button: verify "Link Discord" button styling
- [ ] Unlink button: verify if present and styling
- [ ] Avatar size: verify dimensions

### 9. Section Styling
- [ ] Section headers (h3): verify font styling
- [ ] Section spacing: verify margin between sections
- [ ] Section borders: verify if dividers present

## 🔍 Comparison Steps
1. Navigate to Settings page on original site
2. Open replica Settings page
3. Compare page header
4. Compare settings container
5. Compare each section (username, password, notifications, Discord)
6. Compare form inputs
7. Compare toggle switches
8. Compare buttons
9. Test password strength indicator
10. Document exact differences
11. Update Settings.jsx and Settings.css
12. Rebuild: `cd frontend && npm run build`
13. Refresh and verify

## 📝 Key Measurements to Capture
- Page container padding
- Header font-size
- Settings container styling (gradient, padding, border-radius)
- Section title font-size
- Input field styling
- Button styling
- Toggle switch dimensions and colors
- Password strength indicator styling
- Discord avatar size
- Section spacing
- All spacing values

## 🧪 Testing Checklist
After completion:
- [ ] Page header matches
- [ ] Settings container matches
- [ ] All sections match
- [ ] Form inputs match
- [ ] Toggle switches match
- [ ] Password strength indicator matches
- [ ] Discord section matches
- [ ] All buttons match
- [ ] Responsive behavior matches

## 📌 Notes
- Toggle switches should match Control Center toggles
- Password strength should update in real-time
- Verify if Discord avatar is circular
- Check if there are any success/error messages

## 🚀 Next Task
After completing this, move to **Task 13: Create/Edit Strategy Page**

