# QuickBooks End-to-End Testing Guide

## 🎉 Good News!

**Everything is already built and ready to test!**

✅ Backend: QuickBooks integration endpoints
✅ Frontend: QuickBooks connection UI (matches Gmail/Outlook/Drive)
✅ OAuth flow: Already configured in oauth.py

---

## What You Need to Configure

### 1. Nango Dashboard Setup

1. Go to [Nango Dashboard](https://app.nango.dev/prod)
2. Click **Integrations** → **Add Integration**
3. Search for **QuickBooks Online**
4. Provider Config Key: `quickbooks`
5. Add your Intuit OAuth credentials:
   - Get from: https://developer.intuit.com/app/developer/qbo/docs/get-started
   - Client ID: `<from Intuit Developer Portal>`
   - Client Secret: `<from Intuit Developer Portal>`

### 2. Backend Environment Variable

Add to your backend `.env`:
```bash
NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks
```

Then restart your backend:
```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/CORTEX
uvicorn main:app --reload
```

### 3. Verify Frontend is Running

```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/connectorfrontend
npm run dev
```

Frontend should be at: http://localhost:3000

---

## Testing the Full Flow

### Step 1: Connect QuickBooks (OAuth)

1. Open http://localhost:3000 in your browser
2. Log in with your account
3. Go to **Connections** page (sidebar)
4. You should see 4 connection cards:
   - Outlook (blue)
   - Gmail (red)
   - Google Drive (cyan)
   - **QuickBooks (green)** ← This is the new one!

5. Click **"Connect QuickBooks"** button
6. OAuth popup will open → Log in to QuickBooks
7. Select your company
8. Authorize CORTEX
9. Popup closes → You're redirected back
10. QuickBooks card should show **"Connected"** with green badge

### Step 2: Verify Connection Status

Check the **"Connection Status"** section at the bottom of the page.

You should see:
```
QuickBooks: ✓ Active
```

### Step 3: Test Data Fetching (Backend)

Now that OAuth is connected, test the backend endpoints:

#### 3.1 Explore All Data

```bash
# Get your JWT token from frontend (localStorage or cookies)
TOKEN="your_jwt_token_here"

curl -X GET "http://localhost:8080/integrations/quickbooks/explore" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.'
```

**Expected Response:**
```json
{
  "success": true,
  "user_id": "user-123",
  "data": {
    "accounts": [
      {
        "id": "1",
        "name": "Checking Account",
        "account_type": "Bank",
        "current_balance": 125000.00
      }
    ],
    "invoices": [
      {
        "id": "892",
        "doc_number": "INV-892",
        "customer_name": "Acme Corp",
        "total": 12500.00,
        "balance": 0.00,
        "date": "2025-10-26"
      }
    ],
    "customers": [...],
    "bills": [...],
    "payments": [...]
  }
}
```

#### 3.2 Get Clean Summary

```bash
curl -X GET "http://localhost:8080/integrations/quickbooks/summary?time_range=this_month" \
  -H "Authorization: Bearer $TOKEN" \
  | jq '.'
```

**Expected Response:**
```json
{
  "success": true,
  "time_range": "this_month",
  "revenue": 47500.00,
  "expenses": 22000.00,
  "net_income": 25500.00,
  "outstanding_invoices": 26000.00,
  "cash_on_hand": 125000.00,
  "top_customers": [
    {"name": "Acme Corp", "total": 12500},
    {"name": "Precision Plastics", "total": 20000}
  ],
  "top_vendors": [
    {"name": "Steel Supplier Inc", "total": 8000}
  ],
  "recent_invoices": [
    {
      "id": "892",
      "doc_number": "INV-892",
      "customer": "Acme Corp",
      "total": 12500.00,
      "balance": 0.00,
      "date": "2025-10-26",
      "status": "Paid"
    }
  ],
  "data_counts": {
    "total_invoices": 142,
    "total_bills": 58,
    "total_customers": 23,
    "total_payments": 67
  }
}
```

---

## What the UI Looks Like

### Connections Page (Before Connection)

```
┌────────────────────────────────────────────────────────────┐
│  QuickBooks                               [Not Connected]  │
│  ┌────────┐                                                 │
│  │   $    │  QuickBooks                                     │
│  └────────┘  Accounting data                                │
│                                                              │
│  [Connect QuickBooks] ← Green gradient button               │
└────────────────────────────────────────────────────────────┘
```

### After Connection

```
┌────────────────────────────────────────────────────────────┐
│  QuickBooks                                    [Connected]  │
│  ┌────────┐                                                 │
│  │   $    │  QuickBooks                                     │
│  └────────┘  Accounting data                                │
│                                                              │
│  [Connected] ← Disabled, green gradient                     │
└────────────────────────────────────────────────────────────┘
```

### Connection Status Panel

```
┌────────────────────────────────────────────────────────────┐
│  🔌 Connection Status                                       │
├────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Outlook     │  │ Gmail       │  │ Google Dr.  │        │
│  │ ✓ Active    │  │ ✓ Active    │  │ ✓ Active    │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                              │
│  ┌─────────────┐                                            │
│  │ QuickBooks  │                                            │
│  │ ✓ Active    │ ← This should show after connecting       │
│  └─────────────┘                                            │
└────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### Issue: "Connect QuickBooks" button does nothing

**Solution:**
1. Check browser console for errors
2. Verify `NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks` in backend `.env`
3. Restart backend after adding env var
4. Check backend logs: `uvicorn main:app --reload`

### Issue: OAuth popup opens but shows error

**Solution:**
1. Verify QuickBooks integration exists in Nango dashboard
2. Check Intuit OAuth credentials are correct
3. Make sure Nango's redirect URL is whitelisted in Intuit Developer Portal
4. Try sandbox mode first (easier for testing)

### Issue: Backend returns empty data arrays

**Solution:**
1. QuickBooks Sandbox has limited sample data
2. Try connecting a real Production company
3. Check Nango sync status in dashboard
4. Verify OAuth scopes include `com.intuit.quickbooks.accounting`

### Issue: Field names don't match (e.g., "customer_name" not found)

**Solution:**
1. Use `/explore` endpoint to see actual data structure from Nango
2. Update field mappings in `app/services/integrations/quickbooks.py`
3. Nango normalizes field names - check their docs for QB schema

---

## Next Steps

Once QuickBooks connection works:

### 1. Build CEO Dashboard Homepage

Create a new page that shows:
- Revenue widget (from QB summary)
- Expenses widget
- Net income widget
- Top customers list
- Recent invoices table

### 2. Add RAG Context

Enhance widgets with CORTEX knowledge base:
- "Why did revenue spike?" → Search emails for deals
- Click on "Acme Corp" → Show all communications + invoices
- "Outstanding invoices" → Find follow-up emails

### 3. Automate Nightly Refresh

Set up cron job:
- Fetch QB data at midnight
- Cache results in Supabase
- Generate AI insights overnight
- CEO sees fresh dashboard at 7am

---

## Files Reference

### Backend
- `app/services/integrations/quickbooks.py` - QuickBooks data fetching
- `app/api/v1/routes/integrations.py` - API endpoints
- `app/api/v1/routes/oauth.py` - OAuth flow (already has QB)
- `main.py` - Integrations router registered

### Frontend
- `app/connections/page.tsx` - Connection UI (lines 381-415 = QuickBooks)
- `lib/api.ts` - API client functions

### Config
- Backend: `NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks`
- Nango: Provider config key must be `quickbooks`

---

## Test Checklist

- [ ] Nango QuickBooks integration configured
- [ ] Intuit OAuth credentials added to Nango
- [ ] Backend env var set: `NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks`
- [ ] Backend restarted
- [ ] Frontend running at http://localhost:3000
- [ ] Can see QuickBooks card on Connections page
- [ ] Click "Connect QuickBooks" opens OAuth popup
- [ ] OAuth flow completes successfully
- [ ] QuickBooks card shows "Connected" badge
- [ ] Connection Status panel shows "QuickBooks: ✓ Active"
- [ ] `/integrations/quickbooks/explore` returns data
- [ ] `/integrations/quickbooks/summary` returns clean metrics

---

**Ready to test!** Follow the steps above and let me know if you hit any issues.
