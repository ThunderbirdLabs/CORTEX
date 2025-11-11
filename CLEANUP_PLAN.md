# Cleanup Execution Plan

## Current ingest_document() Structure

```
Lines 217-303: Function signature + try block start + field extraction
Lines 304-375: Build metadata, create Document object
Lines 376-385: Qdrant ingestion → self.qdrant_pipeline.run() ✅ KEEP
Lines 386-388: Old comment
Lines 389-586: Dead entity extraction code ❌ DELETE
Lines 587-588: Dead visualization fix call ❌ DELETE
Lines 589-591: Success logging ✅ KEEP
Lines 592-604: Return success dict (but uses undefined variables) ⚠️ MUST FIX
Lines 605: Empty line
Lines 606-614: Exception handler ✅ KEEP
```

## Target Structure After Cleanup

```python
Lines 217-303: Function signature + try block start + field extraction ✅
Lines 304-375: Build metadata, create Document object ✅
Lines 376-385: Qdrant ingestion ✅
Lines 386-388: NEW: Clean comment about vector-only
Lines 389-393: NEW: Success logging
Lines 394-402: NEW: Clean return dict (without entity counts)
Lines 403: Empty line
Lines 404-412: Exception handler ✅
```

## The Safe Edit

**Replace lines 389-604 with:**

```python
            logger.info(f"✅ DOCUMENT INGESTION COMPLETE: {title}")
            logger.info(f"={'*80}\n")

            return {
                "status": "success",
                "document_id": str(doc_id),
                "source_id": source_id,
                "title": title,
                "source": source,
                "document_type": document_type,
                "characters": len(content)
            }
```

This removes:
- Entity extraction code (196 lines)
- Visualization fix call (2 lines)
- Return fields that reference undefined variables (3 fields: chunks, entities, relationships)

Total lines deleted: 198 lines
