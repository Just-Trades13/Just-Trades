# Quick Reference: JSON Parsing Patterns by Scenario

## 📝 How to Find the Correct JSON Reference

**Formula**: `{{OPENAI_MODULE_ID.text.output[0].content[0].text}}`

The OpenAI module ID is the `"id"` number in the JSON blueprint file for the OpenAI module.

---

## ✅ Verified JSON Parsing References

| Scenario | OpenAI Module ID | JSON Parse Reference | Notes |
|----------|------------------|---------------------|-------|
| **A** | 2 | `{{2.result}}` | Uses `CreateCompletion` API (different format) |
| **B** | 3 | `{{3.text.output[0].content[0].text}}` | ✅ Correct |
| **C** | 2 | `{{2.text.output[0].content[0].text}}` | ✅ Correct |
| **D** | 2 (first), 5 (second) | `{{2.text.output[0].content[0].text}}`<br>`{{5.text.output[0].content[0].text}}` | ✅ Correct - Two OpenAI calls |
| **E** | 2 | `{{2.text.output[0].content[0].text}}` | ✅ Correct |
| **F** | 2 | `{{2.text.output[0].content[0].text}}` | ✅ Correct |

---

## 🔍 How to Verify in Make.com

1. **Find the OpenAI module** in your scenario
2. **Look at the module number** (shown above the module icon)
3. **Use that number** in the JSON parse module

**Example**: If OpenAI module shows as "Module 3", use `{{3.text.output[0].content[0].text}}`

---

## ⚠️ Common Mistakes

❌ **Wrong**: Using `{{5.text.output[0].content[0].text}}` for all scenarios  
✅ **Right**: Check the actual OpenAI module ID for each scenario

❌ **Wrong**: Using `{{2.result}}` when OpenAI uses `createModelResponse`  
✅ **Right**: `createModelResponse` uses `.text.output[0].content[0].text`, `CreateCompletion` uses `.result`

---

## 📋 Module Type Reference

- **`openai-gpt-3:createModelResponse`** → Use: `{{ID.text.output[0].content[0].text}}`
- **`openai-gpt-3:CreateCompletion`** → Use: `{{ID.result}}` (legacy API)

