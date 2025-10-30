# Hardcoded vs Dynamic - Complete Analysis

## Summary: EVERYTHING IS NOW DYNAMIC ✅

As of commit `716e22b` (Oct 29, 2025), **ALL 6 prompts are 100% dynamic** with **ZERO hardcoded fallbacks**.

## The 6 Dynamic Prompts

| # | Prompt Key | Used By | Loads From | Fallback? |
|---|-----------|---------|------------|-----------|
| 1 | `ceo_assistant` | Query engine (chat responses) | Supabase | ❌ NO - FATAL error if missing |
| 2 | `entity_extraction` | Ingestion pipeline (extract entities) | Supabase | ❌ NO - FATAL error if missing |
| 3 | `entity_deduplication` | Dedup cron job (merge entities) | Supabase | ❌ NO - FATAL error if missing |
| 4 | `email_classifier` | Spam detector (filter emails) | Supabase | ❌ NO - FATAL error if missing |
| 5 | `vision_ocr_business_check` | File parser (check if image is business-relevant) | Supabase | ❌ NO - FATAL error if missing |
| 6 | `vision_ocr_extract` | File parser (extract text from images) | Supabase | ❌ NO - FATAL error if missing |

## What Happens If Prompt Is Missing?

### Old Behavior (Before Oct 29)
```python
# ❌ OLD - Had hardcoded fallbacks
template = get_prompt_template("ceo_assistant")
if not template:
    # 100+ lines of hardcoded fallback prompt
    template = """
    You are an intelligent personal assistant...
    [hardcoded prompt here]
    """
```

### New Behavior (Current)
```python
# ✅ NEW - No fallbacks, fail fast with clear error
template = get_prompt_template("ceo_assistant")
if not template:
    error_msg = "❌ FATAL: ceo_assistant prompt not found in Supabase! Run seed script: migrations/master/004_seed_unit_industries_prompts.sql"
    logger.error(error_msg)
    raise ValueError(error_msg)  # Backend won't start
```

**Result**: If any prompt is missing, backend/worker/cron **WILL NOT START** and will show exactly which prompt is missing and how to fix it.

## Code Locations

### 1. CEO Assistant Prompt
**File**: `app/services/ingestion/llamaindex/query_engine.py`
**Line**: 243
```python
ceo_assistant_prompt = PromptTemplate(get_ceo_prompt_template())
```

**Builder**: `app/services/company_context.py` line 249-265
```python
def build_ceo_prompt_template() -> str:
    # Load template from Supabase (no fallback allowed)
    logger.info("🔄 Loading ceo_assistant prompt from Supabase...")
    template = get_prompt_template("ceo_assistant")

    if not template:
        error_msg = "❌ FATAL: ceo_assistant prompt not found in Supabase!"
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info("✅ Loaded ceo_assistant prompt from Supabase")
    return template
```

**Hardcoded Fallback?** ❌ NO

---

### 2. Entity Extraction Prompt
**File**: `app/services/ingestion/llamaindex/ingestion_pipeline.py`
**Line**: 203
```python
entity_extraction_template = get_prompt_template("entity_extraction")
if not entity_extraction_template:
    error_msg = "❌ FATAL: entity_extraction prompt not found in Supabase!"
    logger.error(error_msg)
    raise ValueError(error_msg)
```

**Hardcoded Fallback?** ❌ NO

**Lines Removed**: 150+ lines of hardcoded prompt deleted in commit 716e22b

---

### 3. Entity Deduplication Prompt
**File**: `app/services/deduplication/entity_deduplication.py`
**Line**: 620
```python
dedup_template = get_prompt_template("entity_deduplication")
if not dedup_template:
    error_msg = "❌ FATAL: entity_deduplication prompt not found in Supabase!"
    logger.error(error_msg)
    raise ValueError(error_msg)
```

**Hardcoded Fallback?** ❌ NO

**Lines Removed**: 40+ lines of hardcoded prompt deleted in commit 716e22b

---

### 4. Email Classifier Prompt
**File**: `app/services/filters/openai_spam_detector.py`
**Line**: 85
```python
classifier_template = get_prompt_template("email_classifier")
if not classifier_template:
    error_msg = "❌ FATAL: email_classifier prompt not found in Supabase!"
    logger.error(error_msg)
    raise ValueError(error_msg)
```

**Hardcoded Fallback?** ❌ NO

**Lines Removed**: 30+ lines of hardcoded prompt deleted in commit 716e22b

---

### 5. Vision OCR Business Check Prompt
**File**: `app/services/parsing/file_parser.py`
**Line**: 69
```python
prompt = get_prompt_template("vision_ocr_business_check")
if not prompt:
    error_msg = "❌ FATAL: vision_ocr_business_check prompt not found in Supabase!"
    logger.error(error_msg)
    raise ValueError(error_msg)
```

**Hardcoded Fallback?** ❌ NO

**Lines Removed**: 40+ lines of hardcoded prompt deleted in commit 716e22b

---

### 6. Vision OCR Extract Prompt
**File**: `app/services/parsing/file_parser.py`
**Line**: 77
```python
prompt = get_prompt_template("vision_ocr_extract")
if not prompt:
    error_msg = "❌ FATAL: vision_ocr_extract prompt not found in Supabase!"
    logger.error(error_msg)
    raise ValueError(error_msg)
```

**Hardcoded Fallback?** ❌ NO

**Lines Removed**: 40+ lines of hardcoded prompt deleted in commit 716e22b

---

## Total Lines of Hardcoded Prompts Removed

**Commit**: `716e22b` - "🚀 REMOVE ALL HARDCODED PROMPTS - SUPABASE ONLY"

```
app/services/company_context.py                    | 111 lines removed
app/services/deduplication/entity_deduplication.py |  47 lines removed
app/services/filters/openai_spam_detector.py       |  32 lines removed
app/services/ingestion/llamaindex/ingestion_pipeline.py | 166 lines removed
app/services/parsing/file_parser.py                |  98 lines removed
---------------------------------------------------------------
TOTAL:                                             | 454 lines removed
```

**Result**: Removed **454 lines** of hardcoded prompt fallbacks across 5 files.

---

## Startup Logs - What You'll See

### Backend Startup (FastAPI)
```
🏢 Multi-tenant mode enabled (Company ID: 2ede0765-6f69-4293-931d-22cc88437e01)
✅ Master Supabase client initialized
🔍 Loading prompt templates for company_id: 2ede0765...
✅ Loaded 6 prompt templates: ['ceo_assistant', 'email_classifier', 'entity_deduplication', 'entity_extraction', 'vision_ocr_business_check', 'vision_ocr_extract']
```

### Worker Startup (Dramatiq)
```
🏢 Worker initializing multi-tenant mode (Company ID: 2ede0765-6f69-4293-931d-22cc88437e01)
✅ Worker: Master Supabase client initialized
🔄 Loading entity_extraction prompt from Supabase...
✅ Loaded entity_extraction prompt from Supabase (version loaded dynamically)
```

### Cron Job Startup (Deduplication)
```
🏢 Cron job initializing multi-tenant mode (Company ID: 2ede0765-6f69-4293-931d-22cc88437e01)
✅ Cron job: Master Supabase client initialized
🔄 Loading entity_deduplication prompt from Supabase...
✅ Loaded entity_deduplication prompt from Supabase (version loaded dynamically)
```

---

## What's Still Hardcoded?

### System Prompts (GPT-4o Vision)
**Location**: `app/services/ingestion/llamaindex/query_engine.py` line 80-84
```python
system_prompt=(
    f"You are an intelligent personal assistant to the CEO. Today's date is {current_date}.\n\n"
    "You have access to the entire company's knowledge..."
)
```

**Why?**: This is the LLM's base system prompt that sets context. The actual response synthesis prompt (`ceo_assistant`) is dynamic.

**Could be dynamic?**: Yes, but it's generic and doesn't need per-company customization. Only the synthesis prompt needs customization.

---

### Configuration (Not Prompts)
The following are configuration, NOT prompts:

1. **Entity/Relation Schemas** - Dynamic (loaded from `company_schemas` table)
2. **Company Context** - Dynamic (loaded from `companies` table)
3. **Team Members** - Dynamic (loaded from `company_team_members` table)
4. **Model Names** - Hardcoded config (`gpt-4o`, `text-embedding-3-large`)
5. **Temperature Settings** - Hardcoded config (0.3 for queries, 0.7 for extraction)

---

## How to Verify Everything Is Dynamic

### Step 1: Check Master Supabase
```sql
SELECT company_id, prompt_key, version, updated_at
FROM company_prompts
WHERE company_id = '2ede0765-6f69-4293-931d-22cc88437e01'
AND is_active = true
ORDER BY prompt_key;
```

**Expected Result**: 6 rows (one for each prompt)

### Step 2: Start Backend and Check Logs
```bash
# Backend should show:
✅ Loaded 6 prompt templates: ['ceo_assistant', 'email_classifier', 'entity_deduplication', 'entity_extraction', 'vision_ocr_business_check', 'vision_ocr_extract']
```

### Step 3: Edit a Prompt in Master Frontend
1. Go to https://master-frontend.vercel.app/dashboard/prompts
2. Select "Unit Industries"
3. Click "Edit" on any prompt
4. Change the text
5. Click "Save Changes"
6. Check version incremented

### Step 4: Restart Backend and Verify Change
```bash
# Clear prompt cache (restart backend)
# Send a chat message
# Check response uses NEW prompt
```

---

## Benefits of 100% Dynamic Prompts

### 1. No Redeployment Required
- Edit prompt in master frontend
- Restart backend (30 seconds)
- New prompt is live

### 2. Version Tracking
- Every prompt edit increments version number
- Full audit log in `audit_log_global`
- Can rollback by restoring old prompt text

### 3. Per-Company Customization
- Unit Industries can have different prompts than ACME Corp
- Same codebase, different AI behavior
- Perfect for white-label SaaS

### 4. Fail-Fast Error Handling
- If prompt missing, backend won't start
- Clear error message tells you exactly what to do
- No silent fallbacks that hide problems

### 5. A/B Testing Ready
- Easy to test prompt variations
- Just edit prompt and restart
- Compare results without touching code

---

## Migration History

### Before (Single-Tenant, Hardcoded)
```python
# ❌ OLD - Hardcoded in code
CEO_ASSISTANT_PROMPT = """
You are an intelligent personal assistant to the CEO.
[400+ lines of hardcoded prompt]
"""
```

**Problems**:
- Need code deploy to change prompts
- Can't customize per company
- Prompts scattered across 5+ files
- No version tracking
- No audit trail

### After (Multi-Tenant, Dynamic)
```python
# ✅ NEW - Loaded from Supabase
template = get_prompt_template("ceo_assistant")
if not template:
    raise ValueError("Prompt not found - run seed script!")
```

**Benefits**:
- Edit prompts via web UI
- Instant updates (just restart)
- One codebase, unlimited companies
- Full version history
- Complete audit trail

---

## Testing Checklist

### ✅ Backend Tests
- [ ] Backend starts successfully
- [ ] Logs show "Loaded 6 prompt templates"
- [ ] Chat responses use CEO prompt
- [ ] No errors about missing prompts

### ✅ Worker Tests
- [ ] Worker starts successfully
- [ ] Logs show "Worker: Master Supabase client initialized"
- [ ] Email sync works (uses email_classifier prompt)
- [ ] Entity extraction works (uses entity_extraction prompt)
- [ ] Vision OCR works (uses vision_ocr_* prompts)

### ✅ Cron Job Tests
- [ ] Cron job starts successfully
- [ ] Logs show "Cron job: Master Supabase client initialized"
- [ ] Deduplication runs (uses entity_deduplication prompt)
- [ ] No errors about missing prompts

### ✅ Master Frontend Tests
- [ ] Can view all 6 prompts
- [ ] Can edit any prompt
- [ ] Version increments on save
- [ ] Changes reflected in backend (after restart)

---

## Conclusion

**Question**: "theres nothing hardcoded now only dynamic?"

**Answer**: ✅ **CORRECT** - All 6 AI prompts are 100% dynamic with ZERO hardcoded fallbacks.

**Evidence**:
1. Commit `716e22b` removed **454 lines** of hardcoded prompts
2. All 6 prompts load from `company_prompts` table in master Supabase
3. If any prompt is missing, backend/worker/cron will NOT START (fail-fast)
4. Master frontend allows editing all prompts via web UI
5. Changes take effect immediately after restart (no redeploy)

**The only hardcoded things left are**:
- Base system prompts (generic LLM context)
- Configuration values (model names, temperatures)
- Code logic (not prompts)

**Everything that defines AI behavior per company is now dynamic and editable via the master admin dashboard.**
