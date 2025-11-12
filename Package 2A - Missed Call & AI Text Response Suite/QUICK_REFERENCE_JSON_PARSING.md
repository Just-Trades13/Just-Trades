# Quick Reference: JSON Parsing Patterns by Scenario (Package 2A)

## 📝 How to Find the Correct JSON Reference

**Formula**: `{{OPENAI_MODULE_ID.text.output[0].content[0].text}}`

The OpenAI module ID is the `"id"` number in the JSON blueprint file for the OpenAI module.

---

## ✅ Verified JSON Parsing References

| Scenario | OpenAI Module ID | JSON Parse Reference | Notes |
|----------|------------------|---------------------|-------|
| **2A-A** | N/A | N/A | No OpenAI - direct SMS |
| **2A-B** | 4 | `{{4.text.output[0].content[0].text}}` | ✅ Correct |
| **2A-C** | 3 | `{{3.text.output[0].content[0].text}}` | ✅ Correct |
| **2A-D** | 6 | `{{6.text.output[0].content[0].text}}` | ✅ Correct |
| **2A-E** | 3 | `{{3.text.output[0].content[0].text}}` | ✅ Correct |
| **2A-F** | 3 | `{{3.text.output[0].content[0].text}}` | ✅ Correct |

---

## 🔍 How to Verify in Make.com

1. **Find the OpenAI module** in your scenario
2. **Look at the module number** (shown above the module icon)
3. **Use that number** in the JSON parse module

**Example**: If OpenAI module shows as "Module 3", use `{{3.text.output[0].content[0].text}}`

---

## ⚠️ Common Mistakes

❌ **Wrong**: Using `{{4.text.output[0].content[0].text}}` for all scenarios  
✅ **Right**: Check the actual OpenAI module ID for each scenario

❌ **Wrong**: Using `{{2.result}}` when OpenAI uses `createModelResponse`  
✅ **Right**: `createModelResponse` uses `.text.output[0].content[0].text`, `CreateCompletion` uses `.result`

---

## 📋 Module Type Reference

- **`openai-gpt-3:createModelResponse`** → Use: `{{ID.text.output[0].content[0].text}}`
- **`openai-gpt-3:CreateCompletion`** → Use: `{{ID.result}}` (legacy API, not used in Package 2A)

---

## 📊 Package 2A Specific Notes

**All Package 2A scenarios use `openai-gpt-3:createModelResponse`**, so the pattern is consistent:
- Format: `{{MODULE_ID.text.output[0].content[0].text}}`
- Just replace `MODULE_ID` with the actual module number

**Scenario 2A-A** doesn't use OpenAI - it sends a direct SMS response.

