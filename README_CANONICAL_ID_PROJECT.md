# Canonical ID Project - Quick Reference

**Status:** Paused - Waiting for Nango Response Examples
**Resume:** Next week with fresh AI agent
**Main Guide:** `CANONICAL_ID_SYSTEM_COMPLETE_GUIDE.md`

---

## What This Project Does

Eliminates 67% data duplication by using canonical IDs (thread_id for emails, file_id for files) instead of individual message_ids.

**Before:** 601 documents (271 emails, 174 duplicates)
**After:** ~200 documents (no duplicates)

---

## Files Changed

**Create:**
- `app/core/canonical_ids.py`
- `app/services/deduplication/universal_dedup.py`

**Modify:**
- `app/services/sync/providers/outlook.py` (line 78)
- `app/services/sync/providers/gmail.py` (line 91)
- `app/services/sync/persistence.py` (line 142)
- `app/services/preprocessing/normalizer.py` (delete 344-422, add 344-384)
- `app/services/rag/pipeline.py` (line 241)

---

## Current Status

**What's done:**
- ✅ Forensic analysis (87% code reusable)
- ✅ Architecture designed
- ✅ Complete implementation guide written
- ✅ All code changes mapped (exact line numbers)
- ✅ Test strategy defined
- ✅ Deployment plan ready

**What's blocked:**
- ⚠️ Need real Nango response examples from partner
- ⚠️ Must verify threadId format before coding

**Partner action:** Add Nango examples to Section 20 of main guide

---

## Next Week Pickup (For New Agent)

**Step 1:** Read `CANONICAL_ID_SYSTEM_COMPLETE_GUIDE.md` Section 31 (README for new agent)

**Step 2:** Verify Nango examples added (Section 20)
- If not added: Request from partner
- If added: Validate format matches our assumptions

**Step 3:** Follow implementation sequence (Section 7)
- Phase 1: Create 2 new files (2 hours)
- Phase 2-3: Modify 6 files (2 hours)
- Phase 4-5: Test and deploy (2 hours)

**Total time:** 4-6 hours

---

## Emergency Contacts

**If stuck:**
1. Check Section 13 (Troubleshooting)
2. Check Section 15 (Critical unknowns)
3. Review forensic analysis in `FORENSIC_ANALYSIS_CANONICAL_REFACTOR.md`

**If code doesn't match guide:**
- Codebase may have changed since Nov 14
- Re-run forensic analysis (read all files again)
- Update line numbers in guide

---

## Success Metrics

**Deployment successful if:**
- Supabase: ~200 docs (from 601)
- Logs: "🔄 Universal dedup for: outlook:thread:..."
- Reports: No duplicate chunks
- Tests: All passing

---

## Key Insights from This Session

1. **87% code reuse** - Don't rewrite, extract and generalize
2. **Drive/QB already canonical** - Only emails need conversion
3. **Email content accumulates** - Latest contains full thread (verified)
4. **Nango format critical** - Must validate before implementing
5. **Partner normalizes data** - Don't assume Nango API docs = reality

---

**Main guide:** `CANONICAL_ID_SYSTEM_COMPLETE_GUIDE.md` (800+ lines)
**This file:** Quick reference for project status
