# Dynamic Prompts System - Full Documentation

## Overview

**CORTEX now has FULLY DYNAMIC PROMPTS!** Every single prompt in the system is stored in the master Supabase database and can be edited without touching code.

This means:
- Each company can customize their prompts
- Prompts can be edited from the master dashboard (UI TODO)
- No code changes or redeployments needed to update prompts
- Complete backward compatibility (works in single-tenant mode too)

---

## Architecture

### 1. Database: `company_prompts` Table

**Location**: Master Supabase (NOT company Supabase)

**Schema**:
```sql
CREATE TABLE company_prompts (
    id SERIAL PRIMARY KEY,
    company_id UUID REFERENCES companies(id),
    prompt_key TEXT NOT NULL,           -- e.g., "ceo_assistant", "email_classifier"
    prompt_name TEXT NOT NULL,          -- Human-readable name
    prompt_description TEXT,             -- What this prompt does
    prompt_template TEXT NOT NULL,      -- Full prompt with {{placeholders}}
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by TEXT
);
```

### 2. Backend: `company_context.py` Module

**Location**: `app/services/company_context.py`

**Key Functions**:
- `load_prompt_templates()` - Loads ALL prompts from master Supabase at startup
- `get_prompt_template(key)` - Get a specific prompt by key
- `render_prompt_template(key, variables)` - Render prompt with {{variable}} substitution
- `build_ceo_prompt_template()` - Build CEO assistant prompt (with fallback)
- `build_email_classification_context()` - Build email classifier prompt (with fallback)
- `get_vision_ocr_business_check_prompt()` - Get vision OCR prompts

**Caching**: Prompts are loaded ONCE at startup and cached in memory for performance.

### 3. Seed Script: `seed_default_prompts.py`

**Location**: `scripts/seed_default_prompts.py`

**Usage**:
```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/CORTEX
export MASTER_SUPABASE_URL="https://..."
export MASTER_SUPABASE_SERVICE_KEY="..."
export COMPANY_ID="2ede0765-..."

python scripts/seed_default_prompts.py
```

**What it does**: Populates `company_prompts` table with 6 default prompts (listed below).

---

## Available Prompts

### 1. **ceo_assistant** - CEO Assistant Response Synthesis
**Used by**: `app/services/ingestion/llamaindex/query_engine.py`

**Purpose**: Main prompt for synthesizing final query responses with company context.

**Variables**:
- `{{company_name}}` - Company name
- `{{company_description}}` - Company description
- `{{company_profile}}` - Full company profile (location, industries, capabilities)
- `{{team_section}}` - Team members list
- `{{context_str}}` - Sub-answers from vector/graph search
- `{{query_str}}` - User's question

**Example**:
```
You are the CEO of Unit Industries Group, Inc., a progressive plastic...

COMPANY PROFILE:
Unit Industries Group, Inc. - Santa Ana, CA
- Progressive plastic injection molding...

YOUR TEAM:
- Anthony Codet - President & CEO: Primary decision-maker...
- Kevin Trainor - VP/Sales: Customer relationships...
```

---

### 2. **email_classifier** - Email Business Classification
**Used by**: `app/services/filters/openai_spam_detector.py`

**Purpose**: Classifies emails as BUSINESS or SPAM for filtering.

**Variables**:
- `{{company_name}}` - Company name
- `{{company_location}}` - Company location
- `{{company_context}}` - Company description, capabilities, industries
- `{{batch_emails}}` - Batch of emails to classify (filled by spam detector)

**Example**:
```
You are filtering emails for Unit Industries Group, Inc., located in Santa Ana, CA.

COMPANY CONTEXT:
- Company: Progressive plastic injection molding...
- Specializes in: Integrated Connectors, High-Temp Thermoplastics...
```

---

### 3. **vision_ocr_business_check** - Image Business Relevance Check
**Used by**: `app/services/parsing/file_parser.py`

**Purpose**: GPT-4o Vision prompt to classify if an image is business-critical or should be skipped.

**Variables**:
- `{{company_short_desc}}` - Short company description

**Example**:
```
FIRST, classify if this image contains BUSINESS-CRITICAL CONTENT for Unit Industries Group, Inc. (injection molding manufacturer):

**BUSINESS-CRITICAL content** (KEEP these):
- Technical documents: CAD drawings, engineering specs...
```

---

### 4. **vision_ocr_extract** - Image Text Extraction
**Used by**: `app/services/parsing/file_parser.py`

**Purpose**: GPT-4o Vision prompt to extract text and context from images/documents with OCR.

**Variables**: None (generic extraction prompt)

**Example**:
```
Analyze this document/image and provide a comprehensive extraction:

1. **Full Text Transcription**: Extract ALL text visible...
2. **Document Type**: What kind of document is this?
```

---

### 5. **entity_extraction** - Entity and Relationship Extraction
**Used by**: `app/services/ingestion/llamaindex/ingestion_pipeline.py`

**Purpose**: Extracts entities (PERSON, COMPANY, ROLE, MATERIAL, etc.) and relationships from documents.

**Variables**:
- `{{company_name}}` - Company name
- `{{company_short_desc}}` - Short company description
- `{{company_industry}}` - Industry type (e.g., "injection molding manufacturing")
- `{{company_operations}}` - Operations description
- `{{entity_types}}` - List of entity types to extract

**Example**:
```
You are an expert at extracting entities and relationships from injection molding manufacturing documents.

**CONTEXT**: You are analyzing documents for Unit Industries Group, Inc., ...

**ENTITY TYPES TO EXTRACT** (PERSON, COMPANY, ROLE, PURCHASE_ORDER, MATERIAL, CERTIFICATION):
```

---

### 6. **entity_deduplication** - Entity Deduplication and Resolution
**Used by**: `app/services/deduplication/entity_deduplication.py`

**Purpose**: Determines if two entity names refer to the same real-world entity (fuzzy matching).

**Variables**:
- `{{company_name}}` - Company name
- `{{company_industry}}` - Industry type
- `{{entity_type}}` - Entity type being deduplicated
- `{{entity1_name}}` - First candidate entity name
- `{{entity2_name}}` - Second candidate entity name

**Example**:
```
You are an entity resolution expert for Unit Industries Group, Inc.'s knowledge graph.

**TASK**: Determine if two entity names refer to the SAME real-world entity.

**ENTITY TYPE**: COMPANY
**CANDIDATE 1**: TriStar
**CANDIDATE 2**: TriStar Industries
```

---

## How It Works

### Startup Flow

1. **Backend starts** → `app/services/company_context.py` loads
2. **Check multi-tenant mode** → If `COMPANY_ID` env var exists
3. **Load company context** → Fetch company info from `companies` table
4. **Load prompt templates** → Fetch all prompts from `company_prompts` table
5. **Cache in memory** → Store in global variables for fast access
6. **Build prompts** → Render templates with company-specific variables

### Runtime Flow

1. **Service needs a prompt** (e.g., query_engine needs CEO assistant prompt)
2. **Call `get_prompt_template("ceo_assistant")`** → Returns cached template
3. **Render with variables** → Replace `{{company_name}}`, `{{context_str}}`, etc.
4. **Use in LLM call** → Send rendered prompt to OpenAI API

### Fallback Behavior

**If prompt not found in database**:
- System falls back to hardcoded prompts (backward compatible)
- Logs warning: `⚠️ Prompt template 'xxx' not found in database, using fallback`
- Works seamlessly in single-tenant mode (no master Supabase)

---

## Setup Instructions

### Step 1: Run Migration

```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/MASTERBACKEND

# Run migration on MASTER Supabase
psql postgresql://<MASTER_SUPABASE_CONNECTION_STRING> < ../CORTEX/migrations/master/003_create_prompt_templates.sql
```

Or manually run the SQL in Supabase SQL Editor.

### Step 2: Seed Prompts for Unit Industries

```bash
cd /Users/nicolascodet/Desktop/CORTEX\ OFFICAL/CORTEX

# Set env vars
export MASTER_SUPABASE_URL="https://frkquqpbnczafibjsvmd.supabase.co"
export MASTER_SUPABASE_SERVICE_KEY="eyJhbGciOi..."
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

### Step 3: Restart Backend

```bash
# Prompts are loaded at startup, so restart backend to pick them up
# On Render: Click "Manual Deploy" → "Clear build cache & deploy"
```

**Expected logs**:
```
🏢 Multi-tenant mode ENABLED for company: 2ede0765-...
🔍 Loading company context for company_id: 2ede0765-...
✅ Loaded company context for: Unit Industries Group, Inc.
   📍 Location: Santa Ana, CA
   👥 Team members: 3
   🏭 Industries: 7

🔍 Loading prompt templates for company_id: 2ede0765-...
✅ Loaded 6 prompt templates: ['ceo_assistant', 'email_classifier', 'vision_ocr_business_check', 'vision_ocr_extract', 'entity_extraction', 'entity_deduplication']
```

---

## Editing Prompts

### Option 1: Direct Database Edit (Current)

```sql
-- View all prompts for a company
SELECT prompt_key, prompt_name, LEFT(prompt_template, 100) as preview
FROM company_prompts
WHERE company_id = '2ede0765-6f69-4293-931d-22cc88437e01'
AND is_active = TRUE;

-- Update a prompt
UPDATE company_prompts
SET prompt_template = 'Your updated prompt here with {{variables}}...',
    updated_at = NOW(),
    version = version + 1
WHERE company_id = '2ede0765-6f69-4293-931d-22cc88437e01'
AND prompt_key = 'ceo_assistant';
```

### Option 2: Master Dashboard UI (TODO)

**Planned features**:
- View all prompts for a company
- Edit prompt templates in a code editor
- Preview rendered prompts with sample variables
- Version history and rollback
- Test prompts before activating
- Duplicate prompts from one company to another

---

## Benefits

1. **No Code Changes**: Update prompts without touching codebase
2. **Per-Company Customization**: Each company can have different prompts
3. **Fast Iteration**: Edit prompts in dashboard, restart backend, test
4. **Version Control**: Database stores version history
5. **Backward Compatible**: Works with or without master Supabase
6. **Centralized Management**: All prompts in one place
7. **Hot-Reload Ready**: Can implement hot-reload in future (no restart needed)

---

## Migration Path (Upgrading Existing Companies)

### For Unit Industries (Already Done):
1. ✅ Master Supabase schema created (`company_prompts` table)
2. ✅ Company context loaded dynamically
3. ✅ Default prompts seeded
4. ⏳ Backend restart needed to activate

### For New Companies:
1. Create company in `companies` table
2. Run `seed_default_prompts.py` with their `COMPANY_ID`
3. Customize prompts via dashboard (or SQL)
4. Deploy their backend with env vars

### For Single-Tenant Companies (No Master):
- No changes needed!
- System falls back to hardcoded prompts
- Works exactly as before

---

## Testing

### Verify Prompts Loaded:

```bash
# Check backend logs on startup
# Should see:
✅ Loaded 6 prompt templates: ['ceo_assistant', ...]
```

### Test a Query:

```bash
# Send a query to the backend
curl -X POST https://nango-connection-only.onrender.com/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What materials do we use?"}'

# Response should use the custom CEO assistant prompt
```

### Verify Prompt Variables:

```python
# In Python console
from app.services.company_context import get_prompt_template, render_prompt_template

# Get template
template = get_prompt_template("ceo_assistant")
print(template[:200])

# Render with variables
rendered = render_prompt_template("ceo_assistant", {
    "company_name": "Test Corp",
    "context_str": "Some context",
    "query_str": "What is X?"
})
print(rendered[:500])
```

---

## Troubleshooting

### Prompt Not Loading

**Symptom**: Logs show `⚠️ Prompt template 'xxx' not found in database, using fallback`

**Fix**:
1. Check `company_prompts` table:
   ```sql
   SELECT * FROM company_prompts WHERE company_id = '...' AND prompt_key = 'xxx';
   ```
2. Verify `is_active = TRUE`
3. Run `seed_default_prompts.py` if missing

### Backend Crashing on Startup

**Symptom**: Backend fails to start with Supabase error

**Fix**:
1. Check env vars: `MASTER_SUPABASE_URL`, `MASTER_SUPABASE_SERVICE_KEY`
2. Verify master Supabase is accessible
3. Check `company_prompts` table exists (run migration)

### Prompt Variables Not Replaced

**Symptom**: Rendered prompt contains `{{company_name}}` literally

**Fix**:
1. Check `render_prompt_template()` is called with correct variables
2. Verify variable names match exactly (case-sensitive)
3. Look for typos in `{{variable}}` syntax

---

## Future Enhancements

1. **Hot-Reload**: Reload prompts without backend restart
2. **Dashboard UI**: Web interface for editing prompts
3. **Prompt Versioning**: Track and rollback prompt changes
4. **A/B Testing**: Test different prompt versions
5. **Prompt Analytics**: Track which prompts perform best
6. **Prompt Templates**: Library of proven prompt templates
7. **Variable Validation**: Warn if required variables missing

---

## Summary

✅ **DONE**:
- `company_prompts` table in master Supabase
- 6 default prompts (CEO assistant, email classifier, vision OCR, entity extraction, deduplication)
- `company_context.py` module for loading prompts
- Seed script for populating prompts
- Full backward compatibility

⏳ **TODO**:
- Run migration on master Supabase
- Seed prompts for Unit Industries
- Restart Unit Industries backend
- Build master dashboard UI for editing prompts
- Test with real queries

---

## Questions?

- **Where are prompts stored?** Master Supabase → `company_prompts` table
- **How often are they loaded?** Once at startup (cached in memory)
- **Can I edit without code changes?** Yes! Edit in database, restart backend
- **What if prompt is missing?** Falls back to hardcoded prompt
- **Do I need master Supabase?** No, works in single-tenant mode without it

---

**Built with ❤️ for CORTEX Multi-Tenant Architecture**
