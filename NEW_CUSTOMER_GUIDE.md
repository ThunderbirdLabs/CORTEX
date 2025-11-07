# 🚀 CORTEX New Customer Onboarding Guide

Complete step-by-step guide for deploying CORTEX for a new customer in multi-tenant mode.

---

## 📋 Overview

**What You'll Create:**
- Company record in master Supabase
- Customer's dedicated infrastructure (Supabase, Neo4j, Qdrant, Redis)
- Backend deployment on Render
- Frontend deployment on Vercel
- Seeded AI prompt templates

**Time Required:** ~30-45 minutes

---

## ✅ Prerequisites

- [ ] Access to master admin dashboard
- [ ] Render account (for backend)
- [ ] Vercel account (for frontend)
- [ ] Supabase account (for customer database)
- [ ] Neo4j Aura account (for knowledge graph)
- [ ] Qdrant Cloud account (for vector store)
- [ ] Upstash or Render Redis (for job queue)
- [ ] OpenAI API key
- [ ] Nango OAuth keys (shared across customers or per-customer)

---

## 🎯 STEP 1: Create Company via Master Admin Dashboard

### 1.1 Access Master Admin
1. Go to master admin dashboard (e.g., `https://master-admin.vercel.app`)
2. Login with your master admin credentials

### 1.2 Launch Company Wizard
1. Navigate to **"Companies"** page
2. Click **"+ Add Company"** button
3. Complete the 4-step wizard:

#### **Step 1: Company Info**
```yaml
Required:
- Company Name: "Acme Corporation"
- Slug: "acme-corp" (auto-generated)

Optional:
- Location: "San Francisco, CA"
- Description: "B2B SaaS platform for manufacturing automation"
- Primary Contact Name: "Jane Smith"
- Primary Contact Email: "jane@acmecorp.com"
- Industries Served: "Manufacturing, Automotive, Supply Chain"
- Key Capabilities: "Real-time tracking, Predictive analytics, Quality control"
- Plan: "enterprise" (or "trial")
```

Click **"Continue"** → Company record created with `status: "provisioning"`

#### **Step 2: Deployment Credentials** (Optional - can skip and add later)
- Skip for now, we'll add these after provisioning infrastructure

#### **Step 3: Team Members** (Optional - can skip and add later)
- Skip for now, can add team members later

#### **Step 4: Complete**
- **SAVE THE COMPANY ID** displayed on success screen
- Example: `abc-123-uuid-456-def`

**✅ Checkpoint:** Company record created in master Supabase

---

## 🏗️ STEP 2: Provision Customer Infrastructure

### 2.1 Create Customer's Supabase Project

1. **Go to:** https://supabase.com/dashboard
2. Click **"New Project"**
3. **Settings:**
   ```yaml
   Name: acme-corp-cortex
   Database Password: [GENERATE STRONG PASSWORD - SAVE IT!]
   Region: us-west-1 (or closest to customer)
   Plan: Free (or Pro for production)
   ```
4. Click **"Create new project"**
5. ⏱️ Wait ~2 minutes for provisioning

6. **Run Migrations:**
   - Go to **SQL Editor** in Supabase dashboard
   - Click **"New Query"**
   - Copy ALL migration files from `/migrations/*.sql` in order
   - Run each migration (or combine into one large query)
   - Creates tables: `documents`, `insights`, `reports`, `chat_history`, `document_alerts`, etc.

7. **Copy Credentials:**
   - Go to **Settings → API**
   - Save these values:
     ```yaml
     Project URL: https://xxxxx.supabase.co
     Anon key: eyJhbGc...
     Service Role key: eyJhbGc... (click "Reveal")
     ```

**✅ Checkpoint:** Customer Supabase ready with all tables

---

### 2.2 Create Neo4j Aura Instance (Knowledge Graph)

1. **Go to:** https://console.neo4j.io
2. Click **"New Instance"**
3. **Settings:**
   ```yaml
   Name: acme-corp-graph
   Region: us-west-1 (same as Supabase)
   Size: AuraDB Free (or Professional for production)
   ```
4. Click **"Create"**
5. ⏱️ Wait ~5 minutes for provisioning

6. **Copy Credentials** (shown only once!):
   ```yaml
   URI: neo4j+s://abc123.databases.neo4j.io
   Username: neo4j
   Password: [SAVE THIS PASSWORD!]
   Database: neo4j
   ```

**✅ Checkpoint:** Neo4j Aura instance ready

---

### 2.3 Create Qdrant Cluster (Vector Store)

1. **Go to:** https://cloud.qdrant.io
2. Click **"Create Cluster"**
3. **Settings:**
   ```yaml
   Name: acme-corp-vectors
   Region: us-west (same as others)
   Size: Free 1GB (or larger for production)
   ```
4. Click **"Create"**
5. ⏱️ Wait ~2 minutes

6. **Create Collection:**
   - Click on your new cluster
   - Go to **"Collections"** tab
   - Click **"Create Collection"**
   - Settings:
     ```yaml
     Name: acme_vectors
     Vector size: 1536 (for OpenAI text-embedding-3-small)
     Distance: Cosine
     ```

7. **Copy Credentials:**
   ```yaml
   Cluster URL: https://abc-xyz-123.qdrant.io
   API Key: [from "API Keys" tab]
   Collection Name: acme_vectors
   ```

**✅ Checkpoint:** Qdrant cluster ready with collection

---

### 2.4 Create Redis Instance (Job Queue)

**Option A: Upstash (Recommended - Free tier)**

1. **Go to:** https://upstash.com
2. Click **"Create Database"**
3. Settings:
   ```yaml
   Name: acme-corp-redis
   Type: Regional
   Region: us-west-1 (same as others)
   ```
4. Copy **Redis URL**: `redis://default:password@redis.upstash.io:6379`

**Option B: Render**

1. Create new Redis service on Render
2. Copy connection URL

**✅ Checkpoint:** Redis ready

---

### 2.5 Prepare API Keys

**OpenAI:**
- Use existing API key OR create new one at https://platform.openai.com/api-keys
- Format: `sk-proj-...`

**Nango OAuth:**
- Use existing Nango keys (shared across customers)
- OR create new Nango project at https://nango.dev
- Copy:
  - Secret Key
  - Public Key
  - Provider keys (gmail, outlook, google-drive)

**✅ Checkpoint:** All infrastructure provisioned, credentials saved

---

## 🔐 STEP 3: Save Deployment Credentials to Master Supabase

### 3.1 Option A: Via Master Admin UI (Recommended)

1. Go to master admin dashboard
2. Navigate to **Companies** → Select your new company
3. Click **"Edit Deployment"** or **"Add Deployment Config"**
4. Fill in the form with all credentials from Step 2
5. Click **"Save"**

### 3.2 Option B: Via Direct SQL Insert

Run this in master Supabase SQL Editor:

```sql
INSERT INTO company_deployments (
  company_id,
  supabase_url,
  supabase_anon_key,
  supabase_service_key,
  neo4j_uri,
  neo4j_user,
  neo4j_password,
  neo4j_database,
  qdrant_url,
  qdrant_api_key,
  qdrant_collection_name,
  redis_url,
  openai_api_key,
  nango_secret_key,
  nango_public_key,
  nango_provider_key_gmail,
  nango_provider_key_outlook,
  nango_provider_key_google_drive,
  admin_pin_hash
) VALUES (
  'abc-123-uuid-456-def',  -- Your company_id from Step 1
  'https://xxxxx.supabase.co',
  'eyJhbGc...',  -- Supabase anon key
  'eyJhbGc...',  -- Supabase service key
  'neo4j+s://abc123.databases.neo4j.io',
  'neo4j',
  'your-neo4j-password',
  'neo4j',
  'https://abc-xyz-123.qdrant.io',
  'qdrant-api-key',
  'acme_vectors',
  'redis://default:pass@redis.upstash.io:6379',
  'sk-proj-...',  -- OpenAI API key
  'nango-secret-key',
  'nango-public-key',
  'google-mail',  -- Gmail provider key
  'microsoft-graph',  -- Outlook provider key
  'google-drive',  -- Google Drive provider key
  crypt('2525', gen_salt('bf'))  -- Admin PIN (bcrypt hashed)
);
```

**✅ Checkpoint:** Deployment credentials saved in master Supabase

---

## 🚀 STEP 4: Deploy Customer Backend (Render)

### 4.1 Create New Web Service

1. **Go to:** https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. **Connect Repository:**
   - Repository: `ThunderbirdLabs/CORTEX` (or your fork)
   - Branch: `main`

### 4.2 Configure Service

**Basic Settings:**
```yaml
Name: acme-corp-backend
Region: Oregon (US West)
Branch: main
Root Directory: . (leave empty)
Runtime: Python 3
Build Command: pip install -r requirements.txt
Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
Instance Type: Starter (512 MB RAM) or higher
```

### 4.3 Add Environment Variables

**⚠️ IMPORTANT: Only 3 env vars needed! Everything else loaded from master Supabase.**

```bash
# MULTI-TENANT MODE ENABLERS (Required)
COMPANY_ID=abc-123-uuid-456-def
MASTER_SUPABASE_URL=https://your-master.supabase.co
MASTER_SUPABASE_SERVICE_KEY=eyJhbGc...

# Optional: Environment identifier
ENVIRONMENT=production
```

**That's it!** The backend will load all other credentials (Supabase, Neo4j, Qdrant, Redis, OpenAI, Nango) from the `company_deployments` table in master Supabase.

### 4.4 Deploy

1. Click **"Create Web Service"**
2. ⏱️ Wait ~5 minutes for first deployment

### 4.5 Verify Logs

Check logs for these success indicators:
```
🏢 Initializing MULTI-TENANT mode...
✅ Master Supabase connected (Company ID: abc-123...)
✅ Company Supabase connected
✅ Company context loaded: Acme Corporation
✅ Loaded 6 prompt templates: ['ceo_assistant', 'email_classifier', ...]
✅ CORS: Loaded frontend URL from master Supabase: https://acme-frontend.vercel.app
🌐 CORS allowed origins: ['https://acme-frontend.vercel.app']
✅ Application started successfully
```

If you see `🏠 Initializing SINGLE-TENANT mode`, you're missing the `COMPANY_ID` env var!

### 4.6 Copy Backend URL

Example: `https://acme-corp-backend.onrender.com`

**✅ Checkpoint:** Backend deployed and running in multi-tenant mode

---

## 🎨 STEP 5: Deploy Customer Frontend (Vercel)

### 5.1 Create New Project

1. **Go to:** https://vercel.com/dashboard
2. Click **"Add New..."** → **"Project"**
3. **Import Repository:**
   - Repository: `nicolascodet/connectorfrontend` (or your fork)
   - Framework Preset: Next.js
   - Root Directory: `./` (or leave blank)

### 5.2 Configure Project

**Project Settings:**
```yaml
Project Name: acme-corp-frontend
Framework: Next.js
Root Directory: (leave blank)
Build Command: (auto-detected)
Output Directory: (auto-detected)
Install Command: npm install
```

### 5.3 Add Environment Variables

**Required Variables:**

```bash
# Customer's Supabase (for client-side queries)
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGc...

# Backend API URL
NEXT_PUBLIC_API_URL=https://acme-corp-backend.onrender.com

# Optional: Analytics
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=G-XXXXXXXXXX
```

### 5.4 Deploy

1. Click **"Deploy"**
2. ⏱️ Wait ~3 minutes for deployment

### 5.5 Copy Frontend URL

Example: `https://acme-corp-frontend.vercel.app`

**✅ Checkpoint:** Frontend deployed and accessible

---

## 🔗 STEP 6: Update Company Record with URLs

### 6.1 Via Master Admin UI

1. Go to master admin dashboard
2. Navigate to **Companies** → Select your company
3. Click **"Edit"**
4. Update:
   ```yaml
   Backend URL: https://acme-corp-backend.onrender.com
   Frontend URL: https://acme-corp-frontend.vercel.app
   Status: active (change from "provisioning")
   ```
5. Click **"Save"**

### 6.2 Via Direct SQL Update

Run in master Supabase:

```sql
UPDATE companies
SET
  backend_url = 'https://acme-corp-backend.onrender.com',
  frontend_url = 'https://acme-corp-frontend.vercel.app',
  status = 'active',
  activated_at = NOW()
WHERE id = 'abc-123-uuid-456-def';
```

**✅ Checkpoint:** Company record updated with deployment URLs

---

## 🤖 STEP 7: Seed Default AI Prompts

### 7.1 Run Seed Script

On your local machine:

```bash
cd /path/to/CORTEX

# Set environment variables
export COMPANY_ID=abc-123-uuid-456-def
export MASTER_SUPABASE_URL=https://your-master.supabase.co
export MASTER_SUPABASE_SERVICE_KEY=eyJhbGc...

# Run seed script
python3 scripts/seed_default_prompts.py
```

### 7.2 Verify Output

You should see:
```
============================================================
  Seeding Default Prompt Templates
============================================================

📋 Seeding prompts for: Acme Corporation

✅ Added ceo_assistant: CEO Assistant Response Synthesis
✅ Added email_classifier: Email Business Classification
✅ Added vision_ocr_business_check: Image Business Relevance Check
✅ Added vision_ocr_extract: Image Text Extraction
✅ Added entity_extraction: Entity and Relationship Extraction
✅ Added entity_deduplication: Entity Deduplication and Resolution

============================================================
  ✅ Prompt Templates Seeded!
============================================================
```

**This creates 6 default prompts:**
- `ceo_assistant` - Main response synthesis
- `email_classifier` - BUSINESS vs SPAM filter
- `vision_ocr_business_check` - Image relevance check
- `vision_ocr_extract` - OCR extraction
- `entity_extraction` - Neo4j entity/relationship extraction
- `entity_deduplication` - Fuzzy entity matching

**✅ Checkpoint:** AI prompts seeded in `company_prompts` table

---

## 🧪 STEP 8: Test Customer Deployment

### 8.1 Access Frontend

1. Open `https://acme-corp-frontend.vercel.app`
2. **Create account** or **login**

### 8.2 Test OAuth Sync

**Gmail:**
1. Click **"Connect Gmail"**
2. Complete OAuth flow → Should redirect to Nango → Authorize
3. Check sync status → Should show "Connected"
4. Wait 1-2 minutes
5. Check documents → Should see emails ingested

**Outlook:**
1. Click **"Connect Outlook"**
2. Complete OAuth flow
3. Verify sync

**Google Drive:**
1. Click **"Connect Google Drive"**
2. Complete OAuth flow
3. Verify file sync

### 8.3 Test Chat/Search

1. Go to chat/search page
2. Ask a question: "What are the latest emails?"
3. Verify response uses `ceo_assistant` prompt
4. Check sources are linked correctly

### 8.4 Test Admin Panel

1. Navigate to `/admin`
2. Enter PIN: `2525` (or your custom PIN)
3. Check:
   - ✅ Document counts
   - ✅ Sync status
   - ✅ Recent activity
   - ✅ Integration status

### 8.5 Test Insights & Alerts

1. Go to dashboard
2. Click **"Generate Insights"**
3. Wait ~2 minutes
4. Verify insights appear
5. Check alerts sidebar for urgent items

**✅ Checkpoint:** Customer deployment fully functional

---

## 📋 Post-Deployment Checklist

- [ ] Company created in master Supabase
- [ ] Infrastructure provisioned (Supabase, Neo4j, Qdrant, Redis)
- [ ] Deployment credentials saved
- [ ] Backend deployed on Render (3 env vars)
- [ ] Frontend deployed on Vercel (3 env vars)
- [ ] Company URLs updated, status = "active"
- [ ] Default prompts seeded
- [ ] OAuth sync tested (Gmail, Outlook, Drive)
- [ ] Chat/search tested
- [ ] Admin panel accessible
- [ ] Insights/alerts working

---

## 🔧 Environment Variables Reference

### Backend (Render) - 3 Variables

```bash
COMPANY_ID=abc-123-uuid-456-def
MASTER_SUPABASE_URL=https://your-master.supabase.co
MASTER_SUPABASE_SERVICE_KEY=eyJhbGc...
```

**All other credentials loaded from master Supabase:**
- Customer Supabase (URL, keys)
- Neo4j (URI, user, password)
- Qdrant (URL, API key, collection)
- Redis (URL)
- OpenAI (API key)
- Nango (secret, public, provider keys)
- Admin PIN

### Frontend (Vercel) - 3 Variables

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGc...
NEXT_PUBLIC_API_URL=https://acme-corp-backend.onrender.com
```

---

## 🚨 Troubleshooting

### Backend shows "Single-tenant mode"
**Problem:** Missing `COMPANY_ID` env var
**Fix:** Add `COMPANY_ID` to Render env vars, redeploy

### Backend can't connect to master Supabase
**Problem:** Wrong `MASTER_SUPABASE_URL` or `MASTER_SUPABASE_SERVICE_KEY`
**Fix:** Verify keys in master Supabase → Settings → API

### Frontend CORS errors
**Problem:** Backend not loading `frontend_url` from company record
**Fix:** Verify `frontend_url` is set in master Supabase `companies` table

### Prompts not loading
**Problem:** `company_prompts` table empty
**Fix:** Run `scripts/seed_default_prompts.py` with correct `COMPANY_ID`

### OAuth not working
**Problem:** Wrong Nango keys or provider keys
**Fix:** Verify credentials in `company_deployments` table

### Neo4j connection fails
**Problem:** Wrong URI or password
**Fix:** Test connection manually, update `company_deployments` table

### Qdrant collection not found
**Problem:** Collection name mismatch
**Fix:** Verify collection exists in Qdrant dashboard, update `qdrant_collection_name`

---

## 📚 Additional Resources

- **Master Admin Dashboard:** Manage companies, schemas, prompts
- **Main README:** Full architecture documentation
- **Setup Guide:** `docs/SETUP.md` - Master Supabase setup
- **API Docs:** Backend API documentation (Swagger at `/docs`)
- **Prompt Templates:** Customize in `company_prompts` table

---

## 🎉 Success!

Your customer is now live on CORTEX! They can:
- ✅ Sync emails from Gmail/Outlook
- ✅ Upload documents
- ✅ Connect Google Drive
- ✅ Search via hybrid RAG (vector + graph)
- ✅ Chat with AI assistant
- ✅ Generate insights
- ✅ Receive alerts
- ✅ Save investigation reports

**Total deployment time:** ~30-45 minutes per customer

**Scalability:** Each customer runs in complete isolation with their own infrastructure.

---

**Need help?** Contact the CORTEX team or check the troubleshooting section above.
