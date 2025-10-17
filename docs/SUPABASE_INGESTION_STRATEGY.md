# Supabase Ingestion Strategy - Complete Analysis

## 📊 Current Supabase Schema

### Table 1: `connections`
**Purpose:** Track OAuth connections to external providers

**Fields:**
- `id` (int): Primary key
- `tenant_id` (uuid): Tenant identifier
- `provider_key` (string): Provider name (e.g., "google-drive")
- `connection_id` (uuid): Unique connection identifier
- `created_at` (timestamp)
- `updated_at` (timestamp)

**Ingestion Status:** ⚠️ **NOT INGESTED** (metadata only, no content to index)

**Recommended Action:** Use for metadata enrichment only (e.g., link documents to connection source)

---

### Table 2: `documents`
**Purpose:** Store documents from external sources (Google Drive, SharePoint, etc.)

**Fields:**
- `id` (int): Primary key
- `tenant_id` (uuid): Tenant identifier
- `source` (string): Source system (e.g., "googledrive")
- `source_id` (string): External document ID
- `document_type` (string): Type (e.g., "googlesheet", "googledoc", "googlesslide")
- `title` (string): Document title
- **`content` (text): ✅ MAIN INGESTION FIELD**
- `raw_data` (json): Full API response from source
- `file_type` (string): MIME type
- `file_size` (int): Size in bytes
- `file_url` (string): Optional direct URL
- `source_created_at` (timestamp): Original creation date
- `source_modified_at` (timestamp): Last modified date
- `ingested_at` (timestamp): When fetched into Supabase
- **`metadata` (json): ⚠️ CRITICAL - Contains rich document metadata**
- `content_hash` (string): SHA256 hash for deduplication

**Metadata Structure (from sample):**
```json
{
  "parser": "unstructured",
  "file_name": "tmp4ohfripv.bin",
  "file_size": 1022,
  "file_type": "text/csv",
  "characters": 1022,
  "owner_name": "sales team",
  "owner_email": "wecare@thunderbird-labs.com",
  "num_documents": 1,
  "web_view_link": "https://docs.google.com/spreadsheets/...",
  "parent_folders": ["0AJhZDijs2AT2Uk9PVA"],
  "original_filename": "miso financials",
  "original_mime_type": "application/vnd.google-apps.spreadsheet"
}
```

**Ingestion Status:** ✅ **CURRENTLY INGESTED** (via UniversalIngestionPipeline)

**Issues Discovered:**
1. 🚨 **ALL metadata properties are copied to extracted entities** (violates Neo4j best practices)
2. ❌ **No MENTIONED_IN relationships** between entities and documents
3. ⚠️ **Rich metadata in `metadata` json field is being merged into doc_metadata**

---

### Table 3: `emails`
**Purpose:** Store emails from Gmail, Outlook, etc.

**Fields:**
- `id` (int): Primary key
- `tenant_id` (uuid): Tenant identifier
- `user_id` (string): User email address
- `user_principal_name` (string): User principal name
- `message_id` (string): External message ID
- `source` (string): Email provider (e.g., "gmail")
- `subject` (string): Email subject line
- `sender_name` (string): Sender display name
- `sender_address` (string): Sender email
- `to_addresses` (json array): List of recipient emails
- `received_datetime` (timestamp): When email was received
- `web_link` (string): Link to view in web client
- `change_key` (string): Version identifier
- `created_at` (timestamp): When ingested into Supabase
- **`full_body` (text): ✅ MAIN INGESTION FIELD**
- `episode_id` (uuid): Legacy field (not used in current architecture)
- `metadata` (json): Additional metadata

**Ingestion Status:** ✅ **CURRENTLY INGESTED** (via UniversalIngestionPipeline)

**Special Handling:** Creates SENT_BY and SENT_TO relationships to PERSON nodes

---

## 🔍 Critical Issues Identified

### Issue #1: Metadata Pollution on Entity Nodes
**Problem:** When ingesting documents, ALL document metadata (file_size, owner_name, web_view_link, etc.) is copied to EVERY extracted entity node.

**Example:**
```cypher
// WRONG - Current behavior
(:PERSON {name: "nick codet", owner_name: "sales team", file_size: 425, document_id: 3, ...})

// CORRECT - Expected behavior
(:PERSON {name: "nick codet", email: "nick@example.com"})
```

**Root Cause:**
```python
# Line 236-240 in ingestion_pipeline.py
if "metadata" in document_row and document_row["metadata"]:
    if isinstance(document_row["metadata"], dict):
        doc_metadata.update(document_row["metadata"])  # ← Merges ALL metadata
```

When DynamicLLMPathExtractor extracts entities, it inherits ALL metadata from the parent Document.

**Impact:**
- Storage bloat (each entity stores ~20 unnecessary properties)
- Query confusion (PERSON nodes have file_size, document_type, etc.)
- Violates Neo4j best practices
- Makes graph unusable for production

---

### Issue #2: Missing Entity→Document Relationships
**Problem:** No relationships exist connecting extracted entities back to source documents.

**Missing Pattern:**
```cypher
// SHOULD EXIST (but doesn't):
(:PERSON {name: "nick codet"}) -[:MENTIONED_IN]-> (:GOOGLESLIDE {title: "Shiba and knowldege"})
```

**Impact:**
- Can't answer: "Which documents mention Nick Codet?"
- Can't traverse: Document → Entities → Related Documents
- Breaks GraphRAG multi-hop reasoning
- Missing core value proposition of knowledge graph

---

### Issue #3: Old Ingestion Script Uses Deprecated Architecture
**File:** `scripts/ingestion/ingest_from_supabase.py`

**Problem:** Imports `HybridPropertyGraphPipeline` which:
1. No longer exists in codebase
2. Was using deprecated `SchemaLLMPathExtractor`
3. Has different API than `UniversalIngestionPipeline`

**Status:** ⚠️ **BROKEN** - needs to be updated or deleted

---

## ✅ Solution Strategy

### Phase 1: Fix Metadata Inheritance (HIGH PRIORITY)

**Approach:** Create two separate Document objects:
1. **Full metadata version** → For Qdrant (chunks need all metadata for filtering)
2. **Minimal metadata version** → For entity extraction (prevent pollution)

**Implementation:**
```python
# For Qdrant: Full metadata
doc_metadata_full = {...}  # All fields from Supabase row

document_for_qdrant = Document(
    text=content,
    metadata=doc_metadata_full  # Full metadata for chunk filtering
)

# For Entity Extraction: Minimal metadata
doc_metadata_minimal = {
    "document_id": str(doc_id),
    "title": title,
    "document_type": document_type,
}

document_for_extraction = Document(
    text=content,
    metadata=doc_metadata_minimal,  # Only essential fields
    excluded_llm_metadata_keys=list(doc_metadata_full.keys())  # Exclude from LLM
)
```

---

### Phase 2: Add Entity→Document Relationships

**Implementation:**
```python
# After entity extraction
for extracted_entity in entities:
    # Create MENTIONED_IN relationship
    mentioned_in_rel = Relation(
        label="MENTIONED_IN",
        source_id=extracted_entity.id,  # Entity node
        target_id=document_node.id,     # Document node
        properties={"extracted_at": str(datetime.now())}
    )
    self.graph_store.upsert_relations([mentioned_in_rel])
```

**Result:**
```cypher
(:PERSON {name: "nick codet"}) -[:MENTIONED_IN]-> (:GOOGLESLIDE {title: "Shiba..."})
(:COMPANY {name: "ACME Corp"}) -[:MENTIONED_IN]-> (:EMAIL {subject: "Welcome..."})
```

---

### Phase 3: Universal Table Support

**Current Status:**
- ✅ `documents` table: Fully supported
- ✅ `emails` table: Fully supported
- ⚠️ `connections` table: Not ingested (no content)

**Field Mapping:**
| Supabase Field | Universal Field | Notes |
|----------------|-----------------|-------|
| `content` | content | documents table |
| `full_body` | content | emails table |
| `title` | title | documents table |
| `subject` | title | emails table |
| `document_type` | document_type | documents table |
| (hardcoded "email") | document_type | emails table |
| `source` | source | Both tables |
| `id` | doc_id | Both tables |
| `tenant_id` | tenant_id | Both tables |

---

## 🎯 Implementation Plan

### Step 1: Update UniversalIngestionPipeline
- [ ] Split Document creation (full vs minimal metadata)
- [ ] Add MENTIONED_IN relationship creation
- [ ] Add metadata filtering configuration
- [ ] Test with sample row from each table

### Step 2: Clean Up Old Code
- [ ] Delete or update `scripts/ingestion/ingest_from_supabase.py`
- [ ] Remove any references to `HybridPropertyGraphPipeline`
- [ ] Verify no other scripts use deprecated architecture

### Step 3: Comprehensive Testing
- [ ] Create test that ingests 1 row from each table:
  - 1x connection (metadata only - document enrichment)
  - 1x document (Google Sheet)
  - 1x email (Gmail)
- [ ] Verify graph structure:
  - Entity nodes have ONLY entity properties
  - Document nodes have full metadata
  - MENTIONED_IN relationships exist
  - Graph traversal works

### Step 4: Production Validation
- [ ] Re-run production flow test with same 4 documents
- [ ] Verify critical fixes:
  - ✅ No metadata pollution on entities
  - ✅ MENTIONED_IN relationships present
  - ✅ All 3 table types work correctly
- [ ] Update `GRAPH_ANALYSIS_CRITICAL_ISSUES.md` with resolution

---

## 📐 Expected Graph Structure (After Fix)

### Document Nodes (Full Metadata)
```cypher
(:GOOGLESHEET {
  document_id: "2",
  title: "miso financials",
  content: "Category,Quarter,Revenue...",
  source: "googledrive",
  document_type: "googlesheet",
  tenant_id: "23e4af88...",
  source_id: "1RTp_DZw...",
  file_size: 1022,
  owner_name: "sales team",
  owner_email: "wecare@thunderbird-labs.com",
  web_view_link: "https://docs.google.com/...",
  // ... all other document metadata
})
```

### Entity Nodes (Clean, Minimal Properties)
```cypher
(:PERSON {
  id: "nick codet",
  name: "nick codet",
  email: "nick@example.com"  // Only if extracted from content
})

(:COMPANY {
  id: "acme corp",
  name: "ACME Corp"
})

(:TOPIC {
  id: "basketball analytics",
  name: "Basketball Analytics"
})
```

### Relationships
```cypher
// Entity → Document
(:PERSON {name: "nick codet"}) -[:MENTIONED_IN {extracted_at: "2025-10-16..."}]-> (:GOOGLESLIDE)

// Email-specific
(:EMAIL) -[:SENT_BY]-> (:PERSON {name: "Alex Thompson"})
(:EMAIL) -[:SENT_TO]-> (:PERSON {name: "Emma"})

// Entity → Entity (from extraction)
(:PERSON {name: "nick codet"}) -[:WORKS_ON]-> (:PROJECT {name: "JCAP Automation"})
```

---

## 🔐 Metadata Filtering Configuration

### Metadata That SHOULD Be Inherited (Minimal Set)
```python
ALLOWED_ENTITY_METADATA = {
    "document_id",   # For relationship creation
    "title",         # For context
    "document_type", # For filtering queries
}
```

### Metadata That SHOULD NOT Be Inherited
```python
EXCLUDED_FROM_ENTITIES = {
    "source_id", "source", "tenant_id",
    "file_size", "file_type", "file_url",
    "owner_name", "owner_email",
    "web_view_link", "parent_folders",
    "parser", "file_name", "characters",
    "created_at", "modified_at", "ingested_at",
    "content_hash", "raw_data",
    "sender_name", "sender_address", "to_addresses",
    "received_datetime", "message_id",
    # ... all other document-specific fields
}
```

---

## 📊 Testing Matrix

| Table | Row ID | Title/Subject | Expected Entities | Expected Relationships |
|-------|--------|---------------|-------------------|------------------------|
| documents | 2 | miso financials | TOPIC (Basketball, Shiba) | 2× MENTIONED_IN |
| documents | 3 | Shiba and knowldege | PERSON (nick codet), TOPIC | 2× MENTIONED_IN |
| emails | 6166 | Welcome to Cortex! | PERSON (Alex, Emma), COMPANY | 5× (2 SENT_BY/TO + 3 MENTIONED_IN) |

---

## ✅ Success Criteria

### Graph Quality
- [ ] Entity nodes contain ONLY entity properties (no file_size, owner_name, etc.)
- [ ] Document nodes contain full metadata
- [ ] MENTIONED_IN relationships link entities to source documents
- [ ] Can query: "Which documents mention X?"
- [ ] Can traverse: Document → Entities → Related Documents

### Code Quality
- [ ] No deprecated code (HybridPropertyGraphPipeline, SchemaLLMPathExtractor)
- [ ] No unused scripts
- [ ] Clear separation: Qdrant metadata vs Entity metadata
- [ ] Production-ready error handling

### Architecture Validation
- [ ] Follows 2025 LlamaIndex best practices
- [ ] Follows Neo4j graph modeling best practices
- [ ] Supports all Supabase tables (documents, emails, connections)
- [ ] Ready for 24/7 production operation

---

## 🚀 Next Steps

1. **Implement metadata filtering** in UniversalIngestionPipeline
2. **Add MENTIONED_IN relationships** after entity extraction
3. **Update or delete** old ingestion script
4. **Test with all 3 tables** (connections, documents, emails)
5. **Verify graph structure** is clean and follows best practices
6. **Update documentation** with resolution

---

## 📚 References

- Neo4j Best Practices: "Avoid property duplication, use relationships instead"
- LlamaIndex Docs: "excluded_llm_metadata_keys for metadata filtering"
- PropertyGraphIndex Pattern: "MENTIONS relationship from chunks to entities"
- Industry Standard: Entity→Document relationships for graph traversal
