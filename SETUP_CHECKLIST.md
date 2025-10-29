# ✅ CORTEX Multi-Tenant Setup Checklist

**Follow this step-by-step. Don't skip steps!**

---

## 📋 STEP 1: Create Master Supabase Project (5 min)

**YOU DO THIS NOW:**

1. Open https://supabase.com/dashboard
2. Click "New Project"
3. Fill in:
   ```
   Name: cortex-master
   Database Password: [GENERATE STRONG PASSWORD - SAVE IT!]
   Region: us-west-1
   Plan: Free
   ```
4. Click "Create new project"
5. Wait ~2 minutes for provisioning

6. **Once ready, go to Settings → API**
7. Copy these values:
   ```
   Project URL: https://xxxxx.supabase.co
   Project API keys:
   - anon key: eyJhbGc...
   - service_role key: eyJhbGc... (click "Reveal")
   ```

8. **SAVE THESE SECURELY!** You'll need them next.

**STATUS:** ⬜ Not started → ✅ Done

---

## 📋 STEP 2: Run Master Database Migrations (3 min)

**Option A: Using Supabase SQL Editor** (Easiest)

1. In your master Supabase dashboard
2. Click "SQL Editor" in left sidebar
3. Click "New Query"
4. Open file: `migrations/master/001_create_master_tables.sql`
5. Copy ALL contents (Cmd+A, Cmd+C)
6. Paste into SQL Editor
7. Click "Run" (bottom right)
8. Wait for "Success ✓" message

**Verify it worked:**
```sql
-- Run this query:
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Should see these tables:
-- audit_log_global
-- companies
-- company_deployments
-- company_schemas
-- company_team_members
-- master_admin_sessions
-- master_admins
```

**STATUS:** ⬜ Not started → ✅ Done

---

## 📋 STEP 3: Gather Unit Industries Credentials (5 min)

You'll need these from your **existing** Render deployment.

**Go to:** https://dashboard.render.com → `nango-connection-only` → Environment

**Copy these values:**

```bash
# Supabase (Unit Industries operational database)
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

# Neo4j
NEO4J_URI=
NEO4J_USER=
NEO4J_PASSWORD=

# Qdrant
QDRANT_URL=
QDRANT_API_KEY=
QDRANT_COLLECTION_NAME=

# Redis
REDIS_URL=

# OpenAI
OPENAI_API_KEY=

# Nango
NANGO_SECRET_KEY=
NANGO_PUBLIC_KEY=
NANGO_PROVIDER_KEY_GMAIL=
NANGO_PROVIDER_KEY_OUTLOOK=
NANGO_PROVIDER_KEY_GOOGLE_DRIVE=
```

**Have these ready in a text file!**

**STATUS:** ⬜ Not started → ✅ Done

---

## 📋 STEP 4: Run Setup Script (10 min)

**Now run the wizard:**

```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/CORTEX

# Check dependencies first
./scripts/check_dependencies.sh

# Run setup
python3 scripts/setup_master.py
```

**The wizard will ask for:**

1. **Master Supabase credentials** (from Step 1)
   - URL: https://xxxxx.supabase.co
   - Service key: eyJhbGc...

2. **Your master admin account** (create new password!)
   - Email: nicolas@unit.com (or your email)
   - Name: Nicolas Codet
   - Password: [Choose strong password, min 12 chars]
   - Confirm password: [same]

3. **Unit Industries credentials** (from Step 3)
   - Paste each value when prompted

4. **Admin PIN** (current value)
   - Enter: 2525

**At the end, you'll see:**

```
✅ Setup complete!

Next steps:
  1. Add these to your Unit Industries Render env vars:
     COMPANY_ID=abc-123-uuid-from-output
     MASTER_SUPABASE_URL=https://xxxxx.supabase.co
     MASTER_SUPABASE_SERVICE_KEY=eyJhbGc...
```

**SAVE THE COMPANY_ID!**

**STATUS:** ⬜ Not started → ✅ Done

---

## 📋 STEP 5: Install Master Frontend Dependencies (2 min)

```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/master-admin-frontend
npm install
```

Wait for dependencies to install (~1-2 minutes).

**STATUS:** ⬜ Not started → ✅ Done

---

## 📋 STEP 6: Configure Master Frontend (1 min)

Create `.env.local` file:

```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/master-admin-frontend

cat > .env.local << 'EOF'
NEXT_PUBLIC_MASTER_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_MASTER_SUPABASE_ANON_KEY=eyJhbGc...
NEXT_PUBLIC_MASTER_API_URL=http://localhost:8000
EOF
```

**Replace** `xxxxx.supabase.co` and `eyJhbGc...` with YOUR master Supabase values!

**STATUS:** ⬜ Not started → ✅ Done

---

## 📋 STEP 7: Test Master Frontend Locally (1 min)

```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/master-admin-frontend
npm run dev
```

**Open:** http://localhost:3001

You should see beautiful purple/pink gradient login page!

**STATUS:** ⬜ Not started → ✅ Done

---

## 📋 STEP 8: Update Unit Industries Render (ENABLE MULTI-TENANT) (5 min)

**⚠️ THIS IS THE BIG STEP - Enables multi-tenant mode**

1. Go to https://dashboard.render.com
2. Find service: `nango-connection-only`
3. Click "Environment"
4. Click "Add Environment Variable"
5. Add these **3 NEW** variables:

```bash
COMPANY_ID=[paste from Step 4 output - abc-123-uuid...]
MASTER_SUPABASE_URL=[paste from Step 1 - https://xxxxx.supabase.co]
MASTER_SUPABASE_SERVICE_KEY=[paste from Step 1 - eyJhbGc...]
```

6. Click "Save Changes"
7. **Render will auto-redeploy** (~3-5 minutes)

**STATUS:** ⬜ Not started → ✅ Done

---

## 📋 STEP 9: Verify Multi-Tenant Mode Enabled (2 min)

**Watch Render logs during deployment:**

1. Render dashboard → `nango-connection-only` → "Logs"
2. Look for these lines:

✅ **SUCCESS indicators:**
```
🏢 Initializing MULTI-TENANT mode...
✅ Master Supabase connected (Company ID: abc-123...)
✅ Company Supabase connected
🏢 Loading schemas from MASTER Supabase (Company ID: abc-123...)
ℹ️  No custom entities for this company (using defaults only)
✅ Application started successfully
```

❌ **If you see this (WRONG):**
```
🏠 Initializing SINGLE-TENANT mode (backward compatible)...
```

→ **FIX:** Go back to Step 8, make sure `COMPANY_ID` env var is set correctly

**STATUS:** ⬜ Not started → ✅ Done

---

## 📋 STEP 10: Test Unit Industries Still Works (5 min)

**CRITICAL: Make sure nothing broke!**

1. **Go to:** https://connectorfrontend.vercel.app
2. **Login** as Anthony
3. **Test sync:** Click sync Gmail → Should work
4. **Test chat:** Ask a question → Should work
5. **Test admin:** Go to `/admin`, PIN 2525 → Should work

**If ANY of these fail:**
- Check Render logs for errors
- Verify env vars are correct
- DM me the error!

**STATUS:** ⬜ Not started → ✅ Done

---

## 📋 STEP 11: Add Custom Entity (Test Dynamic Schemas) (3 min)

**Prove multi-tenant schema loading works!**

1. Go to master Supabase → SQL Editor
2. Run this query:

```sql
-- Add custom "MACHINE" entity for Unit Industries
INSERT INTO company_schemas (company_id, override_type, entity_type, description, created_by)
VALUES (
  (SELECT id FROM companies WHERE slug = 'unit-industries'),
  'entity',
  'MACHINE',
  'Injection molding machines and equipment',
  'nicolas@unit.com'
);

-- Verify it was added
SELECT entity_type, description
FROM company_schemas
WHERE company_id = (SELECT id FROM companies WHERE slug = 'unit-industries');
```

3. **Restart Unit Industries backend:**
   - Render dashboard → `nango-connection-only`
   - Click "Manual Deploy" → "Deploy latest commit"

4. **Check logs for:**
```
✅ Loaded 1 custom entities for this company: ['MACHINE']
```

5. **Test it works:**
   - Sync an email mentioning machines
   - Check Neo4j Studio:
   ```cypher
   MATCH (n:MACHINE) RETURN n LIMIT 5;
   ```
   - Should see MACHINE nodes! 🎉

**STATUS:** ⬜ Not started → ✅ Done

---

## 🎉 YOU'RE DONE!

**What you have now:**

✅ Master Supabase (control plane)
✅ Master admin dashboard frontend (localhost:3001)
✅ Unit Industries in multi-tenant mode
✅ Dynamic schema loading working
✅ Foundation for deploying multiple companies

**What's next:**

1. **Build master admin dashboard pages** (dashboard, companies, schema editor)
2. **Deploy master frontend to Vercel**
3. **Build master backend API** (auth, CRUD endpoints)
4. **Deploy master backend to Render**
5. **Deploy second company (Acme Corp)**

---

## 🚨 Troubleshooting

### **Problem: Setup script fails with "bcrypt not installed"**
```bash
pip install bcrypt supabase
```

### **Problem: "Single-tenant mode" in Render logs**
- Check `COMPANY_ID` env var is set in Render
- Check `MASTER_SUPABASE_URL` env var is set
- Redeploy after adding vars

### **Problem: "Could not load custom entities"**
- Check `COMPANY_ID` in Render matches company_id in master Supabase
- Check `MASTER_SUPABASE_SERVICE_KEY` is correct (not anon key!)

### **Problem: Unit Industries stops working**
- Remove the 3 new env vars from Render
- Redeploy
- It will go back to single-tenant mode (works like before)

---

## 📞 Need Help?

- Check `docs/MULTI_TENANT_SETUP.md` for detailed guide
- Check `docs/ENTERPRISE_ACTION_PLAN.md` for roadmap
- Check Render logs for error messages
- Check master Supabase for data

**LET'S BUILD THIS EMPIRE! 🚀**

