# Quick Reference: JSON Parsing Patterns by Scenario - Package 4A

## 📝 How to Find the Correct JSON Reference

**Formula**: `{{OPENAI_MODULE_ID.text.output[0].content[0].text}}`

The OpenAI module ID is the `"id"` number in the JSON blueprint file for the OpenAI module.

---

## ✅ Verified JSON Parsing References

| Scenario | OpenAI Module ID(s) | JSON Parse Reference | Notes |
|----------|---------------------|---------------------|-------|
| **4A-A** | 3 (email), 6 (SMS) | `{{3.text.output[0].content[0].text}}`<br>`{{6.text.output[0].content[0].text}}` | ✅ Two paths - email and SMS |
| **4A-B** | 3, 4, 5 (per segment) | `{{3.text.output[0].content[0].text}}`<br>`{{4.text.output[0].content[0].text}}`<br>`{{5.text.output[0].content[0].text}}` | ✅ Three segments - parsed via modules 6, 7, 8 |
| **4A-C** | 2 | `{{2.text.output[0].content[0].text}}` | ✅ Correct |
| **4A-D** | 3, 4, 5 (per stage) | Conditional: `{{IF({{1.Reactivation Stage}} = "stage_1", {{3.text.output[0].content[0].text}}, IF({{1.Reactivation Stage}} = "stage_2", {{4.text.output[0].content[0].text}}, {{5.text.output[0].content[0].text}})}}` | ✅ Three stages - conditional parsing via module 6 |
| **4A-E** | 3 (high), 4 (medium) | Conditional: `{{IF({{1.Lead Score}} >= 75, {{3.text.output[0].content[0].text}}, {{4.text.output[0].content[0].text}})}}` | ✅ Two priorities - conditional parsing via module 5 |
| **4A-F** | 5 | `{{5.text.output[0].content[0].text}}` | ✅ Correct |

---

## 🔍 How to Verify in Make.com

1. **Find the OpenAI module** in your scenario
2. **Look at the module number** (shown above the module icon)
3. **Use that number** in the JSON parse module

**Example**: If OpenAI module shows as "Module 3", use `{{3.text.output[0].content[0].text}}`

---

## ⚠️ Common Mistakes

❌ **Wrong**: Using `{{2.text.output[0].content[0].text}}` for all scenarios  
✅ **Right**: Check the actual OpenAI module ID for each scenario

❌ **Wrong**: Using `{{5.result}}` when OpenAI uses `createModelResponse`  
✅ **Right**: `createModelResponse` uses `.text.output[0].content[0].text`, `CreateCompletion` uses `.result`

❌ **Wrong**: Forgetting conditional logic in multi-path scenarios (4A-A, 4A-B, 4A-D, 4A-E)  
✅ **Right**: Use the correct module ID based on which path is active (check router output)

---

## 📋 Module Type Reference

- **`openai-gpt-3:createModelResponse`** → Use: `{{ID.text.output[0].content[0].text}}`
- **`openai-gpt-3:CreateCompletion`** → Use: `{{ID.result}}` (legacy API - not used in Package 4A)

---

## 🔧 Special Cases

### Scenario 4A-A (Dual Path)
- **Email path**: Module 3 → Parse via Module 4 → Use `{{3.text.output[0].content[0].text}}`
- **SMS path**: Module 6 → Parse via Module 7 → Use `{{6.text.output[0].content[0].text}}`

### Scenario 4A-B (Three Segments)
- **Cold 30d**: Module 3 → Parse via Module 6
- **No Reply 14d**: Module 4 → Parse via Module 7
- **No Show**: Module 5 → Parse via Module 8
- Router determines which parse module to use

### Scenario 4A-D (Three Stages with Conditional)
- **Stage 1**: Module 3 → Conditional parse via Module 6
- **Stage 2**: Module 4 → Conditional parse via Module 6
- **Stage 3**: Module 5 → Conditional parse via Module 6
- Module 6 uses conditional formula to select correct OpenAI output

### Scenario 4A-E (Two Priorities with Conditional)
- **High Score (≥75)**: Module 3 → Conditional parse via Module 5
- **Medium Score (50-74)**: Module 4 → Conditional parse via Module 5
- Module 5 uses conditional formula based on Lead Score

---

## 🧪 Testing JSON Parsing

1. **Run scenario** with test data
2. **Check OpenAI module output** - verify JSON is returned
3. **Check Parse JSON module** - verify it parses correctly
4. **Check next module** - verify parsed data flows correctly

If parsing fails:
- Verify OpenAI returned valid JSON
- Check module ID matches reference
- Verify JSON structure matches expected format
- Check for syntax errors in conditional formulas

---

## 📚 Quick Reference Table

| Scenario | Parse Module ID | Reference Formula |
|----------|----------------|-------------------|
| 4A-A (Email) | 4 | `{{3.text.output[0].content[0].text}}` |
| 4A-A (SMS) | 7 | `{{6.text.output[0].content[0].text}}` |
| 4A-B (Cold) | 6 | `{{3.text.output[0].content[0].text}}` |
| 4A-B (No Reply) | 7 | `{{4.text.output[0].content[0].text}}` |
| 4A-B (No Show) | 8 | `{{5.text.output[0].content[0].text}}` |
| 4A-C | 3 | `{{2.text.output[0].content[0].text}}` |
| 4A-D | 6 | Conditional (see above) |
| 4A-E | 5 | Conditional (see above) |
| 4A-F | 6 | `{{5.text.output[0].content[0].text}}` |

---

**Last Updated**: 2025-01-XX  
**Package**: Package 4A - Lead Reactivation Suite

