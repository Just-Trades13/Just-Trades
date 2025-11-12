# Quick Reference: JSON Parsing Patterns by Scenario (Package 5A)

## 📝 How to Find the Correct JSON Reference

**Formula**: `{{OPENAI_MODULE_ID.text.output[0].content[0].text}}`

The OpenAI module ID is the `"id"` number in the JSON blueprint file for the OpenAI module.

---

## ✅ Verified JSON Parsing References

| Scenario | OpenAI Module ID | JSON Parse Reference | Notes |
|----------|------------------|---------------------|-------|
| **5A-A** | 5 | `{{5.text.output[0].content[0].text}}` | ✅ Correct |
| **5A-B** | 2 (first), 5 (second) | `{{2.text.output[0].content[0].text}}`<br>`{{5.text.output[0].content[0].text}}` | ✅ Correct - Two OpenAI calls |
| **5A-C** | 2 | `{{2.text.output[0].content[0].text}}` | ✅ Correct |
| **5A-D** | 3 (first), 9 (second) | `{{3.text.output[0].content[0].text}}`<br>`{{9.text.output[0].content[0].text}}` | ✅ Correct - Two OpenAI calls |
| **5A-E** | 3 | `{{3.text.output[0].content[0].text}}` | ✅ Correct |
| **5A-F** | 3 | `{{3.text.output[0].content[0].text}}` | ✅ Correct |

---

## 🔍 How to Verify in Make.com

1. **Find the OpenAI module** in your scenario
2. **Look at the module number** (shown above the module icon)
3. **Use that number** in the JSON parse module

**Example**: If OpenAI module shows as "Module 5", use `{{5.text.output[0].content[0].text}}`

---

## ⚠️ Common Mistakes

❌ **Wrong**: Using `{{5.text.output[0].content[0].text}}` for all scenarios  
✅ **Right**: Check the actual OpenAI module ID for each scenario

❌ **Wrong**: Using `{{2.result}}` when OpenAI uses `createModelResponse`  
✅ **Right**: `createModelResponse` uses `.text.output[0].content[0].text`

❌ **Wrong**: Missing array brackets `[0]`  
✅ **Right**: Always include `[0]` for array access

---

## 📋 Module Type Reference

- **`openai-gpt-3:createModelResponse`** → Use: `{{ID.text.output[0].content[0].text}}`
- **`openai-gpt-3:CreateCompletion`** → Use: `{{ID.result}}` (legacy API - not used in Package 5A)

---

## 🎯 Package 5A Specific Notes

- **All scenarios use `openai-gpt-3:createModelResponse`** - consistent API format
- **Pattern is consistent**: `{{ID.text.output[0].content[0].text}}` for all AI modules
- **Scenarios 5A-B and 5A-D**: Use multiple OpenAI modules - verify each JSON parse references the correct module ID

---

**Last Updated**: 2025-01-XX  
**Package**: Package 5A - AI Quote & Appointment Builder Suite

