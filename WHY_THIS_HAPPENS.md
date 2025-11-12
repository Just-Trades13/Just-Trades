# Why I See Data But Make.com Doesn't

## 🎯 THE ANSWER

**The API key works perfectly!** The problem is **HOW Make.com structures the response**.

---

## 📊 COMPARISON

### What I Did (Direct API Call)
```python
import requests

response = requests.post(
    "https://api.apollo.io/v1/mixed_people/search",
    headers={"X-Api-Key": "your_key"},
    json={"q_keywords": "homeowner"}
)

# Returns clean data:
{
    "people": [
        {
            "first_name": "John",
            "email": "john@example.com",
            ...
        }
    ]
}
```

### What Make.com Does (HTTP Module)
```json
Module 18 output (probably):
{
    "status": 200,
    "body": {
        "people": [...]
    },
    "headers": [...],
    ...
}
```

**Make.com WRAPS the response!** We need to know WHERE it puts the data.

---

## 🔧 WHAT WE NEED

**Run your scenario and look at Module 18's output bundle.**

Tell me:
- What fields do you see?
- Where is the `people` array?
- What's the exact structure?

Then I can fix it with one line change! 🚀

---

## ✅ ONCE WE KNOW

I'll update the blueprint with the correct path:
- Maybe: `{{`18.body.people[0]`}}`
- Maybe: `{{`18.data.people[0]`}}`
- Maybe: `{{`18.people[0]`}}`
- Or something else!

**The API key is fine - just need the right path!**

