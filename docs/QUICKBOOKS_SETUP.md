# QuickBooks Integration Setup

## Step 1: Nango Dashboard Configuration

### 1.1 Add QuickBooks Integration in Nango

Go to [Nango Dashboard](https://app.nango.dev) → Integrations → Add Integration

**Configuration:**
```
Provider: QuickBooks Online
Provider Config Key: quickbooks
OAuth Scopes:
  - com.intuit.quickbooks.accounting (required - access financial data)
  - com.intuit.quickbooks.payment (optional - payment processing)
```

### 1.2 Get QuickBooks OAuth Credentials

1. Go to [Intuit Developer Portal](https://developer.intuit.com/)
2. Create an app or use existing app
3. Go to Keys & Credentials
4. Copy:
   - **Client ID**
   - **Client Secret**

### 1.3 Configure in Nango

In Nango Dashboard → QuickBooks Integration:
- **Client ID**: Paste from Intuit
- **Client Secret**: Paste from Intuit
- **Redirect URL**: `https://api.nango.dev/oauth/callback` (Nango handles this)
- **Environment**: Sandbox or Production

**Important:** You need to add Nango's redirect URL to your QuickBooks app settings in Intuit Developer Portal!

---

## Step 2: Update CORTEX Environment Variables

Add to your `.env` file:

```bash
# QuickBooks Integration
NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks
```

That's it! The `nango_provider_key_quickbooks` config variable is already set up in CORTEX.

---

## Step 3: Test OAuth Flow

### 3.1 Start CORTEX Backend

```bash
uvicorn main:app --reload
```

### 3.2 Initiate OAuth Connection

**Request:**
```bash
curl -X GET "http://localhost:8080/connect/start?provider=quickbooks" \
  -H "Authorization: Bearer YOUR_USER_JWT"
```

**Response:**
```json
{
  "auth_url": "https://api.nango.dev/oauth/connect/quickbooks?connect_session_token=...",
  "provider": "quickbooks",
  "tenant_id": "user-12345"
}
```

### 3.3 Complete OAuth in Browser

1. Open the `auth_url` in your browser
2. Log in to QuickBooks
3. Select your company
4. Authorize CORTEX
5. You'll be redirected back to your frontend

### 3.4 Check Connection Status

```bash
curl -X GET "http://localhost:8080/status" \
  -H "Authorization: Bearer YOUR_USER_JWT"
```

**Response:**
```json
{
  "tenant_id": "user-12345",
  "providers": {
    "quickbooks": {
      "configured": true,
      "connected": true,
      "connection_id": "user-12345",
      "last_sync": "2025-10-27T12:00:00Z"
    }
  }
}
```

---

## Step 4: Test Data Fetching

### 4.1 Get QuickBooks Company Realm ID

When you complete OAuth, Nango stores the QuickBooks `realmId` (company ID) in connection metadata.

**Fetch it:**
```bash
curl -X GET "https://api.nango.dev/connection/user-12345?provider_config_key=quickbooks" \
  -H "Authorization: Bearer YOUR_NANGO_SECRET_KEY"
```

**Response:**
```json
{
  "connection_id": "user-12345",
  "provider_config_key": "quickbooks",
  "credentials": {...},
  "metadata": {
    "realmId": "9130357567890123"  ← This is the company ID!
  }
}
```

### 4.2 Explore ALL QuickBooks Data

```bash
curl -X GET "http://localhost:8080/integrations/quickbooks/explore?realm_id=9130357567890123" \
  -H "Authorization: Bearer YOUR_USER_JWT"
```

**Response:** (Full data dump - see integrations.py for structure)
```json
{
  "success": true,
  "user_id": "user-12345",
  "realm_id": "9130357567890123",
  "data": {
    "company_info": {
      "CompanyInfo": {
        "CompanyName": "Acme Manufacturing",
        "Country": "US",
        "FiscalYearStartMonth": "January"
      }
    },
    "profit_and_loss": {
      "Header": {...},
      "Rows": {
        "Row": [
          {
            "group": "Income",
            "Summary": {
              "ColData": [{"value": "47500.00"}]
            }
          },
          {
            "group": "Expenses",
            "Summary": {
              "ColData": [{"value": "22000.00"}]
            }
          }
        ]
      }
    },
    "invoices": [
      {
        "Id": "892",
        "DocNumber": "INV-892",
        "CustomerRef": {"name": "Acme Corp"},
        "TotalAmt": 12500.00,
        "Balance": 0.00,
        "TxnDate": "2025-10-26",
        "Line": [...]
      }
    ],
    "customers": [...],
    "vendors": [...],
    "bills": [...],
    "payments": [...],
    "expenses": [...]
  }
}
```

### 4.3 Get Clean Summary (Dashboard-Ready)

```bash
curl -X GET "http://localhost:8080/integrations/quickbooks/summary?realm_id=9130357567890123&time_range=this_month" \
  -H "Authorization: Bearer YOUR_USER_JWT"
```

**Response:** (Cleaned, formatted data)
```json
{
  "success": true,
  "time_range": "this_month",
  "company_name": "Acme Manufacturing",
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
    "total_vendors": 12
  }
}
```

---

## Troubleshooting

### Error: "QuickBooks provider not configured"
- Make sure `NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks` is in your `.env`
- Restart the backend after adding env variables

### Error: "Failed to retrieve access token from Nango"
- Check that QuickBooks integration is configured in Nango dashboard
- Verify Client ID and Client Secret are correct
- Make sure Nango's redirect URL is whitelisted in Intuit Developer Portal

### Error: 401 Unauthorized from QuickBooks API
- OAuth token may have expired (Nango auto-refreshes, but check)
- User may have disconnected the app from QuickBooks settings
- Verify the `realm_id` is correct

### Empty/Missing Data
- QuickBooks Sandbox accounts have limited sample data
- Try connecting to a real Production company
- Check QuickBooks permissions (ensure `com.intuit.quickbooks.accounting` scope is granted)

---

## Next Steps

Once QuickBooks connection works:
1. Build dashboard widgets that combine QB financial data + CORTEX knowledge base
2. Set up nightly refresh jobs (fetch QB data at midnight)
3. Create RAG-powered insights (e.g., "Why did revenue spike?" with context from emails)

See `app/api/v1/routes/integrations.py` for implementation details.
