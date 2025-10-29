# 🏢 CORTEX Enterprise Multi-Tenant Setup Guide

**IMPORTANT:** This setup is **BACKWARD COMPATIBLE**. Your existing Unit Industries deployment will continue working without any changes!

---

## 🎯 What This Does

Before: One CORTEX deployment = One company (Unit Industries)

After: One codebase → Multiple isolated deployments
```
Master Control Plane (YOU)
├── Unit Industries
├── Acme Corp
├── Globex Inc
└── [Future companies...]
```

Each company gets:
- ✅ Own Supabase (documents, emails, users)
- ✅ Own Neo4j (isolated knowledge graph)
- ✅ Own Qdrant (isolated vectors)
- ✅ Own custom schemas (you manage from master dashboard)
- ✅ Complete data isolation

---

## 📋 Setup Steps

### **Step 1: Create Master Supabase Project (5 minutes)**

1. Go to https://supabase.com/dashboard
2. Click "New Project"
3. Settings:
   ```
   Name: cortex-master
   Database Password: [Generate strong - SAVE IT!]
   Region: us-west-1 (same as existing)
   Plan: Free (for now)
   ```
4. Wait ~2 minutes for provisioning
5. Copy these values:
   ```
   Project URL: https://[ref].supabase.co
   Anon/public key: eyJhbGc...
   Service role key: eyJhbGc... (click "Reveal")
   ```
6. **SAVE THESE SECURELY!**

---

### **Step 2: Run Master Database Migrations (2 minutes)**

#### **Option A: Using Supabase SQL Editor** (Easiest)

1. Open your master Supabase project
2. Click "SQL Editor" in sidebar
3. Click "New Query"
4. Copy contents of `migrations/master/001_create_master_tables.sql`
5. Paste and click "Run"
6. Wait for "Success" message
7. Verify tables created:
   ```sql
   SELECT table_name FROM information_schema.tables
   WHERE table_schema = 'public'
   ORDER BY table_name;
   ```
   Should see: companies, company_schemas, company_deployments, etc.

#### **Option B: Using psql** (Advanced)

```bash
# Get your connection string from Supabase dashboard → Project Settings → Database
psql "postgresql://postgres:[password]@[host]/postgres" \
  -f migrations/master/001_create_master_tables.sql
```

---

### **Step 3: Run Setup Script (10 minutes)**

This wizard will:
- Create your master admin account
- Add Unit Industries to master
- Securely store all credentials

```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/CORTEX

# Install dependencies (if not already)
pip install bcrypt supabase

# Run setup wizard
python scripts/setup_master.py
```

**The script will prompt for:**

1. **Master Supabase credentials** (from Step 1)
2. **Your admin account:**
   - Email: nicolas@unit.com (or your email)
   - Password: [Choose strong password, min 12 chars]
3. **Unit Industries credentials** (get these from your Render env vars):
   - SUPABASE_URL
   - SUPABASE_ANON_KEY
   - SUPABASE_SERVICE_KEY
   - NEO4J_URI
   - NEO4J_PASSWORD
   - QDRANT_URL
   - QDRANT_API_KEY
   - QDRANT_COLLECTION_NAME
   - REDIS_URL
   - OPENAI_API_KEY
   - NANGO_SECRET_KEY
   - NANGO_PUBLIC_KEY
   - NANGO_PROVIDER_KEY_GMAIL
   - NANGO_PROVIDER_KEY_OUTLOOK
   - Admin PIN (current: 2525)

**Output:**
```
✅ Master control plane is ready!

Next steps:
  1. Add these to your Unit Industries Render env vars:
     COMPANY_ID=abc-123-uuid-here
     MASTER_SUPABASE_URL=https://xxx.supabase.co
     MASTER_SUPABASE_SERVICE_KEY=eyJhbGc...
```

**SAVE THE COMPANY_ID!** You'll need it next.

---

### **Step 4: Update Unit Industries Render Environment (5 minutes)**

**CRITICAL:** This enables multi-tenant mode for Unit Industries.

1. Go to https://dashboard.render.com
2. Find your `nango-connection-only` service
3. Click "Environment"
4. Add these NEW variables:
   ```bash
   COMPANY_ID=[UUID from setup script output]
   MASTER_SUPABASE_URL=https://[your-master-ref].supabase.co
   MASTER_SUPABASE_SERVICE_KEY=eyJhbGc... [from Step 1]
   ```
5. Click "Save Changes"
6. **Render will auto-redeploy** (~3 minutes)

**What happens on restart:**
- Backend detects `COMPANY_ID` env var
- Enables multi-tenant mode
- Connects to BOTH master + company Supabase
- Loads Unit Industries' schemas from master
- Everything else works exactly the same

**Logs to verify:**
```
🏢 Multi-tenant mode ENABLED (Company ID: abc-123...)
✅ Master Supabase connected (Company ID: abc-123...)
✅ Company Supabase connected
🏢 Loading schemas from MASTER Supabase (Company ID: abc-123...)
ℹ️  No custom entities for this company (using defaults only)
✅ Application started successfully
```

---

### **Step 5: Verify Multi-Tenant Mode (2 minutes)**

Check Render logs after deployment:

✅ **Success indicators:**
```
🏢 Initializing MULTI-TENANT mode...
✅ Master Supabase connected (Company ID: abc-123...)
✅ Company Supabase connected
```

❌ **If you see this (single-tenant mode):**
```
🏠 Initializing SINGLE-TENANT mode (backward compatible)...
```
→ Check that `COMPANY_ID` env var is set correctly in Render

---

### **Step 6: Test That Nothing Broke (5 minutes)**

1. **Test existing functionality:**
   - Go to https://connectorfrontend.vercel.app
   - Login as Anthony
   - Sync Gmail → Should work
   - Chat → Should work
   - Admin dashboard (PIN 2525) → Should work

2. **Test master control (via SQL for now, dashboard coming next):**
   ```sql
   -- In master Supabase SQL Editor:

   -- View companies
   SELECT slug, name, status FROM companies;

   -- View schemas for Unit Industries
   SELECT entity_type, description
   FROM company_schemas
   WHERE company_id = (SELECT id FROM companies WHERE slug = 'unit-industries');

   -- Should be empty (no custom schemas yet)

   -- Add a test custom entity
   INSERT INTO company_schemas (company_id, override_type, entity_type, description)
   VALUES (
     (SELECT id FROM companies WHERE slug = 'unit-industries'),
     'entity',
     'MACHINE',
     'Injection molding machines'
   );

   -- Verify
   SELECT entity_type FROM company_schemas
   WHERE company_id = (SELECT id FROM companies WHERE slug = 'unit-industries');
   ```

3. **Restart Unit Industries backend** (to load new schema):
   - Render dashboard → Manual Deploy → "Clear build cache & deploy"
   - Check logs for:
     ```
     ✅ Loaded 1 custom entities for this company: ['MACHINE']
     ```

4. **Verify MACHINE entity is now recognized:**
   - Sync an email mentioning machines
   - Check Neo4j:
     ```cypher
     MATCH (n:MACHINE) RETURN n LIMIT 5;
     ```
   - Should see MACHINE nodes!

---

## 🎉 You're Done! What You Have Now

### **Current State:**

```
Master Supabase (cortex-master)
├── companies table
│   └── Unit Industries (id: abc-123...)
├── company_schemas table
│   └── Unit Industries → MACHINE entity
├── company_team_members table
│   └── Anthony, Kevin, Sandra, Ramiro, Paul, Hayden
└── master_admins table
    └── nicolas@unit.com (YOU)

Unit Industries Backend (nango-connection-only.onrender.com)
├── Connected to Master Supabase (reads schemas)
├── Connected to Company Supabase (stores documents)
├── Custom entities: PERSON, COMPANY, ROLE, PURCHASE_ORDER, MATERIAL, CERTIFICATION, MACHINE ✨
└── Works exactly like before + multi-tenant support
```

---

## 🚀 What's Next

### **Phase 2: Build Master Admin Dashboard** (Coming Next!)

Frontend at `master-admin.vercel.app` where you:
- See list of ALL companies
- Click "Manage Unit Industries"
  - Edit their schema (add/remove entities)
  - Edit their team roster
  - View their metrics
  - Trigger manual syncs
- Click "Add New Company" → Deploy Acme Corp
- View global audit log

### **Phase 3: Deploy Second Company**

```bash
# One command to deploy new company:
python scripts/deploy_company.py --name "Acme Corporation" --slug acme-corp

# Creates:
# - New Supabase project
# - New Neo4j database
# - New Qdrant collection
# - New Render service
# - New Vercel frontend
# - All managed from your master dashboard
```

---

## ❓ FAQ

### **Q: Will this break my existing Unit Industries deployment?**
**A:** NO! Without `COMPANY_ID` env var, it runs in single-tenant mode (exactly like before). Only after you add `COMPANY_ID` does multi-tenant mode activate.

### **Q: Can I revert back to single-tenant?**
**A:** Yes! Just remove `COMPANY_ID`, `MASTER_SUPABASE_URL`, `MASTER_SUPABASE_SERVICE_KEY` from Render env vars and redeploy.

### **Q: Where are Unit Industries' documents stored?**
**A:** Still in their own Supabase project (no change). Master Supabase ONLY stores configuration (schemas, team, settings).

### **Q: How do I add custom entities now?**
**A:** Two ways:
1. **Via SQL** (for now):
   ```sql
   INSERT INTO company_schemas (company_id, override_type, entity_type, description)
   VALUES (
     (SELECT id FROM companies WHERE slug = 'unit-industries'),
     'entity',
     'PROJECT',
     'Manufacturing projects'
   );
   ```
2. **Via master admin dashboard** (coming next - click buttons, no SQL!)

### **Q: What if master Supabase goes down?**
**A:** Company backends cache schemas at startup. They'll continue working with cached schemas until restart. Master is only queried at startup, not per-request.

### **Q: How much does master Supabase cost?**
**A:** Free tier works fine (low usage, just config data). Upgrade to $25/month Pro if you have 50+ companies.

---

## 🔐 Security Notes

### **Credentials Storage**

**⚠️ IMPORTANT:** The setup script stores credentials in **PLAIN TEXT** in `company_deployments` table for now.

**Production TODO:**
```python
# In production, encrypt sensitive fields:
from cryptography.fernet import Fernet

# Generate key (store in env var: MASTER_ENCRYPTION_KEY)
key = Fernet.generate_key()
cipher = Fernet(key)

# Encrypt before storing
encrypted_password = cipher.encrypt(neo4j_password.encode())

# Decrypt when needed
decrypted_password = cipher.decrypt(encrypted_password).decode()
```

**For now (testing):** Master Supabase has RLS enabled + service role only access = reasonably secure.

### **Master Admin Authentication**

Currently: Email + bcrypt password

**Production TODO:**
- Add 2FA/TOTP
- Add rate limiting on login
- Add session management
- Add IP whitelisting

---

## 📊 Cost Breakdown

### **Current (Single-Tenant - Unit Industries Only):**
```
Supabase:          $25/month
Neo4j:             $65/month
Qdrant:            $50/month
Render (backend):  $21/month
Vercel (frontend): $20/month (or free)
-------------------------
Total:             $181/month
```

### **After Multi-Tenant Setup:**
```
Master Supabase:   $0/month (free tier)
Unit Industries:   $181/month (same as before)
-------------------------
Total:             $181/month (NO INCREASE!)
```

### **Adding Acme Corp:**
```
Master Supabase:   $0/month
Unit Industries:   $181/month
Acme Corp:         $181/month (new)
-------------------------
Total:             $362/month

Revenue if charging $500/month per company:
2 companies × $500 = $1000/month
Profit: $1000 - $362 = $638/month
```

---

## 🎯 Summary

**What you just built:**
- ✅ Master control plane (manage all companies from one place)
- ✅ Backward compatible (Unit Industries still works)
- ✅ Dynamic schema loading per company
- ✅ Foundation for deploying unlimited companies
- ✅ Enterprise-grade multi-tenancy

**What's still manual (coming next):**
- Master admin dashboard UI
- Automated company deployment
- Encryption of credentials
- Master API for programmatic access

**You're now ready to scale CORTEX to multiple companies! 🚀**

---

## 📞 Need Help?

1. Check Render logs for errors
2. Check master Supabase SQL Editor for data
3. Test SQL queries in FAQ section
4. Verify env vars are set correctly

**Common issues:**
- "Single-tenant mode" in logs → `COMPANY_ID` not set
- "Master Supabase not initialized" → Check `MASTER_SUPABASE_URL` and key
- "Could not load custom entities" → Check company_id matches in master DB
