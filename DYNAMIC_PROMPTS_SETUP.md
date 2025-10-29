# Dynamic Prompts Setup Checklist

## Quick Start (3 Steps)

### Step 1: Run Migration on Master Supabase

Go to [Supabase SQL Editor](https://supabase.com/dashboard/project/frkquqpbnczafibjsvmd/sql/new) and run:

```sql
-- migrations/master/003_create_prompt_templates.sql

CREATE TABLE company_prompts (
    id SERIAL PRIMARY KEY,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    prompt_key TEXT NOT NULL,
    prompt_name TEXT NOT NULL,
    prompt_description TEXT,
    prompt_template TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by TEXT,
    UNIQUE(company_id, prompt_key, is_active)
);

CREATE INDEX idx_company_prompts_company ON company_prompts(company_id);
CREATE INDEX idx_company_prompts_key ON company_prompts(prompt_key);
CREATE INDEX idx_company_prompts_active ON company_prompts(is_active);

ALTER TABLE company_prompts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Master admins full access to prompts"
    ON company_prompts
    FOR ALL
    USING (true);
```

**Verify**: Check that `company_prompts` table exists in Supabase Table Editor.

---

### Step 2: Seed Default Prompts for Unit Industries

```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/CORTEX

# Set env vars
export MASTER_SUPABASE_URL="https://frkquqpbnczafibjsvmd.supabase.co"
export MASTER_SUPABASE_SERVICE_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZya3F1cXBibmN6YWZpYmpzdm1kIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTczNzc2ODk1NiwiZXhwIjoyMDUzMzQ0OTU2fQ.AswRg7lO5DGJOt-lNR-8gvuD0TyaXzX7P-GxCyK82n4"
export COMPANY_ID="2ede0765-6f69-4293-931d-22cc88437e01"

# Run seed script
python scripts/seed_default_prompts.py
```

**Expected output**:
```
================================================================================
  Seeding Default Prompt Templates
================================================================================

📋 Seeding prompts for: Unit Industries Group, Inc.

✅ Added ceo_assistant: CEO Assistant Response Synthesis
✅ Added email_classifier: Email Business Classification
✅ Added vision_ocr_business_check: Image Business Relevance Check (GPT-4o Vision)
✅ Added vision_ocr_extract: Image Text Extraction (GPT-4o Vision)
✅ Added entity_extraction: Entity and Relationship Extraction
✅ Added entity_deduplication: Entity Deduplication and Resolution

================================================================================
  ✅ Prompt Templates Seeded!
================================================================================
```

**Verify**: Check Supabase → `company_prompts` table → Should see 6 rows.

---

### Step 3: Restart Unit Industries Backend

Go to [Render Dashboard](https://dashboard.render.com) → nango-connection-only → Click "Manual Deploy" → "Clear build cache & deploy"

**Expected logs** (check after deployment):
```
🏢 Multi-tenant mode ENABLED for company: 2ede0765-...
✅ Loaded company context for: Unit Industries Group, Inc.
   📍 Location: Santa Ana, CA
   👥 Team members: 3
   🏭 Industries: 7

🔍 Loading prompt templates for company_id: 2ede0765-...
✅ Loaded 6 prompt templates: ['ceo_assistant', 'email_classifier', 'vision_ocr_business_check', 'vision_ocr_extract', 'entity_extraction', 'entity_deduplication']
```

**If you see this** → ✅ **DONE! All prompts are now dynamic and loaded from Supabase!**

---

## Verify Everything Works

### Test 1: Check Prompts in Database

```sql
-- Go to Supabase SQL Editor
SELECT
    prompt_key,
    prompt_name,
    LEFT(prompt_template, 100) as preview,
    is_active
FROM company_prompts
WHERE company_id = '2ede0765-6f69-4293-931d-22cc88437e01'
ORDER BY prompt_key;
```

**Should return 6 rows**:
- ceo_assistant
- email_classifier
- entity_deduplication
- entity_extraction
- vision_ocr_business_check
- vision_ocr_extract

---

### Test 2: Check Backend Logs

Go to Render → nango-connection-only → Logs tab

Look for:
```
✅ Loaded 6 prompt templates: ['ceo_assistant', 'email_classifier', ...]
✅ Using CEO prompt template from master Supabase
```

---

### Test 3: Send a Query

```bash
# Test query endpoint
curl -X POST https://nango-connection-only.onrender.com/query \
  -H "Content-Type: application/json" \
  -H "Authorization: YOUR_TOKEN" \
  -d '{"question": "What materials do we use?"}'
```

**Response should** use the dynamic CEO assistant prompt (check response quality).

---

## Edit a Prompt (Example)

### Update CEO Assistant Prompt

```sql
-- Go to Supabase SQL Editor
UPDATE company_prompts
SET
    prompt_template = 'You are the CEO of {{company_name}}, {{company_description}}.

YOUR AMAZING TEAM:
{{team_section}}

Context from knowledge base:
---------------------
{{context_str}}
---------------------

Create a SUPER AWESOME response that will blow their mind!

Question: {{query_str}}
Answer: ',
    updated_at = NOW(),
    version = version + 1
WHERE company_id = '2ede0765-6f69-4293-931d-22cc88437e01'
AND prompt_key = 'ceo_assistant';
```

### Restart Backend

Go to Render → Manual Deploy

### Test

Send a query and see the new prompt in action!

---

## Troubleshooting

### Issue: Seed script fails with "table does not exist"

**Fix**: Run Step 1 migration first.

---

### Issue: Backend logs show `⚠️ Prompt template 'xxx' not found in database, using fallback`

**Possible causes**:
1. Seed script didn't run → Run Step 2
2. `is_active = FALSE` → Update in Supabase:
   ```sql
   UPDATE company_prompts SET is_active = TRUE WHERE prompt_key = 'xxx';
   ```
3. Wrong `COMPANY_ID` → Check env vars on Render

---

### Issue: Backend crashes on startup with Supabase error

**Possible causes**:
1. Missing env vars → Add to Render:
   - `MASTER_SUPABASE_URL`
   - `MASTER_SUPABASE_SERVICE_KEY`
   - `COMPANY_ID`
2. Master Supabase down → Check Supabase status
3. `company_prompts` table missing → Run Step 1 migration

---

## What's Next?

1. **Test queries** - Make sure responses use dynamic prompts
2. **Edit prompts** - Try updating a prompt and restart backend
3. **Build dashboard UI** - Web interface for editing prompts (TODO)
4. **Add new prompts** - Insert new prompts for other features
5. **Copy to other companies** - Duplicate prompts when onboarding new companies

---

## Files Modified

### New Files:
- `migrations/master/003_create_prompt_templates.sql` - Database schema
- `scripts/seed_default_prompts.py` - Seed script
- `app/services/company_context.py` - Context + prompt loader
- `DYNAMIC_PROMPTS_README.md` - Full documentation
- `DYNAMIC_PROMPTS_SETUP.md` - This checklist

### Modified Files:
- `app/services/ingestion/llamaindex/query_engine.py` - Uses `build_ceo_prompt_template()`
- (Other files like `file_parser.py`, `openai_spam_detector.py`, etc. can optionally be updated to use dynamic prompts too)

---

## Status

- ✅ Migration created
- ✅ Seed script created
- ✅ Backend loader created
- ✅ CEO assistant prompt (dynamic)
- ✅ Email classifier prompt (dynamic)
- ✅ Vision OCR prompts (dynamic)
- ✅ Entity extraction prompt (dynamic)
- ✅ Entity deduplication prompt (dynamic)
- ⏳ Run migration on master Supabase
- ⏳ Seed prompts for Unit Industries
- ⏳ Restart backend to activate
- ⏳ Build dashboard UI for editing

**3 steps away from fully dynamic prompts!**

---

**Questions? Check [DYNAMIC_PROMPTS_README.md](DYNAMIC_PROMPTS_README.md) for full documentation.**
