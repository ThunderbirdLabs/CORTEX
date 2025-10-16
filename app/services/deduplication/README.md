# Deduplication Service

Clean, lightweight content-based deduplication to prevent duplicate documents from being ingested into RAG.

## How It Works

1. **Content Hashing**: Computes SHA256 hash of normalized content (case-insensitive, whitespace-normalized)
2. **Duplicate Detection**: Checks Supabase `documents` table for existing documents with same hash
3. **Auto-Skip**: If duplicate found, skips RAG ingestion (saves tokens & storage)
4. **Transparent**: Returns `{status: 'skipped', reason: 'duplicate'}` for monitoring

## Architecture

```
Document Flow:
1. Extract text → content
2. Normalize content (lowercase, trim whitespace)
3. Compute SHA256 hash
4. Check documents table for existing hash
5. If duplicate → skip ingestion
6. If unique → proceed to RAG pipeline
```

## Usage

Already integrated into `app/services/universal/ingest.py`:

```python
# Automatic deduplication (built-in)
result = await ingest_document_universal(
    supabase=supabase,
    cortex_pipeline=pipeline,
    tenant_id="user123",
    source="gmail",
    source_id="msg_abc",
    document_type="email",
    title="Q4 Report",
    content="..."
)

# If duplicate:
# {
#   'status': 'skipped',
#   'reason': 'duplicate',
#   'content_hash': 'abc123...'
# }
```

## Database Schema

Run migration first:

```bash
psql -h <host> -U postgres -d postgres -f migrations/add_content_hash_column.sql
```

Adds:
- `documents.content_hash` column (TEXT)
- Index on `(tenant_id, content_hash)` for fast lookups

## Configuration

Optional environment variable (future):
```bash
ENABLE_DEDUPLICATION=true  # Default: true
```

To disable for specific documents:
```python
result = await should_ingest_document(
    supabase, tenant_id, content, source,
    skip_dedupe=True  # Force ingestion
)
```

## Performance

- **Dedup Check**: ~5-10ms (indexed lookup)
- **Hash Computation**: ~1-2ms (SHA256 of normalized text)
- **Memory**: Negligible (no in-memory cache needed)

## Monitoring

Check logs for dedupe activity:
```
✅ No duplicate found (hash: abc123...)
⏭️  Skipping duplicate document: Q4 Report
```

Query duplicate stats:
```sql
-- Count duplicates skipped
SELECT COUNT(*) FROM documents 
WHERE metadata->>'is_duplicate' = 'true';

-- Find all duplicates of a document
SELECT * FROM documents 
WHERE content_hash = 'abc123...' 
ORDER BY ingested_at;
```

## Limitations

- **Content-based only**: Same content with different IDs = duplicate
- **Exact match**: Minor content changes = new document
- **Per-tenant**: Duplicate detection scoped to tenant_id
- **No fuzzy matching**: Use similarity search for near-duplicates

## Future Enhancements

- [ ] Fuzzy deduplication (Levenshtein distance, MinHash)
- [ ] Cross-tenant deduplication (optional)
- [ ] Dedupe reporting dashboard
- [ ] Configurable normalization strategies

