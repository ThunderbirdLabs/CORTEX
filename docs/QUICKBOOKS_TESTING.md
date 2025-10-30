# QuickBooks Integration - Testing Guide

## What We Built

### Backend Endpoints

1. **`GET /integrations/quickbooks/explore`**
   - Fetches ALL QuickBooks data (accounts, invoices, bills, payments, etc.)
   - Returns raw data dump for exploration

2. **`GET /integrations/quickbooks/summary`**
   - Returns clean, dashboard-ready financial summary
   - Calculates revenue, expenses, net income
   - Shows top customers, recent invoices, etc.

### Data Sources (via Nango)

The integration fetches from these Nango QuickBooks endpoints:
- `/accounts` - Chart of accounts
- `/invoices` - Sales invoices
- `/customers` - Customer list
- `/bills` - Vendor bills
- `/bill-payments` - Bill payments
- `/payments` - Customer payments
- `/items` - Products/services
- `/purchases` - Purchase transactions
- `/deposits` - Bank deposits
- `/transfers` - Account transfers
- `/credit-memos` - Credit memos
- `/journal-entries` - Journal entries

---

## Testing Steps

### Step 1: Verify QuickBooks is Configured in Nango

1. Go to [Nango Dashboard](https://app.nango.dev/prod)
2. Check that **QuickBooks** integration exists
3. Verify it has a provider config key: `quickbooks`
4. Make sure Intuit OAuth credentials are set

### Step 2: Set Environment Variable

Add to your `.env`:
```bash
NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks
```

Restart the backend:
```bash
uvicorn main:app --reload
```

### Step 3: Test OAuth Connection

#### 3.1 Get Auth URL

```bash
curl -X GET "http://localhost:8080/connect/start?provider=quickbooks" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Expected Response:**
```json
{
  "auth_url": "https://api.nango.dev/oauth/connect/quickbooks?connect_session_token=...",
  "provider": "quickbooks",
  "tenant_id": "user-12345"
}
```

#### 3.2 Complete OAuth

1. Open `auth_url` in browser
2. Log in to QuickBooks
3. Select company
4. Authorize
5. Get redirected back to frontend

#### 3.3 Verify Connection

```bash
curl -X GET "http://localhost:8080/status" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Expected Response:**
```json
{
  "tenant_id": "user-12345",
  "providers": {
    "quickbooks": {
      "configured": true,
      "connected": true,
      "connection_id": "user-12345",
      "last_sync": "2025-10-30T..."
    }
  }
}
```

### Step 4: Fetch QuickBooks Data

#### 4.1 Explore All Data

```bash
curl -X GET "http://localhost:8080/integrations/quickbooks/explore" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Expected Response:**
```json
{
  "success": true,
  "user_id": "user-12345",
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

#### 4.2 Get Clean Summary

```bash
curl -X GET "http://localhost:8080/integrations/quickbooks/summary?time_range=this_month" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
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

## Troubleshooting

### Error: "QuickBooks provider not configured"
- Verify `NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks` in `.env`
- Restart backend after adding

### Error: 401/403 from Nango
- Check QuickBooks integration exists in Nango dashboard
- Verify Intuit OAuth credentials are correct
- Make sure user completed OAuth flow

### Empty Data Arrays
- QuickBooks Sandbox has limited data
- Try connecting a real Production company
- Check Nango sync status in dashboard

### Field Names Don't Match
- Nango normalizes QB field names
- Check actual response structure with `/explore` endpoint
- Update field mappings in `integrations.py` if needed

---

## Next Steps

Once QuickBooks data is flowing:

1. **Build CEO Dashboard Homepage**
   - Apple-style widget cards
   - Revenue, expenses, net income
   - Top customers, recent invoices
   - Outstanding payments

2. **Add RAG Context**
   - Combine QB metrics with CORTEX email/doc search
   - "Why did revenue spike?" → Find related deals in emails
   - "Who is Acme Corp?" → Show communications + invoices

3. **Automate Nightly Refresh**
   - Cron job to fetch QB data at midnight
   - Cache results for fast morning load
   - Generate AI insights overnight

4. **Build Frontend Dashboard**
   - Next.js page with widget grid
   - Refresh button to fetch latest data
   - Click widget → see more details

---

## API Documentation

### GET /integrations/quickbooks/explore

**Description:** Fetch ALL QuickBooks data (raw dump)

**Auth:** Required (JWT)

**Response:**
```json
{
  "success": true,
  "user_id": "string",
  "data": {
    "accounts": Array<Account>,
    "invoices": Array<Invoice>,
    "customers": Array<Customer>,
    "bills": Array<Bill>,
    "payments": Array<Payment>,
    ...
  }
}
```

### GET /integrations/quickbooks/summary

**Description:** Get clean financial summary for dashboard

**Auth:** Required (JWT)

**Query Parameters:**
- `time_range` (optional): `this_week`, `this_month`, `this_quarter`, `this_year` (default: `this_month`)

**Response:**
```json
{
  "success": true,
  "time_range": "string",
  "revenue": number,
  "expenses": number,
  "net_income": number,
  "outstanding_invoices": number,
  "cash_on_hand": number,
  "top_customers": Array<{name: string, total: number}>,
  "top_vendors": Array<{name: string, total: number}>,
  "recent_invoices": Array<Invoice>,
  "data_counts": {
    "total_invoices": number,
    "total_bills": number,
    "total_customers": number,
    "total_payments": number
  }
}
```

---

## Files Modified

### Backend
- `app/services/integrations/quickbooks.py` - QuickBooks data fetching
- `app/services/integrations/__init__.py` - Export functions
- `app/api/v1/routes/integrations.py` - API endpoints
- `main.py` - Register integrations router

### Config
- `app/core/config.py` - Already had `nango_provider_key_quickbooks`
- `.env` - Add `NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks`

---

**Ready to test!** Start with OAuth flow, then explore data, then build the dashboard UI.
