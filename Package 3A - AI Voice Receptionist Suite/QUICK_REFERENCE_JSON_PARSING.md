# Quick Reference: JSON Parsing Patterns by Scenario (Package 3A)

## 📝 How to Find the Correct JSON Reference

**Formula**: `{{OPENAI_MODULE_ID.text.output[0].content[0].text}}`

The OpenAI module ID is the `"id"` number in the JSON blueprint file for the OpenAI module.

---

## ✅ Verified JSON Parsing References

| Scenario | OpenAI Module ID | JSON Parse Reference | Notes |
|----------|------------------|---------------------|-------|
| **3A-A** | 3 | `{{3.text.output[0].content[0].text}}` | ✅ Correct |
| **3A-B** | 3 | `{{3.text.output[0].content[0].text}}` | ✅ Correct |
| **3A-C** | 3 | `{{3.text.output[0].content[0].text}}` | ✅ Correct |
| **3A-D** | 3 | `{{3.text.output[0].content[0].text}}` | ✅ Correct |
| **3A-E** | 4 | `{{4.text.output[0].content[0].text}}` | ✅ Correct |
| **3A-F** | 2 | `{{2.text.output[0].content[0].text}}` | ✅ Correct |

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
- **`openai-gpt-3:CreateCompletion`** → Use: `{{ID.result}}` (legacy API, not used in Package 3A)

---

## 📊 Package 3A Specific Notes

**All Package 3A scenarios use `openai-gpt-3:createModelResponse`**, so the pattern is consistent:
- Format: `{{MODULE_ID.text.output[0].content[0].text}}`
- Just replace `MODULE_ID` with the actual module number

**JSON Output Structure**:
All scenarios return JSON objects from OpenAI. The parsed JSON will have fields like:
- `response` - The AI-generated text response
- `intent` - Caller intent classification
- `booking_requested` - Boolean for booking scenarios
- `should_transfer` - Boolean for routing scenarios
- Other scenario-specific fields

---

## 📋 Scenario-Specific JSON Fields

### Scenario 3A-A (Basic Voice Receptionist)
```json
{
  "response": "string",
  "intent": "question|inquiry|complaint|booking|information|goodbye",
  "needs_followup": boolean,
  "booking_requested": boolean,
  "should_transfer": boolean,
  "transfer_reason": "string"
}
```

### Scenario 3A-B (Voice with Booking)
```json
{
  "response": "string",
  "intent": "string",
  "booking_requested": boolean,
  "booking_confirmed": boolean,
  "booking_details": {
    "name": "string",
    "preferred_date": "string",
    "preferred_time": "string",
    "reason": "string",
    "confirmed_slot": "string"
  },
  "available_slots": ["string"],
  "needs_more_info": boolean
}
```

### Scenario 3A-C (Voice with Routing)
```json
{
  "response": "string",
  "intent": "string",
  "should_transfer": boolean,
  "transfer_department": "Sales|Support|Billing|Technical",
  "transfer_reason": "string",
  "transfer_number": "string",
  "needs_followup": boolean
}
```

### Scenario 3A-D (Advanced Voice)
```json
{
  "response": "string",
  "intent": "string",
  "conversation_stage": "greeting|qualification|booking|routing|closing",
  "booking_requested": boolean,
  "booking_confirmed": boolean,
  "booking_details": {...},
  "should_transfer": boolean,
  "transfer_department": "string",
  "lead_score": number,
  "key_qualifiers": ["string"],
  "needs_followup": boolean,
  "followup_method": "email|sms|none"
}
```

### Scenario 3A-E (Voice with Transcription)
```json
{
  "summary": "string",
  "key_points": ["string"],
  "caller_intent": "string",
  "action_items": ["string"],
  "next_steps": "string",
  "pricing_discussed": boolean,
  "budget_mentioned": "string",
  "decision_maker": boolean,
  "urgency_level": "low|medium|high|urgent",
  "call_outcome": "string",
  "call_quality_score": number,
  "important_details": "string",
  "followup_required": boolean,
  "followup_method": "string"
}
```

### Scenario 3A-F (Voice Analytics)
```json
{
  "total_calls": number,
  "period": "string",
  "booking_rate": number,
  "common_intents": ["string"],
  "common_topics": ["string"],
  "peak_times": ["string"],
  "avg_call_quality": number,
  "conversion_trend": "string",
  "insights": ["string"],
  "recommendations": ["string"],
  "summary": "string"
}
```

---

**Last Updated**: 2025-01-XX  
**Package**: Package 3A - AI Voice Receptionist Suite

