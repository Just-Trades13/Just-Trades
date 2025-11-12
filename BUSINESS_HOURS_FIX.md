# 🔧 Business Hours Filter - Fix Guide

## ⚠️ PROBLEM:
The current filter uses **UTC time**, but Nelson needs **local business hours**.

**Current filter (9 AM - 5 PM UTC):**
```
{{and(contains(["Mon", "Tue", "Wed", "Thu", "Fri"]; formatDate(now(); "E")); ge(toNumber(formatDate(now(); "HH")); 9); le(toNumber(formatDate(now(); "HH")); 17))}}
```

This means emails only send between **9 AM - 5 PM UTC** (which is **3 AM - 11 AM Central Time**).

---

## ✅ SOLUTIONS:

### **Option 1: Central Time (Chicago) - 9 AM to 5 PM CT**
**Nelson's phone: 773 = Chicago area = Central Time**

9 AM - 5 PM CT = **15:00 - 23:00 UTC**

**New filter:**
```
{{and(contains(["Mon", "Tue", "Wed", "Thu", "Fri"]; formatDate(now(); "E")); ge(toNumber(formatDate(now(); "HH")); 15); le(toNumber(formatDate(now(); "HH")); 23))}}
```

---

### **Option 2: Eastern Time - 9 AM to 5 PM ET**

9 AM - 5 PM ET = **14:00 - 22:00 UTC**

**New filter:**
```
{{and(contains(["Mon", "Tue", "Wed", "Thu", "Fri"]; formatDate(now(); "E")); ge(toNumber(formatDate(now(); "HH")); 14); le(toNumber(formatDate(now(); "HH")); 22))}}
```

---

### **Option 3: Pacific Time - 9 AM to 5 PM PT**

9 AM - 5 PM PT = **17:00 - 01:00 UTC** (spans midnight)

**New filter:**
```
{{and(contains(["Mon", "Tue", "Wed", "Thu", "Fri"]; formatDate(now(); "E")); or(and(ge(toNumber(formatDate(now(); "HH")); 17); le(toNumber(formatDate(now(); "HH")); 23)); and(ge(toNumber(formatDate(now(); "HH")); 0); le(toNumber(formatDate(now(); "HH")); 1)))}}
```

---

### **Option 4: Custom Time Range**

If you need different hours, use this formula:
- Replace `15` with your UTC start hour
- Replace `23` with your UTC end hour

**Formula:**
```
{{and(contains(["Mon", "Tue", "Wed", "Thu", "Fri"]; formatDate(now(); "E")); ge(toNumber(formatDate(now(); "HH"))); START_HOUR); le(toNumber(formatDate(now(); "HH")); END_HOUR))}}
```

**UTC Conversion:**
- Central Time (CT): Add 6 hours to local time
- Eastern Time (ET): Add 5 hours to local time  
- Pacific Time (PT): Add 8 hours to local time
- Mountain Time (MT): Add 7 hours to local time

---

## 📝 HOW TO UPDATE IN MAKE.COM:

1. Open your scenario in Make.com
2. Click on **Module 2 (Router)**
3. Click the **wrench icon** on the first route (Business Hours route)
4. Click **"Set up a filter"**
5. In the **Condition** field, click the **"fx"** icon (formula mode)
6. Replace the entire formula with one of the options above
7. Click **"OK"**
8. Save your scenario

---

## 🧪 TESTING:

After updating, test the filter:
1. Check what time it is in UTC: https://time.is/UTC
2. Verify your business hours match the UTC hours in the filter
3. Run a test execution to confirm emails only send during business hours

---

## 💡 RECOMMENDED:

Based on Nelson's phone number (773 = Chicago), use **Option 1 (Central Time)**.

