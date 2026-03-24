# SETUP GUIDE: Fix OpenAI API Key Error

## Step 1: Get a Valid API Key

1. Go to: https://platform.openai.com/account/api-keys
2. Sign in with your OpenAI account (create one if you don't have it)
3. Click: **"Create new secret key"**
4. Copy the key immediately (you can only see it once!)

## Step 2: Verify Your Account Has Billing

Before the API key will work:
1. Go to: https://platform.openai.com/account/billing/overview
2. Check that you have:
   - ✅ A valid payment method on file
   - ✅ Billing enabled (not a free trial or expired trial)
   - ✅ Positive balance or credit

## Step 3: Update Your .env File

Replace the invalid key in `.env` with your new key:

```
OPENAI_API_KEY=sk-proj-[YOUR-NEW-KEY-HERE]
```

**Important:** 
- Keep the format: `OPENAI_API_KEY=your-full-key`
- Do NOT add quotes around the key
- Do NOT share this key with anyone

## Step 4: Restart Your Flask App

After updating `.env`, restart the application:

```bash
python app.py
```

## Step 5: Test the Fix

Try using the diagnosis feature or run the test script:

```bash
python test_api.py
```

You should see: ✅ API Key is VALID!

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Invalid API key" | Your key is wrong or API key format is incorrect |
| "Rate limit exceeded" | You've made too many requests; wait a few minutes |
| "Billing required" | Add a payment method at https://platform.openai.com/account/billing |
| "API key not found" | Make sure `.env` file exists and has `OPENAI_API_KEY=sk-...` |

Need help? Contact OpenAI support at: https://help.openai.com
