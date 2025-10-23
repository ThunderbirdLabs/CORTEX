# 🔌 Nango Integration Setup Guide

Complete step-by-step guide for setting up all Cortex data connectors.

---

## 📋 Prerequisites

1. **Nango Account** - Sign up at https://nango.dev
2. **Provider Apps** - Create OAuth apps for each provider:
   - Google Cloud Console (Gmail + Drive)
   - Microsoft Azure (Outlook)
   - Intuit Developer Portal (QuickBooks)

---

## 🚀 Setup Steps

### **1. Outlook (Microsoft 365)**

#### **A. Create Azure App**

1. Go to https://portal.azure.com
2. Navigate to **Azure Active Directory** → **App Registrations**
3. Click **New Registration**
   - Name: `Cortex Outlook Connector`
   - Supported account types: **Multitenant**
   - Redirect URI: `https://api.nango.dev/oauth/callback`
4. Save **Application (client) ID**
5. Go to **Certificates & Secrets** → **New client secret**
   - Save the **Secret Value** (shown once!)
6. Go to **API Permissions** → **Add permission** → **Microsoft Graph** → **Delegated**
   - Add scopes:
     - `User.Read`
     - `Mail.Read`
     - `Mail.ReadBasic`
     - `offline_access`
7. Click **Grant admin consent**

#### **B. Configure in Nango**

```bash
# Login to Nango CLI
npx nango auth

# Create Outlook integration
npx nango integration:create \
  --provider microsoft \
  --integration-id outlook \
  --client-id YOUR_AZURE_CLIENT_ID \
  --client-secret YOUR_AZURE_CLIENT_SECRET \
  --scopes "User.Read Mail.Read Mail.ReadBasic offline_access"
```

#### **C. Set Environment Variable**

In your Render backend, add:
```bash
NANGO_PROVIDER_KEY_OUTLOOK=outlook
```

---

### **2. Gmail (Google Workspace)**

#### **A. Create Google Cloud Project**

1. Go to https://console.cloud.google.com
2. Create new project: `Cortex Gmail Connector`
3. Enable **Gmail API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
   - Application type: **Web application**
   - Name: `Cortex Gmail`
   - Authorized redirect URIs: `https://api.nango.dev/oauth/callback`
5. Save **Client ID** and **Client Secret**

#### **B. Configure in Nango**

```bash
# Create Gmail integration
npx nango integration:create \
  --provider google \
  --integration-id google-mail \
  --client-id YOUR_GOOGLE_CLIENT_ID \
  --client-secret YOUR_GOOGLE_CLIENT_SECRET \
  --scopes "https://www.googleapis.com/auth/gmail.readonly"
```

#### **C. Set Environment Variable**

```bash
NANGO_PROVIDER_KEY_GMAIL=google-mail
```

---

### **3. Google Drive**

#### **A. Enable Drive API**

1. In same Google Cloud project from Gmail setup
2. Navigate to **APIs & Services** → **Library**
3. Search for **Google Drive API** → Click **Enable**
4. Use same OAuth client credentials from Gmail setup

#### **B. Configure in Nango**

Option 1: **Separate Drive integration** (recommended for different scopes):
```bash
npx nango integration:create \
  --provider google \
  --integration-id google-drive \
  --client-id YOUR_GOOGLE_CLIENT_ID \
  --client-secret YOUR_GOOGLE_CLIENT_SECRET \
  --scopes "https://www.googleapis.com/auth/drive.readonly"
```

Option 2: **Use Gmail integration** (if Drive scopes added to same integration):
```bash
# Update existing google-mail integration to add Drive scope
npx nango integration:update \
  --integration-id google-mail \
  --add-scope "https://www.googleapis.com/auth/drive.readonly"
```

#### **C. Deploy Drive Sync** (if using separate integration)

```bash
cd nango-integrations

# Deploy the all-files sync
npx nango deploy

# Verify sync is enabled in Nango dashboard
# Integration: google-drive → Syncs → all-files → Should show "Enabled"
```

#### **D. Set Environment Variable**

If using separate Drive integration:
```bash
NANGO_PROVIDER_KEY_GOOGLE_DRIVE=google-drive
```

If using Gmail integration for both:
```bash
# Leave NANGO_PROVIDER_KEY_GOOGLE_DRIVE unset
# Backend will automatically fall back to NANGO_PROVIDER_KEY_GMAIL
```

---

### **4. QuickBooks**

#### **A. Create Intuit App**

1. Go to https://developer.intuit.com
2. Click **Create an app** → **QuickBooks Online**
3. App name: `Cortex QuickBooks Connector`
4. Go to **Keys & credentials**
5. Add **Redirect URI**: `https://api.nango.dev/oauth/callback`
6. Save **Client ID** and **Client Secret**
7. Note the scopes you need:
   - `com.intuit.quickbooks.accounting` (full accounting access)
   - Or specific scopes like:
     - `com.intuit.quickbooks.accounting.invoice.read`
     - `com.intuit.quickbooks.accounting.customer.read`
     - `com.intuit.quickbooks.accounting.payment.read`

#### **B. Configure in Nango**

```bash
# Create QuickBooks integration
npx nango integration:create \
  --provider quickbooks \
  --integration-id quickbooks \
  --client-id YOUR_INTUIT_CLIENT_ID \
  --client-secret YOUR_INTUIT_CLIENT_SECRET \
  --scopes "com.intuit.quickbooks.accounting"
```

#### **C. Set Environment Variable**

```bash
NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks
```

---

## 🔗 Testing Connections

### **Test OAuth Flow**

1. Go to your frontend: `https://your-frontend.vercel.app`
2. Click **Connections** in sidebar settings
3. Click **Connect [Provider]**
4. Complete OAuth in popup
5. Should see **Connected** badge

### **Test Manual Sync**

```bash
# Outlook
curl -H "Authorization: Bearer <jwt>" \
  https://your-backend.onrender.com/sync/once

# Gmail
curl -H "Authorization: Bearer <jwt>" \
  https://your-backend.onrender.com/sync/once/gmail

# Google Drive
curl -H "Authorization: Bearer <jwt>" \
  https://your-backend.onrender.com/sync/once/drive
```

### **Verify Data in Supabase**

```sql
-- Check emails table
SELECT source, COUNT(*) FROM emails GROUP BY source;

-- Check documents table
SELECT source, document_type, COUNT(*) FROM documents GROUP BY source, document_type;

-- Check connections table
SELECT provider_key, COUNT(*) FROM connections GROUP BY provider_key;
```

---

## 🎯 QuickBooks Data Sync (Future)

Currently QuickBooks is OAuth-ready but sync not implemented. To add sync later:

1. **Create QuickBooks sync endpoint** in `app/api/v1/routes/sync.py`
2. **Create QuickBooks connector** in `app/services/connectors/quickbooks.py`
3. **Normalize QuickBooks data** (invoices, customers, payments → documents format)
4. **Add to universal ingestion** pipeline

Example structure:
```python
# app/services/connectors/quickbooks.py
async def fetch_invoices(access_token: str) -> List[Dict]:
    """Fetch invoices from QuickBooks API"""
    
async def normalize_invoice(invoice: Dict, tenant_id: str) -> Dict:
    """Normalize QB invoice to document format"""
    return {
        "source": "quickbooks",
        "source_id": invoice["Id"],
        "document_type": "invoice",
        "title": f"Invoice #{invoice['DocNumber']}",
        "content": f"Customer: {invoice['CustomerRef']['name']}\nAmount: ${invoice['TotalAmt']}...",
        # ... rest of normalization
    }
```

---

## 📊 Nango Dashboard Reference

### **Check Integration Status**

1. Go to https://app.nango.dev
2. Navigate to **Integrations**
3. Verify each integration shows:
   - ✅ **Status**: Operational
   - ✅ **Scopes**: Correctly configured
   - ✅ **Syncs**: Enabled (for Gmail/Drive)

### **Monitor Connections**

1. **Connections** tab shows all user connections
2. Filter by `integration_id` to see specific providers
3. Check connection health and token expiry

### **View Sync Logs**

1. **Logs** tab shows sync execution history
2. Filter by `integration_id` and `connection_id`
3. Useful for debugging sync failures

---

## 🔐 Security Best Practices

1. **Never commit credentials** - Use environment variables only
2. **Use minimal scopes** - Request only what you need
3. **Rotate secrets regularly** - Especially Nango secret key
4. **Monitor webhook signatures** - Verify Nango webhooks are authentic
5. **Implement RLS** - Supabase Row Level Security policies

---

## 🐛 Troubleshooting

### **"Provider not configured" error**

Check environment variables are set in Render:
```bash
NANGO_PROVIDER_KEY_OUTLOOK=outlook
NANGO_PROVIDER_KEY_GMAIL=google-mail
NANGO_PROVIDER_KEY_GOOGLE_DRIVE=google-drive
NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks
```

### **OAuth popup shows wrong scopes**

1. Check Nango dashboard → Integration → Scopes field
2. Verify OAuth app has all required scopes
3. Clear browser cache and retry

### **Sync returns 0 results**

1. Check Nango dashboard → Syncs → Verify sync is **Enabled**
2. Run manual sync from **Test Connection** button
3. Check logs for API errors

### **"Connection not found" after OAuth**

1. Verify webhook endpoint is accessible: `https://your-backend.onrender.com/nango/webhook`
2. Check Nango dashboard → Environment Settings → Webhook URL
3. Check backend logs for webhook receipt

---

## 📝 Next Steps

Once OAuth is working:

1. **Test each provider** - Connect and verify
2. **Run manual syncs** - Check data flows to Supabase
3. **Search test** - Ask questions about synced data
4. **Monitor costs** - OpenAI entity extraction usage
5. **Add more sources** - 600+ Nango integrations available!

---

**Questions?** Check Nango docs: https://docs.nango.dev

