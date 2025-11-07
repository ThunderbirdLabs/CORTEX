# 3-Environment-Variable Deployment 🚀

**The simplest way to deploy CORTEX backends for multi-tenant customers.**

Instead of managing 20+ environment variables per deployment, you only need **3**:

```bash
COMPANY_ID=2ede0765-6f69-4293-931d-22cc88437e01
MASTER_SUPABASE_URL=https://frkquqpbnczafibjsvmd.supabase.co
MASTER_SUPABASE_SERVICE_KEY=eyJhbGci...
```

Everything else (Neo4j, Qdrant, Redis, OpenAI, Nango, customer Supabase) is **automatically loaded** from the master Supabase `company_deployments` table.

---

## How It Works

### 1. Store Credentials in Master Supabase

When you add a company via the Master Admin UI ([AddCompanyWizard](../MASTERFRONTEND/components/AddCompanyWizard.tsx)), all infrastructure credentials are stored in the `company_deployments` table:

- **Supabase** (customer's operational database)
- **Neo4j** (knowledge graph)
- **Qdrant** (vector store)
- **Redis** (job queue)
- **OpenAI** (LLM & embeddings)
- **Nango** (OAuth provider keys)

### 2. Backend Loads Dynamically at Startup

When the backend starts with `COMPANY_ID` set, it:

1. Connects to master Supabase using `MASTER_SUPABASE_URL` + `MASTER_SUPABASE_SERVICE_KEY`
2. Queries `company_deployments` table for the company's credentials
3. Loads all infrastructure config into memory
4. Uses those credentials for Neo4j, Qdrant, Redis, etc.

See [app/core/config.py:134-228](../app/core/config.py#L134-L228) for implementation.

---

## Deployment Guide

### Step 1: Add Company to Master Supabase

1. Go to Master Admin UI: `https://your-master-frontend.vercel.app`
2. Navigate to **Companies** → **+ Add Company**
3. Fill in the 4-step wizard:
   - **Step 1**: Company basic info
   - **Step 2**: Deployment credentials (Neo4j, Qdrant, Redis, OpenAI, Nango, Supabase)
   - **Step 3**: Team members
   - **Step 4**: Success! Copy the `COMPANY_ID`

### Step 2: Deploy Backend to Render

1. Create **New Web Service** on Render
2. Connect to repository: `ThunderbirdLabs/HIGHFORCE`
3. Branch: `main`
4. Build Command: `./render-build.sh`
5. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add **ONLY 3 environment variables**:

```bash
COMPANY_ID=<from-step-1>
MASTER_SUPABASE_URL=https://frkquqpbnczafibjsvmd.supabase.co
MASTER_SUPABASE_SERVICE_KEY=<your-master-service-key>
```

7. Deploy! 🚀

The backend will automatically load all other credentials from master Supabase.

### Step 3: Deploy Dedupe Cron Job (Optional)

1. Create **New Cron Job** on Render
2. Connect to repository: `ThunderbirdLabs/HIGHFORCE`
3. Branch: `main`
4. Build Command: `pip install -r requirements-dedup.txt`
5. Start Command: `python -m app.services.deduplication.run_dedup_cli`
6. Schedule: `*/15 * * * *` (every 15 minutes)
7. Add **SAME 3 environment variables** as backend

---

## Priority & Fallback

**Loading Priority:**
1. **Environment variable** (if set, use it)
2. **Master Supabase** (if env var not set, load from master)
3. **Error** (if neither available, log warning)

This means you can **override** any credential by setting it as an environment variable, while still getting the convenience of loading from master Supabase for everything else.

### Example: Override OpenAI Key

```bash
# These 3 load everything from master Supabase
COMPANY_ID=2ede0765-6f69-4293-931d-22cc88437e01
MASTER_SUPABASE_URL=https://frkquqpbnczafibjsvmd.supabase.co
MASTER_SUPABASE_SERVICE_KEY=eyJhbGci...

# Override just the OpenAI key for testing
OPENAI_API_KEY=sk-proj-my-test-key-xyz
```

The backend will use `sk-proj-my-test-key-xyz` instead of the one stored in master Supabase, but still load all other credentials from master.

---

## Logs & Debugging

When the backend starts, you'll see logs like:

```
🏢 Multi-tenant mode detected (Company ID: 2ede0765-6f69-4293-931d-22cc88437e01)
🔍 Attempting to load credentials from master Supabase...
✅ Successfully loaded credentials from master Supabase
  ✓ supabase_url: Loaded from master Supabase
  ✓ supabase_anon_key: Loaded from master Supabase
  ✓ neo4j_uri: Loaded from master Supabase
  ✓ neo4j_password: Loaded from master Supabase
  ✓ qdrant_url: Loaded from master Supabase
  ✓ qdrant_api_key: Loaded from master Supabase
  ✓ redis_url: Loaded from master Supabase
  ✓ openai_api_key: Loaded from master Supabase
  ✓ nango_secret: Loaded from master Supabase
🎉 Multi-tenant configuration complete!
```

If a credential is missing from both env vars and master Supabase:

```
⚠️  qdrant_api_key: Not found in env or master Supabase
```

---

## Benefits

### For You (Platform Admin)
✅ **One-line deployment** for new customers (just change `COMPANY_ID`)
✅ **Centralized credential management** in master Supabase
✅ **Rotate credentials** without redeploying (update master Supabase + restart)
✅ **Version control security** (no secrets in git)

### For Customers
✅ **Faster onboarding** (30 min → 5 min)
✅ **Secure** (credentials never in customer's hands)
✅ **Scalable** (supports unlimited customers)

---

## Comparison: Before vs. After

### Before (20+ env vars per deployment) ❌

```bash
COMPANY_ID=2ede0765-6f69-4293-931d-22cc88437e01
DATABASE_URL=postgresql://postgres.xyz:password@aws-1-us-east-1.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://slhntddytmzpqqrfndgg.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
NEO4J_URI=neo4j+s://c7eab67c.databases.neo4j.io
NEO4J_PASSWORD=BM-V7UQswzqjd6xz6EWBr6zNXXdLavU3OOF31yiwEYs
NEO4J_USER=neo4j
QDRANT_URL=https://548c56e8-4540-4adc-9c27-311c37dfd84c.us-west-1-0.aws.cloud.qdrant.io
QDRANT_API_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
QDRANT_COLLECTION_NAME=cortex_documents
REDIS_URL=redis://red-d3rtosvgi27c739mu7l0:6379
OPENAI_API_KEY=sk-proj-pwtcBQVJRaghxOkEE9YkKYZJ3vMGWFm5HCMoxMxsAEvxi6x3...
NANGO_SECRET=b32df6ee-cf76-44a3-bde5-241e86cd2c8e
NANGO_PROVIDER_KEY_GMAIL=google-mail
NANGO_PROVIDER_KEY_OUTLOOK=outlook
NANGO_PROVIDER_KEY_GOOGLE_DRIVE=google-drive
NANGO_PROVIDER_KEY_QUICKBOOKS=quickbooks
SEMAPHORE_LIMIT=10
SENTRY_DSN=https://70bf2b04541c8fd279cb8b072b4dc228@o4510229244477440.ingest.us.sentry.io/4510229258043392
MASTER_SUPABASE_URL=https://frkquqpbnczafibjsvmd.supabase.co
MASTER_SUPABASE_SERVICE_KEY=eyJhbGci...
```

### After (3 env vars) ✅

```bash
COMPANY_ID=2ede0765-6f69-4293-931d-22cc88437e01
MASTER_SUPABASE_URL=https://frkquqpbnczafibjsvmd.supabase.co
MASTER_SUPABASE_SERVICE_KEY=eyJhbGci...
```

**That's a 90% reduction in configuration complexity!** 🎉

---

## Testing Locally

Test the dynamic loading with the included test script:

```bash
cd /path/to/CORTEX
python3 test_multi_tenant_config.py
```

Expected output:

```
================================================================================
MULTI-TENANT CONFIGURATION TEST
================================================================================

📋 Company ID: 2ede0765-6f69-4293-931d-22cc88437e01
🏢 Multi-tenant mode: True

🔑 Loaded Credentials:
  Supabase URL: https://slhntddytmzpqqrfndgg.supabase.co
  Supabase Anon Key: ✓ Set
  Neo4j URI: neo4j+s://c7eab67c.databases.neo4j.io
  Neo4j Password: ✓ Set
  Qdrant URL: https://548c56e8-4540-4adc-9c27-311c37dfd84c.us-west-1-0.aws.cloud.qdrant.io
  Qdrant API Key: ✓ Set
  Redis URL: redis://red-d3rtosvgi27c739mu7l0:6379
  OpenAI API Key: ✓ Set
  Nango Secret: ✓ Set

================================================================================

✅ SUCCESS: All required credentials loaded from master Supabase!
```

---

## Security Considerations

### ✅ Good
- Credentials stored in Supabase (encrypted at rest)
- Service role key required to read credentials
- No secrets in version control
- Audit trail in master Supabase

### ⚠️ TODO (Future Enhancements)
- **Encrypt credentials in `company_deployments` table** (currently plaintext)
- **Use Supabase Vault** for secret storage
- **Rotate credentials automatically** (integrate with cloud providers)
- **Add credential expiry dates** and auto-rotation

---

## Troubleshooting

### Backend fails to start: "No deployment found for company_id"

**Cause**: The `COMPANY_ID` doesn't exist in the `company_deployments` table.

**Fix**:
1. Check `COMPANY_ID` is correct
2. Query master Supabase: `SELECT * FROM company_deployments WHERE company_id = 'your-id'`
3. If missing, add company via Master Admin UI

### Backend starts but missing credentials

**Cause**: Credentials not stored in master Supabase or env vars not set.

**Fix**:
1. Check master Supabase: `SELECT * FROM company_deployments WHERE company_id = 'your-id'`
2. Verify all required fields are populated (not NULL)
3. Set missing credentials as env vars temporarily
4. Update master Supabase with missing credentials

### Connection errors (Neo4j, Qdrant, Redis)

**Cause**: Credentials loaded but incorrect/expired.

**Fix**:
1. Verify credentials are correct in master Supabase
2. Test connections manually using the loaded credentials
3. Update master Supabase with correct credentials
4. Restart backend

---

## Next Steps

- Read [NEW_CUSTOMER_GUIDE.md](../NEW_CUSTOMER_GUIDE.md) for complete onboarding flow
- See [COMPLETE_MULTI_TENANT_SYSTEM.md](../docs/COMPLETE_MULTI_TENANT_SYSTEM.md) for architecture details
- Check [AddCompanyWizard.tsx](../MASTERFRONTEND/components/AddCompanyWizard.tsx) for UI flow
