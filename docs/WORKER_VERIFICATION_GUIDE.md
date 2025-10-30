# Worker Verification Guide

## What Was Fixed

We fixed the worker's inability to load dynamic prompts from master Supabase. The issue was that Dramatiq workers run in separate processes and don't execute FastAPI's startup event.

## The 3 Fixes Applied

### 1. Backend (FastAPI) - ✅ WORKING
**File**: `main.py` startup event
**Fix**: Initializes `master_supabase_client` when FastAPI starts
**Status**: Working perfectly - backend logs show all 6 prompts loaded

### 2. Worker (Dramatiq) - ⏳ NEEDS VERIFICATION
**File**: `app/services/background/tasks.py` line 25-32
**Fix**: Initializes `master_supabase_client` in `get_sync_dependencies()`
**Status**: Code committed, needs redeploy verification

### 3. Cron Job (Deduplication) - ⏳ WILL WORK ON NEXT RUN
**File**: `app/services/deduplication/run_dedup_cli.py` line 17-27
**Fix**: Initializes `master_supabase_client` in `main()` function
**Status**: Code committed, will work when cron runs

## How to Verify Worker Fix

After redeploying the worker service on Render, check the logs for this sequence:

### ✅ GOOD - Worker Initialization Success
```
🏢 Worker initializing multi-tenant mode (Company ID: 2ede0765-6f69-4293-931d-22cc88437e01)
✅ Worker: Master Supabase client initialized
🔍 Loading prompt templates for company_id: 2ede0765-6f69-4293-931d-22cc88437e01
✅ Loaded 6 prompt templates: ['ceo_assistant', 'email_classifier', 'entity_deduplication', 'entity_extraction', 'vision_ocr_business_check', 'vision_ocr_extract']
```

### ❌ BAD - Old Error (if still seeing this, redeploy didn't work)
```
[app.services.company_context] [ERROR] ❌ Master Supabase client not initialized
```

## What Each Process Does

### Backend Process
- **What**: Main FastAPI application
- **When**: Runs continuously on Render Web Service
- **Initializes**: In `@app.on_event("startup")`
- **Loads**: Schemas + prompts at startup
- **Uses**: CEO prompt for chat responses

### Worker Process
- **What**: Dramatiq background worker
- **When**: Runs continuously on Render Background Worker
- **Initializes**: In `get_sync_dependencies()` (called per task)
- **Loads**: All 6 prompts when creating RAG pipeline
- **Uses**: Email classifier, entity extraction, vision OCR prompts

### Cron Process
- **What**: Scheduled entity deduplication job
- **When**: Runs every X hours via Render Cron Job
- **Initializes**: In `main()` function at start
- **Loads**: Entity deduplication prompt
- **Uses**: AI decides which entities to merge

## Commits Applied

```bash
# CORTEX repo commits
4e69eb2 🔧 Fix: Initialize master_supabase_client in deduplication cron job
815b8fb 🔧 Fix: Initialize master_supabase_client in Dramatiq worker
2de7284 🔧 Fix: Use dynamic import for master_supabase_client to prevent None capture
312aa55 🔧 Fix: Make CEO prompt loading lazy to prevent NoneType error
```

All commits are pushed to main branch and ready to deploy.

## How Render Deployment Works

When you push to GitHub main branch:
1. **Web Service** (backend) - Auto-deploys from main branch
2. **Background Worker** - Auto-deploys from main branch
3. **Cron Job** - Auto-deploys from main branch

All three services should pick up the fixes automatically.

## Testing After Deployment

### Test 1: Backend Health Check
```bash
curl https://your-cortex-backend.onrender.com/health
```

Should return:
```json
{
  "status": "healthy",
  "multi_tenant_mode": true,
  "company_id": "2ede0765-6f69-4293-931d-22cc88437e01",
  "prompts_loaded": 6,
  "schemas_loaded": X
}
```

### Test 2: Trigger Worker Task
Go to frontend and trigger a Gmail sync. Watch worker logs for:
```
🏢 Worker initializing multi-tenant mode
✅ Worker: Master Supabase client initialized
✅ Loaded 6 prompt templates
```

### Test 3: Wait for Cron Job
Check cron job logs after next scheduled run for:
```
🏢 Cron job initializing multi-tenant mode
✅ Cron job: Master Supabase client initialized
🚀 Starting deduplication at XX:XX:XX UTC
```

## If Worker Still Shows Error

1. **Check Render Dashboard** - Verify Background Worker service redeployed
2. **Check Git Commit** - Verify worker service is using commit `815b8fb` or later
3. **Force Redeploy** - In Render dashboard, click "Manual Deploy" > "Clear build cache & deploy"
4. **Check Environment Variables** - Verify these are set on worker service:
   - `COMPANY_ID`
   - `MASTER_SUPABASE_URL`
   - `MASTER_SUPABASE_SERVICE_KEY`

## Expected Log Sequence on Worker Startup

```
[dramatiq.MainProcess] [INFO] Worker started
[dramatiq.WorkerThread] [INFO] Consuming messages from queue: default
[app.services.background.tasks] [INFO] 🏢 Worker initializing multi-tenant mode (Company ID: 2ede0765...)
[app.services.background.tasks] [INFO] ✅ Worker: Master Supabase client initialized
[app.services.company_context] [INFO] 🔍 Loading prompt templates for company_id: 2ede0765...
[app.services.company_context] [INFO] ✅ Loaded 6 prompt templates: ['ceo_assistant', 'email_classifier', ...]
[app.services.company_context] [INFO] 🔍 Loading schemas for company_id: 2ede0765...
[app.services.company_context] [INFO] ✅ Loaded X schemas
```

## The Dynamic Import Pattern Explained

### Why This Was Hard to Debug

Python imports work differently than you might expect:

```python
# ❌ BROKEN - Captures None at import time
from app.core.dependencies import master_supabase_client

def load_prompts():
    result = master_supabase_client.table("company_prompts")  # Still None!
```

Even though `master_supabase_client` gets initialized later, the variable captured at import time stays `None`.

### The Fix - Dynamic Import

```python
# ✅ WORKING - Gets current value
def _get_master_client():
    from app.core.dependencies import master_supabase_client
    return master_supabase_client

def load_prompts():
    client = _get_master_client()  # Gets current value, not import-time value
    result = client.table("company_prompts")  # Works!
```

This pattern is used throughout `company_context.py` to ensure we always get the current value of `master_supabase_client`.

## Summary

✅ **Backend**: Working perfectly - all prompts load
⏳ **Worker**: Fix committed, needs verification after redeploy
⏳ **Cron**: Fix committed, will work on next scheduled run

All code is pushed to GitHub main branch. Render auto-deploy should pick it up within a few minutes.
