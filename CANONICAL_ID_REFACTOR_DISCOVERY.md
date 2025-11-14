# Canonical ID-Based Universal Deduplication: Complete Discovery & Refactor Plan

**Date:** 2025-11-14
**Current State:** 601 documents in Supabase, 14,438 points in Qdrant
**Goal:** Refactor to canonical ID-based deduplication to eliminate duplicates at ingestion time

---

## Executive Summary

This document provides a comprehensive analysis of the current ingestion architecture and a detailed refactor plan to implement canonical ID-based universal deduplication. The refactor will eliminate duplicate documents by using thread-level canonical IDs for emails and native IDs for other sources, replacing the current post-ingestion thread deduplication.

**Key Finding:** The codebase has a well-architected universal ingestion flow through `ingest_document_universal()`, but uses source-specific IDs (message_id, file_id) in the Supabase unique constraint, allowing thread duplicates. The refactor changes source_id to use canonical IDs (thread_id for emails, file_id for files, etc.) to prevent duplicates at upsert time.

---

## Phase 1: Current State Analysis

### A. ALL Ingestion Paths (Documented)

The codebase has **5 primary document ingestion paths**, all converging on `ingest_document_universal()`:

#### 1. **Gmail Email Sync** (Production Active)

**Entry Point:**
- `/api/v1/sync` (POST) → Manual trigger
- Nango webhook → `/nango/webhook` → Background task

**Flow:**
```
app/services/sync/orchestration/email_sync.py:run_gmail_sync()
├─> Line 341: nango_list_email_records() - Fetch from Nango
├─> Line 359: normalize_gmail_message() - Convert to unified schema
│   └─> app/services/sync/providers/gmail.py:normalize_gmail_message()
│       └─> Returns: {message_id, thread_id, subject, body, ...}
├─> Line 362: ingest_to_cortex() - Universal ingestion wrapper
│   └─> app/services/sync/persistence.py:ingest_to_cortex()
│       └─> Line 137: ingest_document_universal()
│           ├─> source: "gmail"
│           ├─> source_id: email.get("message_id")  ← INDIVIDUAL MESSAGE ID
│           └─> metadata: {thread_id, message_id}
└─> Line 404-432: Process attachments (if any)
    └─> Line 412: ingest_document_universal() for each attachment
        ├─> source: "gmail"
        └─> source_id: f"{message_id}_{attachment_id}"
```

**Current source_id:** `message_id` (individual email ID)
**Thread ID location:** `metadata.thread_id` and `raw_data.thread_id`

**Key File Locations:**
- Orchestrator: `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/orchestration/email_sync.py` (lines 277-478)
- Normalizer: `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/providers/gmail.py` (lines 13-110)
- Persistence: `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/persistence.py` (lines 45-174)

---

#### 2. **Outlook Email Sync** (Production Active)

**Entry Point:**
- `/api/v1/sync` (POST) → Manual trigger
- Nango webhook → `/nango/webhook` → Background task

**Flow:**
```
app/services/sync/orchestration/email_sync.py:run_tenant_sync()
├─> Line 88: nango_list_email_records() - Fetch from Nango
├─> Line 107: normalize_outlook_message() - Convert to unified schema
│   └─> app/services/sync/providers/outlook.py:normalize_outlook_message()
│       └─> Returns: {message_id, thread_id, subject, body, ...}
├─> Line 126: ingest_to_cortex() - Universal ingestion wrapper
│   └─> app/services/sync/persistence.py:ingest_to_cortex()
│       └─> Line 137: ingest_document_universal()
│           ├─> source: "outlook"
│           ├─> source_id: normalized["message_id"]  ← INDIVIDUAL MESSAGE ID
│           └─> metadata: {thread_id, message_id}
└─> Line 163-211: Process attachments (if any)
    └─> Line 181: ingest_document_universal() for each attachment
        ├─> source: "outlook"
        └─> source_id: f"{message_id}_{attachment_id}"
```

**Current source_id:** `message_id` (individual email ID from Outlook)
**Thread ID location:** `metadata.thread_id` and `raw_data.thread_id`

**Key File Locations:**
- Orchestrator: `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/orchestration/email_sync.py` (lines 36-270)
- Normalizer: `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/providers/outlook.py` (lines 47-126)

---

#### 3. **Google Drive File Sync** (Production Active)

**Entry Point:**
- `/api/v1/sync` (POST with `sync_type=drive`)
- Manual trigger

**Flow:**
```
app/services/sync/orchestration/drive_sync.py:run_drive_sync()
├─> Line 223: nango_list_drive_files() - Fetch from Nango/Drive API
├─> Line 242: normalize_drive_file() - Convert to unified schema
│   └─> app/services/sync/providers/google_drive.py:normalize_drive_file()
│       └─> Returns: {file_id, file_name, mime_type, ...}
├─> Line 282: nango_fetch_file() - Download file bytes
└─> Line 292: ingest_document_universal()
    ├─> source: "googledrive"
    ├─> source_id: normalized["file_id"]  ← DRIVE FILE ID (STABLE)
    └─> document_type: "googledoc" | "googlesheet" | "file"
```

**Current source_id:** `file_id` (Google Drive file ID - already canonical!)
**No thread concept:** Files don't have threads, file_id is already unique per file

**Key File Locations:**
- Orchestrator: `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/orchestration/drive_sync.py` (lines 142-359)
- Normalizer: `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/providers/google_drive.py` (lines 12-120)

---

#### 4. **QuickBooks Data Sync** (Production Active)

**Entry Point:**
- `/api/v1/sync` (POST with `sync_type=quickbooks`)
- Manual trigger

**Flow:**
```
app/services/sync/orchestration/quickbooks_sync.py:run_quickbooks_sync()
├─> Line 278: nango_fetch_quickbooks_records("/invoices")
│   └─> For each invoice:
│       ├─> Line 283: normalize_quickbooks_invoice()
│       │   └─> Returns: {source_id: f"invoice-{invoice_id}", ...}
│       └─> Line 286: ingest_document_universal()
│           ├─> source: "quickbooks"
│           ├─> source_id: f"invoice-{invoice_id}"  ← STABLE QB RECORD ID
│           └─> document_type: "invoice"
├─> Line 310: Process Bills (same pattern)
├─> Line 339: Process Payments (same pattern)
└─> Line 366: Process Customers (same pattern)
```

**Current source_id:** Prefixed record IDs:
- Invoices: `invoice-{invoice_id}`
- Bills: `bill-{bill_id}`
- Payments: `payment-{payment_id}`
- Customers: `customer-{customer_id}`

**Already canonical:** QuickBooks record IDs are stable and unique per record type

**Key File Locations:**
- Orchestrator: `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/orchestration/quickbooks_sync.py` (lines 220-415)
- Normalizers: Same file, lines 29-217 (4 normalizer functions)

---

#### 5. **File Upload** (Production Active)

**Entry Point:**
- `/api/v1/upload/file` (POST)
- `/api/v1/upload/files` (POST for batch)

**Flow:**
```
app/api/v1/routes/upload.py:upload_file()
├─> Line 143: sanitize_filename() - Security check
├─> Line 147: Read file bytes (streaming, size-limited)
└─> Line 160: ingest_document_universal()
    ├─> source: "upload"
    ├─> source_id: safe_filename  ← FILENAME-BASED (NOT CANONICAL!)
    └─> document_type: "file"
```

**Current source_id:** Sanitized filename (e.g., "Q4_Report.pdf")
**Problem:** Uploading same file twice with same name = duplicate prevention, but different names = duplicates

**Key File Locations:**
- Upload route: `/Users/alexkashkarian/Desktop/HighForce/app/api/v1/routes/upload.py` (lines 96-202)
- Batch upload: Same file, lines 205-312

---

### B. Current Deduplication Mechanisms

The system has **3 layers of deduplication** with varying effectiveness:

#### 1. **Supabase Unique Constraint** (Primary Prevention)

**Location:** `/Users/alexkashkarian/Desktop/HighForce/migrations/create_documents_table.sql` (line 40)

```sql
UNIQUE(tenant_id, source, source_id)
```

**How it works:**
- Prevents exact duplicate documents with same `(tenant_id, source, source_id)`
- Uses PostgreSQL upsert with `on_conflict='tenant_id,source,source_id'`
- Located in `normalizer.py` line 304-307

**What it prevents:**
- ✅ Re-syncing same Gmail message ID → Updates existing
- ✅ Re-syncing same Drive file ID → Updates existing
- ✅ Re-uploading same filename → Updates existing

**What it DOESN'T prevent:**
- ❌ Multiple emails in same thread (different message_ids)
- ❌ Re-uploading same file with different filename
- ❌ Content duplicates across sources

---

#### 2. **Content Hash Deduplication** (Secondary Check)

**Location:** `/Users/alexkashkarian/Desktop/HighForce/app/services/preprocessing/content_deduplication.py`

**Implementation:**
```python
# Line 134-171: should_ingest_document()
# Line 48-59: compute_content_hash() - SHA256 of normalized content
```

**How it works:**
1. Normalize content (lowercase, whitespace removal)
2. Compute SHA256 hash
3. Check `documents.content_hash` for existing hash
4. Skip ingestion if duplicate found

**Current status:** Line 181 in `normalizer.py`:
```python
skip_dedupe=True  # TEMPORARY: Skip deduplication for testing
```

**Database support:** `/Users/alexkashkarian/Desktop/HighForce/migrations/add_content_hash_column.sql`
- Adds `content_hash` column
- Creates index on `(tenant_id, content_hash)`

**What it prevents (when enabled):**
- ✅ Exact content duplicates across sources
- ✅ Copy-paste emails
- ✅ Same file uploaded through different paths

**Limitations:**
- ❌ Currently disabled (`skip_dedupe=True`)
- ❌ Minor content changes = new document
- ❌ Email threading not considered

---

#### 3. **Thread Deduplication** (Post-Ingestion Cleanup)

**Location:** `/Users/alexkashkarian/Desktop/HighForce/app/services/preprocessing/normalizer.py` (lines 345-422)

**How it works:**
```python
# Line 349-352: Check if email has thread_id
thread_id = metadata.get('thread_id')
if thread_id and document_type == 'email' and source_created_at:
    # Delete older emails in same thread from Qdrant
    # Keep only the latest email per thread
```

**Algorithm:**
1. After document saved to Supabase
2. Before Qdrant ingestion
3. Query Qdrant for existing emails with same `thread_id`
4. Compare timestamps
5. Delete older emails from Qdrant (lines 404-416)

**What it prevents:**
- ✅ Multiple emails per thread in Qdrant
- ✅ Reply-all chains collapsing to latest
- ✅ Forward chains collapsing to latest

**What it DOESN'T prevent:**
- ❌ Duplicates still exist in Supabase (all messages stored)
- ❌ Qdrant points still ingested before deletion (wasteful)
- ❌ Race conditions during concurrent sync (line 411 comment)
- ❌ 601 documents in Supabase but only need 1 per thread

**Dependencies:**
- Requires Qdrant indexes: `thread_id`, `message_id`, `tenant_id`, `document_type`
- Created by: `/Users/alexkashkarian/Desktop/HighForce/app/services/rag/indexes.py`
- See also: `/Users/alexkashkarian/Desktop/HighForce/create_qdrant_thread_index.py`

**Performance issues:**
- Lines 366-399: Pagination loop to handle >1000 chunks per thread
- Line 412-415: Delete operation for every email ingestion
- Runs synchronously during ingestion flow

---

### C. Supabase Schema Analysis

**Primary Table:** `documents`
**Migration:** `/Users/alexkashkarian/Desktop/HighForce/migrations/create_documents_table.sql`

**Key Fields:**
```sql
id BIGSERIAL PRIMARY KEY                    -- Auto-increment
tenant_id TEXT NOT NULL                     -- Multi-tenant isolation
source TEXT NOT NULL                        -- 'gmail', 'outlook', 'googledrive', etc.
source_id TEXT NOT NULL                     -- External ID (message_id, file_id, etc.)
document_type TEXT NOT NULL                 -- 'email', 'file', 'attachment', etc.
title TEXT NOT NULL                         -- Subject/filename
content TEXT NOT NULL                       -- Extracted plain text
content_hash TEXT                           -- SHA256 for dedup (added in migration)
raw_data JSONB                              -- Preserve original structure
file_type TEXT                              -- MIME type
file_size BIGINT                            -- Bytes
file_url TEXT                               -- Supabase Storage URL
source_created_at TIMESTAMPTZ               -- Original creation time
source_modified_at TIMESTAMPTZ              -- Last modification
ingested_at TIMESTAMPTZ DEFAULT NOW()       -- When we ingested it
metadata JSONB DEFAULT '{}'                 -- Flexible metadata
parent_document_id BIGINT                   -- FK to self (for attachments)
```

**Unique Constraint:**
```sql
UNIQUE(tenant_id, source, source_id)  -- Line 40
```

**Indexes:**
```sql
idx_documents_tenant (tenant_id)
idx_documents_source (source)
idx_documents_source_type (source, document_type)
idx_documents_created (source_created_at DESC)
idx_documents_ingested (ingested_at DESC)
idx_documents_metadata (metadata) USING GIN
idx_documents_raw_data (raw_data) USING GIN
idx_documents_content_hash (tenant_id, content_hash)  -- From add_content_hash_column.sql
```

**What breaks if we change source_id:**

Current behavior:
```sql
-- Gmail: Each email in thread gets own row
INSERT INTO documents (source_id, ...) VALUES ('msg_001', ...);  -- Email 1
INSERT INTO documents (source_id, ...) VALUES ('msg_002', ...);  -- Reply (same thread)
INSERT INTO documents (source_id, ...) VALUES ('msg_003', ...);  -- Reply to reply
-- Result: 3 rows in documents table
```

After canonical ID refactor:
```sql
-- Gmail: All emails in thread share same source_id (thread_id)
INSERT INTO documents (source_id, ...) VALUES ('thread_abc', ...);  -- Email 1
INSERT INTO documents (source_id, ...) VALUES ('thread_abc', ...)   -- Reply (UPSERT!)
  ON CONFLICT (tenant_id, source, source_id) DO UPDATE ...
-- Result: 1 row in documents table (latest email content)
```

**Critical question:** Do we want to preserve all emails or only latest per thread?
- **Current system:** Preserves all in Supabase, latest in Qdrant
- **Proposed system:** Only latest everywhere (like Gmail's "conversation view")

---

### D. Qdrant Structure Analysis

**Collection:** `cortex_collection` (from env var `QDRANT_COLLECTION_NAME`)
**Current state:** 14,438 points (chunks from 601 documents)

**Payload Structure** (from `pipeline.py` lines 231-294):

```python
{
    # Core identifiers
    "document_id": str(supabase_doc_id),      # Links back to Supabase
    "source_id": str,                          # Same as Supabase source_id
    "title": str,
    "source": "gmail" | "outlook" | "googledrive" | ...,
    "document_type": "email" | "file" | "attachment",
    "tenant_id": str,

    # Timestamps
    "created_at": ISO string,
    "created_at_timestamp": int,               # Unix timestamp for filtering

    # Thread deduplication (EMAIL ONLY)
    "thread_id": str,                          # From metadata.thread_id or raw_data.thread_id
    "message_id": str,                         # Individual message ID

    # File metadata (FILES ONLY)
    "file_url": str,
    "file_size_bytes": int,
    "mime_type": str,

    # Attachments
    "parent_document_id": str,                 # For grouping attachments with parent

    # Email fields
    "sender_name": str,
    "sender_address": str,
    "to_addresses": JSON string (list),
    "user_id": str,
    "web_link": str,

    # Additional metadata (merged from documents.metadata)
    # ... variable fields
}
```

**Payload Indexes** (created by `indexes.py`):
```python
PayloadSchemaType.KEYWORD:
  - document_type      # Fast filtering by type
  - source             # Fast filtering by source
  - tenant_id          # Multi-tenant isolation

PayloadSchemaType.INTEGER:
  - created_at_timestamp  # Time-based queries
```

**Missing indexes for thread dedup:**
- `thread_id` - Currently created manually by `create_qdrant_thread_index.py`
- `message_id` - Currently created manually

**Chunking Strategy:**
- Uses LlamaIndex `SentenceSplitter`
- Chunk size: 1024 tokens (from `config.py`)
- Chunk overlap: 200 tokens
- Each chunk inherits parent document's payload metadata

**Example document breakdown:**
```
Email with 5000 words
├─> SentenceSplitter creates ~12 chunks
├─> Each chunk gets own Qdrant point
├─> All 12 points share same metadata (thread_id, message_id, etc.)
└─> Thread dedup deletes all 12 points when newer email arrives
```

**Current problem:**
- Email thread with 5 messages = 60 Qdrant points (5 × 12 chunks each)
- Thread dedup keeps only latest message = 12 points
- But Supabase still has all 5 messages (601 documents)
- Mismatch between Supabase (all messages) and Qdrant (latest only)

---

## Phase 2: Canonical ID Mapping Design

### A. Canonical ID Strategy (Per Source)

The canonical ID should represent the **logical document unit** for deduplication:

#### 1. **Gmail Emails** → `thread_id`

**Rationale:** Gmail's API groups emails into threads (conversations). A thread represents a single discussion, even with multiple messages.

**Implementation:**
```python
def get_gmail_canonical_id(normalized_message: dict) -> str:
    """
    Get canonical ID for Gmail message.

    Uses thread_id as canonical because:
    - Gmail threads are stable across API calls
    - Threads group related messages (replies, forwards)
    - Matches user mental model (Gmail's conversation view)

    Returns:
        thread_id if available, else message_id (fallback for drafts)
    """
    thread_id = normalized_message.get("thread_id")
    message_id = normalized_message.get("message_id")

    if thread_id and thread_id.strip():
        return thread_id

    # Fallback: Drafts/sent items may not have thread_id
    return message_id
```

**Current location:** `metadata.thread_id` in normalized message
**Example:** `thread_1a2b3c4d5e6f` (Gmail thread ID)

**Edge cases:**
- Drafts: May not have thread_id → Use message_id
- Sent items: Have thread_id
- Empty thread_id ("" or null): Use message_id as fallback

---

#### 2. **Outlook Emails** → `thread_id` (conversationId)

**Rationale:** Outlook uses `conversationId` to group emails, similar to Gmail threads.

**Implementation:**
```python
def get_outlook_canonical_id(normalized_message: dict) -> str:
    """
    Get canonical ID for Outlook message.

    Uses thread_id (Outlook's conversationId) as canonical.
    Outlook threads work similarly to Gmail.

    Returns:
        thread_id if available, else message_id
    """
    thread_id = normalized_message.get("thread_id")  # Nango maps conversationId → thread_id
    message_id = normalized_message.get("message_id")

    if thread_id and thread_id.strip():
        return thread_id

    return message_id
```

**Current location:** `metadata.thread_id` (Nango normalizes Outlook's conversationId)
**Example:** `AAQkAGI4MzQ...` (Outlook conversation ID)

---

#### 3. **Google Drive Files** → `file_id` (ALREADY CANONICAL)

**Rationale:** Drive file IDs are stable and unique per file. No need to change.

**Implementation:**
```python
def get_drive_canonical_id(normalized_file: dict) -> str:
    """
    Get canonical ID for Google Drive file.

    Drive file_id is already canonical:
    - Stable across API calls
    - Unique per file
    - Version history managed by Drive itself

    Returns:
        file_id
    """
    return normalized_file.get("file_id")
```

**Current location:** `normalized["file_id"]`
**Example:** `1a2b3c4d5e6f7g8h9i0j` (Google Drive file ID)

**No change needed:** Drive sync already uses file_id as source_id

---

#### 4. **QuickBooks Records** → Prefixed record IDs (ALREADY CANONICAL)

**Rationale:** QuickBooks record IDs are unique per record type. Current prefixing is good.

**Implementation:**
```python
def get_quickbooks_canonical_id(record_type: str, record: dict) -> str:
    """
    Get canonical ID for QuickBooks record.

    Uses prefixed record ID:
    - invoice-{invoice_id}
    - bill-{bill_id}
    - payment-{payment_id}
    - customer-{customer_id}

    Prefix prevents collisions across record types.

    Returns:
        Prefixed record ID
    """
    record_id = record.get("id")
    return f"{record_type}-{record_id}"
```

**Current location:** Already implemented in `quickbooks_sync.py` normalizers
**Examples:**
- `invoice-12345`
- `bill-67890`
- `payment-54321`
- `customer-98765`

**No change needed:** QuickBooks already uses canonical IDs

---

#### 5. **File Uploads** → Content hash or generated UUID

**Rationale:** Filenames are not reliable (user can rename). Need content-based or system-generated ID.

**Option A: Content hash** (Recommended)
```python
def get_upload_canonical_id(file_bytes: bytes, filename: str) -> str:
    """
    Get canonical ID for uploaded file.

    Uses SHA256 hash of file bytes:
    - Same file = same ID (dedup across uploads)
    - Different file = different ID
    - Filename independent

    Returns:
        SHA256 hash as canonical ID
    """
    import hashlib
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    return f"upload-{file_hash[:16]}"  # Truncate for readability
```

**Option B: UUID + filename** (Simpler)
```python
def get_upload_canonical_id(filename: str) -> str:
    """
    Get canonical ID for uploaded file.

    Uses UUID + sanitized filename:
    - Unique per upload
    - Preserves filename for user reference
    - No deduplication (user may want duplicate files)

    Returns:
        UUID-prefixed filename
    """
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    return f"upload-{unique_id}-{filename}"
```

**Recommendation:** Use Option A (content hash) for automatic deduplication.

---

### B. Centralized Canonical ID Module

**Create new file:** `/Users/alexkashkarian/Desktop/HighForce/app/core/canonical_ids.py`

```python
"""
Canonical ID Generation
Maps source-specific IDs to canonical document IDs for universal deduplication.

Each source type has different deduplication semantics:
- Emails (Gmail/Outlook): Dedupe by thread (conversation)
- Files (Drive): Dedupe by file_id (already canonical)
- Uploads: Dedupe by content hash
- QuickBooks: Dedupe by record_id (already canonical)
"""
import hashlib
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def get_canonical_id(
    source: str,
    normalized_data: Dict[str, Any],
    file_bytes: Optional[bytes] = None
) -> str:
    """
    Get canonical ID for any document source.

    This is the SINGLE source of truth for canonical ID generation.
    All ingestion paths MUST call this function.

    Args:
        source: Source identifier ('gmail', 'outlook', 'googledrive', 'quickbooks', 'upload')
        normalized_data: Normalized document dict (from provider normalizer)
        file_bytes: File bytes (for upload content hashing)

    Returns:
        Canonical ID string (stable across re-ingestion)

    Examples:
        # Gmail email
        canonical_id = get_canonical_id('gmail', {'thread_id': 'abc123', 'message_id': 'msg456'})
        # Returns: 'abc123' (thread_id)

        # Google Drive file
        canonical_id = get_canonical_id('googledrive', {'file_id': 'file789'})
        # Returns: 'file789' (file_id)

        # File upload
        canonical_id = get_canonical_id('upload', {'filename': 'report.pdf'}, file_bytes=b'...')
        # Returns: 'upload-a1b2c3d4' (content hash)
    """

    if source == 'gmail':
        return _get_gmail_canonical_id(normalized_data)

    elif source == 'outlook':
        return _get_outlook_canonical_id(normalized_data)

    elif source == 'googledrive':
        return _get_drive_canonical_id(normalized_data)

    elif source == 'quickbooks':
        return _get_quickbooks_canonical_id(normalized_data)

    elif source == 'upload':
        return _get_upload_canonical_id(normalized_data, file_bytes)

    else:
        # Unknown source: use source_id if available
        logger.warning(f"Unknown source '{source}', using source_id as canonical_id")
        return normalized_data.get('source_id') or normalized_data.get('id', 'unknown')


def _get_gmail_canonical_id(data: Dict[str, Any]) -> str:
    """Gmail: Use thread_id (conversation) as canonical."""
    thread_id = data.get('thread_id') or data.get('metadata', {}).get('thread_id')
    message_id = data.get('message_id')

    # Prefer thread_id, fallback to message_id
    if thread_id and str(thread_id).strip():
        return str(thread_id)

    if message_id:
        logger.warning(f"Gmail message missing thread_id, using message_id: {message_id[:20]}")
        return str(message_id)

    raise ValueError("Gmail message missing both thread_id and message_id")


def _get_outlook_canonical_id(data: Dict[str, Any]) -> str:
    """Outlook: Use thread_id (conversationId) as canonical."""
    thread_id = data.get('thread_id') or data.get('metadata', {}).get('thread_id')
    message_id = data.get('message_id')

    # Prefer thread_id, fallback to message_id
    if thread_id and str(thread_id).strip():
        return str(thread_id)

    if message_id:
        logger.warning(f"Outlook message missing thread_id, using message_id: {message_id[:20]}")
        return str(message_id)

    raise ValueError("Outlook message missing both thread_id and message_id")


def _get_drive_canonical_id(data: Dict[str, Any]) -> str:
    """Google Drive: Use file_id as canonical (already stable)."""
    file_id = data.get('file_id')

    if not file_id:
        raise ValueError("Google Drive file missing file_id")

    return str(file_id)


def _get_quickbooks_canonical_id(data: Dict[str, Any]) -> str:
    """QuickBooks: Use prefixed record ID (already canonical)."""
    source_id = data.get('source_id')

    if not source_id:
        raise ValueError("QuickBooks record missing source_id")

    # Already has format: "invoice-123", "bill-456", etc.
    return str(source_id)


def _get_upload_canonical_id(data: Dict[str, Any], file_bytes: Optional[bytes]) -> str:
    """File Upload: Use content hash as canonical."""
    if file_bytes:
        # Content-based deduplication
        file_hash = hashlib.sha256(file_bytes).hexdigest()
        return f"upload-{file_hash[:16]}"

    # Fallback: filename-based (less reliable)
    filename = data.get('filename') or data.get('source_id', 'unknown')
    logger.warning(f"Upload missing file_bytes, using filename: {filename}")
    return f"upload-{filename}"
```

---

### C. Attachment Handling Strategy

**Critical question:** How do attachments fit into canonical ID strategy?

**Current behavior:**
- Attachments get compound source_id: `{message_id}_{attachment_id}`
- Each attachment is separate document in Supabase
- Example: Email with 3 attachments = 4 documents total

**Problem with canonical IDs:**
If we use thread_id as canonical for parent email, what about attachments?

**Option 1: Attachments share parent's canonical ID** (NOT RECOMMENDED)
```python
# Email canonical ID: thread_abc
# Attachment 1 canonical ID: thread_abc  ← CONFLICT!
# Attachment 2 canonical ID: thread_abc  ← CONFLICT!
# Result: Only 1 document (can't distinguish attachments)
```

**Option 2: Attachments get compound canonical ID** (RECOMMENDED)
```python
# Email canonical ID: thread_abc
# Attachment 1 canonical ID: thread_abc_attach1
# Attachment 2 canonical ID: thread_abc_attach2
# Result: 3 documents (1 email + 2 attachments)
```

**Implementation:**
```python
def get_canonical_id_for_attachment(
    parent_canonical_id: str,
    attachment_id: str,
    source: str
) -> str:
    """
    Get canonical ID for email attachment.

    Attachments inherit parent's canonical ID with suffix:
    - Parent (email): thread_abc
    - Attachment 1: thread_abc_att_xyz123
    - Attachment 2: thread_abc_att_abc456

    This ensures:
    - Attachments dedupe with parent thread
    - Multiple attachments don't conflict
    - Re-sync updates attachments correctly

    Args:
        parent_canonical_id: Canonical ID of parent email (thread_id)
        attachment_id: Unique attachment identifier
        source: 'gmail' or 'outlook'

    Returns:
        Compound canonical ID
    """
    return f"{parent_canonical_id}_att_{attachment_id}"
```

**Usage in email_sync.py:**
```python
# Parent email ingestion
parent_result = await ingest_to_cortex(cortex_pipeline, normalized, supabase)
parent_canonical_id = get_canonical_id('gmail', normalized)

# Attachment ingestion
for attachment in attachments:
    attachment_canonical_id = get_canonical_id_for_attachment(
        parent_canonical_id,
        attachment['attachmentId'],
        source='gmail'
    )

    await ingest_document_universal(
        ...,
        source_id=attachment_canonical_id,  # ← Use compound ID
        ...
    )
```

---

## Phase 3: Implementation Roadmap

### Overview

This refactor touches **7 files** across 3 layers:
1. **Core layer:** New canonical ID module
2. **Sync layer:** Update all provider normalizers
3. **Ingestion layer:** Update universal ingestion to use canonical IDs

**Estimated effort:** 4-6 hours
**Risk level:** Medium (production data, no rollback needed)
**Testing strategy:** Incremental (source by source)

---

### Step 1: Create Core Canonical ID Module

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/core/canonical_ids.py`

**Action:** CREATE new file with:
- `get_canonical_id()` - Main entry point
- `_get_gmail_canonical_id()` - Gmail thread logic
- `_get_outlook_canonical_id()` - Outlook conversation logic
- `_get_drive_canonical_id()` - Drive file logic (passthrough)
- `_get_quickbooks_canonical_id()` - QB record logic (passthrough)
- `_get_upload_canonical_id()` - Upload hash logic
- `get_canonical_id_for_attachment()` - Attachment compound ID

**Lines:** ~150 lines
**Dependencies:** None (pure Python, uses hashlib)
**Testing:** Unit tests for each source type

---

### Step 2: Update Gmail Provider

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/providers/gmail.py`

**Changes:**
```python
# Add import at top
from app.core.canonical_ids import get_canonical_id

# In normalize_gmail_message() function
# BEFORE (line ~80):
normalized = {
    "tenant_id": tenant_id,
    "source": "gmail",
    "message_id": email_id,  # ← Individual message ID
    ...
}

# AFTER:
normalized = {
    "tenant_id": tenant_id,
    "source": "gmail",
    "message_id": email_id,  # ← Keep for reference
    "canonical_id": get_canonical_id('gmail', {'thread_id': thread_id, 'message_id': email_id}),
    ...
}
```

**Lines changed:** 2 lines (import + 1 field addition)
**Backward compatible:** Yes (adds field, doesn't remove)

---

### Step 3: Update Outlook Provider

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/providers/outlook.py`

**Changes:**
```python
# Add import at top
from app.core.canonical_ids import get_canonical_id

# In normalize_outlook_message() function
# BEFORE (line ~80):
normalized = {
    "tenant_id": tenant_id,
    "source": "outlook",
    "message_id": email_id,  # ← Individual message ID
    ...
}

# AFTER:
normalized = {
    "tenant_id": tenant_id,
    "source": "outlook",
    "message_id": email_id,  # ← Keep for reference
    "canonical_id": get_canonical_id('outlook', {'thread_id': thread_id, 'message_id': email_id}),
    ...
}
```

**Lines changed:** 2 lines (import + 1 field addition)

---

### Step 4: Update Drive Provider (No Changes Needed)

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/providers/google_drive.py`

**Status:** ✅ Already using canonical IDs (file_id)

**Verification only:** Ensure `normalize_drive_file()` returns `file_id` field

---

### Step 5: Update QuickBooks Provider (No Changes Needed)

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/orchestration/quickbooks_sync.py`

**Status:** ✅ Already using canonical IDs (prefixed record IDs)

**Verification only:** Ensure normalizers return `source_id` with format `{type}-{id}`

---

### Step 6: Update Upload Route

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/api/v1/routes/upload.py`

**Changes:**
```python
# Add import at top (line ~23)
from app.core.canonical_ids import get_canonical_id

# In upload_file() function
# BEFORE (line ~160):
result = await ingest_document_universal(
    ...,
    source_id=safe_filename,  # ← Filename-based
    ...
)

# AFTER (line ~160):
canonical_id = get_canonical_id(
    'upload',
    {'filename': safe_filename},
    file_bytes=file_bytes
)

result = await ingest_document_universal(
    ...,
    source_id=canonical_id,  # ← Content hash based
    ...
)
```

**Lines changed:** 8 lines (import + canonical ID generation)
**Applies to:** Both `upload_file()` and `upload_multiple_files()` endpoints

---

### Step 7: Update Universal Ingestion (Critical Change)

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/services/preprocessing/normalizer.py`

**Change 1: Accept canonical_id parameter**
```python
# Function signature (line 38)
# BEFORE:
async def ingest_document_universal(
    supabase: Client,
    cortex_pipeline: UniversalIngestionPipeline,
    tenant_id: str,
    source: str,
    source_id: str,  # ← Currently: message_id, file_id, filename
    ...
):

# AFTER:
async def ingest_document_universal(
    supabase: Client,
    cortex_pipeline: UniversalIngestionPipeline,
    tenant_id: str,
    source: str,
    source_id: str,  # ← Now: canonical ID (thread_id, file_id, hash)
    original_source_id: Optional[str] = None,  # ← NEW: preserve original ID
    ...
):
```

**Change 2: Update metadata to preserve original ID**
```python
# Metadata construction (line ~270)
# BEFORE:
document_row = {
    'tenant_id': tenant_id,
    'source': source,
    'source_id': source_id,
    ...
    'metadata': metadata,
}

# AFTER:
# Preserve original source_id in metadata for reference
if original_source_id:
    if metadata is None:
        metadata = {}
    metadata['original_source_id'] = original_source_id

document_row = {
    'tenant_id': tenant_id,
    'source': source,
    'source_id': source_id,  # ← Now canonical ID
    ...
    'metadata': metadata,  # ← Contains original_source_id
}
```

**Change 3: Remove thread deduplication logic**
```python
# DELETE lines 345-422 (entire thread dedup section)
# This includes:
# - Thread ID extraction
# - Qdrant query for existing threads
# - Timestamp comparison
# - Qdrant deletion
# - All error handling

# REASON: No longer needed! Canonical ID prevents duplicates at upsert time.
```

**Lines changed:**
- Add 1 parameter: +1 line
- Add metadata preservation: +5 lines
- Remove thread dedup: -78 lines
- **Net change:** -72 lines (simplified!)

---

### Step 8: Update Email Sync Orchestrators

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/persistence.py`

**Changes in `ingest_to_cortex()` function:**

```python
# Add import (line 13)
from app.core.canonical_ids import get_canonical_id

# Update universal ingestion call (line 137)
# BEFORE:
result = await ingest_document_universal(
    supabase=supabase,
    cortex_pipeline=cortex_pipeline,
    tenant_id=email.get("tenant_id"),
    source=email.get("source", "gmail"),
    source_id=email.get("message_id"),  # ← Individual message
    ...
)

# AFTER:
canonical_id = get_canonical_id(
    email.get("source", "gmail"),
    email
)

result = await ingest_document_universal(
    supabase=supabase,
    cortex_pipeline=cortex_pipeline,
    tenant_id=email.get("tenant_id"),
    source=email.get("source", "gmail"),
    source_id=canonical_id,  # ← Thread ID
    original_source_id=email.get("message_id"),  # ← Preserve original
    ...
)
```

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/orchestration/email_sync.py`

**Changes for Gmail attachments (line 412-430):**
```python
# Add import
from app.core.canonical_ids import get_canonical_id, get_canonical_id_for_attachment

# In attachment processing loop
# BEFORE:
source_id=f"{normalized['message_id']}_{attachment_id}",

# AFTER:
parent_canonical = get_canonical_id('gmail', normalized)
attachment_canonical = get_canonical_id_for_attachment(
    parent_canonical,
    attachment_id,
    'gmail'
)
...
source_id=attachment_canonical,
original_source_id=f"{normalized['message_id']}_{attachment_id}",
```

**Changes for Outlook attachments (line 181-204):**
```python
# Same pattern as Gmail
parent_canonical = get_canonical_id('outlook', normalized)
attachment_canonical = get_canonical_id_for_attachment(
    parent_canonical,
    attachment_id,
    'outlook'
)
...
source_id=attachment_canonical,
original_source_id=f"{normalized['message_id']}_{attachment_id}",
```

---

### Step 9: Update Drive Sync (Minimal Changes)

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/orchestration/drive_sync.py`

**Change:** Verify canonical ID usage (should already work)

```python
# Line 292 - Already uses file_id, which IS canonical
result = await ingest_document_universal(
    ...,
    source_id=normalized["file_id"],  # ← Already canonical! No change needed
    ...
)
```

**Action:** No code changes, just add comment for clarity:
```python
# Line 292
source_id=normalized["file_id"],  # Canonical ID (stable Drive file ID)
```

---

### Step 10: Update QuickBooks Sync (Minimal Changes)

**File:** `/Users/alexkashkarian/Desktop/HighForce/app/services/sync/orchestration/quickbooks_sync.py`

**Change:** Verify canonical ID usage (should already work)

```python
# Lines 286, 315, 342, 369 - Already use prefixed IDs
await ingest_document_universal(
    ...,
    source_id=f"invoice-{invoice_id}",  # ← Already canonical! No change needed
    ...
)
```

**Action:** No code changes, just add comments for clarity

---

### Step 11: Database Migration (Optional)

**Decision point:** Do we need to migrate existing data?

**Option A: No migration (Recommended)**
- Let old data exist with old source_ids (message_id)
- New syncs use canonical source_ids (thread_id)
- Over time, re-syncs update to canonical IDs
- Pro: Safe, no downtime
- Con: Mixed data during transition period

**Option B: Backfill migration**
- Create script to update existing documents
- Change source_id from message_id → thread_id
- Requires reading metadata.thread_id for each doc
- Pro: Clean data immediately
- Con: Risky, could cause downtime

**Recommendation:** Option A (no migration)

**Reasoning:**
1. Unique constraint handles both old and new formats
2. Re-sync naturally migrates data
3. No risk of data loss
4. Can run cleanup script later if needed

**If migration desired later:**
```sql
-- Create migration script: update_to_canonical_ids.sql
-- Step 1: Add temp column for new canonical ID
ALTER TABLE documents ADD COLUMN canonical_source_id TEXT;

-- Step 2: Populate for Gmail (use thread_id from metadata)
UPDATE documents
SET canonical_source_id = metadata->>'thread_id'
WHERE source = 'gmail'
  AND metadata->>'thread_id' IS NOT NULL
  AND metadata->>'thread_id' != '';

-- Step 3: Fallback to message_id if no thread_id
UPDATE documents
SET canonical_source_id = source_id
WHERE source = 'gmail'
  AND canonical_source_id IS NULL;

-- Step 4: Same for Outlook
UPDATE documents
SET canonical_source_id = metadata->>'thread_id'
WHERE source = 'outlook'
  AND metadata->>'thread_id' IS NOT NULL;

-- Step 5: Other sources (already canonical)
UPDATE documents
SET canonical_source_id = source_id
WHERE source IN ('googledrive', 'quickbooks', 'upload')
  AND canonical_source_id IS NULL;

-- Step 6: Verify all rows updated
SELECT COUNT(*) FROM documents WHERE canonical_source_id IS NULL;
-- Should be 0

-- Step 7: Drop old constraint, add new one
ALTER TABLE documents DROP CONSTRAINT documents_tenant_id_source_source_id_key;
ALTER TABLE documents ADD CONSTRAINT documents_tenant_id_source_canonical_key
  UNIQUE(tenant_id, source, canonical_source_id);

-- Step 8: Rename column
ALTER TABLE documents RENAME COLUMN source_id TO old_source_id;
ALTER TABLE documents RENAME COLUMN canonical_source_id TO source_id;
```

**DO NOT RUN THIS NOW** - Only if clean migration required

---

### Step 12: Remove Thread Dedup Infrastructure (Cleanup)

**Files to modify/remove:**

1. **Remove thread dedup script:**
   - File: `/Users/alexkashkarian/Desktop/HighForce/create_qdrant_thread_index.py`
   - Action: DELETE (no longer needed)

2. **Remove thread indexes from auto-creation:**
   - File: `/Users/alexkashkarian/Desktop/HighForce/app/services/rag/indexes.py`
   - Action: NO CHANGE (indexes don't hurt, might be useful for other queries)

3. **Update documentation:**
   - File: `/Users/alexkashkarian/Desktop/HighForce/docs/guides/PRODUCTION_DEDUPLICATION_STRATEGY.md`
   - Action: Update to reflect new canonical ID strategy

---

### Step 13: Testing Strategy (Critical!)

Test each source type independently before moving to next:

#### Test 1: Gmail Thread Deduplication
```bash
# Terminal 1: Tail logs
tail -f logs/app.log | grep -i "thread\|canonical\|duplicate"

# Terminal 2: Trigger Gmail sync
curl -X POST http://localhost:8000/api/v1/sync \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"sync_type": "gmail"}'

# Expected behavior:
# 1. First sync: Creates documents with canonical_id = thread_id
# 2. Second sync (same emails): UPSERTS (updates existing)
# 3. No "Deleted X older thread chunks" logs (removed!)
# 4. Verify Supabase: Count documents with source='gmail'
#    Should be: number of unique threads, not total messages
```

**SQL verification:**
```sql
-- Before: 601 documents (many messages per thread)
-- After: ~200 documents (one per thread)
SELECT COUNT(*), COUNT(DISTINCT metadata->>'thread_id')
FROM documents
WHERE source = 'gmail';

-- Should show: COUNT = COUNT(DISTINCT thread_id)
```

#### Test 2: Outlook Thread Deduplication
```bash
# Same pattern as Gmail
curl -X POST http://localhost:8000/api/v1/sync \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"sync_type": "outlook"}'
```

#### Test 3: Drive Files (Should be unchanged)
```bash
curl -X POST http://localhost:8000/api/v1/sync \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -d '{"sync_type": "drive"}'

# Expected: Works exactly as before (already canonical)
```

#### Test 4: File Upload Deduplication
```bash
# Upload same file twice
curl -X POST http://localhost:8000/api/v1/upload/file \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@test.pdf"

# Upload again (same content)
curl -X POST http://localhost:8000/api/v1/upload/file \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -F "file=@test.pdf"

# Expected: Second upload UPSERTS (updates first)
# Verify: Only 1 document in Supabase for this file
```

#### Test 5: Attachment Deduplication
```bash
# Sync email with attachments
# Then sync again (should update, not duplicate)

# Verify Supabase:
SELECT source_id, title, document_type
FROM documents
WHERE source = 'gmail'
  AND metadata->>'thread_id' = '<test_thread_id>'
ORDER BY document_type;

# Expected:
# source_id            | title                    | document_type
# ---------------------|--------------------------|---------------
# thread_abc           | Email subject            | email
# thread_abc_att_001   | attachment1.pdf          | attachment
# thread_abc_att_002   | attachment2.xlsx         | attachment
```

#### Test 6: Qdrant Verification
```python
# Python script to verify Qdrant deduplication
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

# Count points per thread
results = client.scroll(
    collection_name="cortex_collection",
    scroll_filter=Filter(
        must=[
            FieldCondition(key="source", match=MatchValue(value="gmail")),
            FieldCondition(key="tenant_id", match=MatchValue(value="<your_tenant>"))
        ]
    ),
    limit=1000,
    with_payload=True
)

# Group by thread_id
from collections import Counter
thread_counts = Counter(point.payload.get('thread_id') for point, _ in results)

print(f"Unique threads: {len(thread_counts)}")
print(f"Avg chunks per thread: {sum(thread_counts.values()) / len(thread_counts)}")

# Expected: Each thread appears once (not multiple times)
# Old behavior: Same thread_id appears multiple times (one per email)
# New behavior: Same thread_id appears once (latest email only)
```

---

## Phase 4: Risk Analysis & Mitigation

### High Risks

#### Risk 1: Data Loss from Unique Constraint
**Scenario:** Thread with 5 emails → After refactor → Only latest email preserved

**Impact:** HIGH - User loses historical emails in Supabase

**Likelihood:** HIGH - This is by design

**Mitigation:**
1. **DECISION REQUIRED:** Do we want to preserve all emails or just latest?
   - Option A: Preserve all → Don't use thread_id as canonical (keep message_id)
   - Option B: Latest only → Use thread_id (Gmail conversation view model)

2. **Recommended:** Latest only (Option B) because:
   - Matches Gmail's conversation view UX
   - Qdrant already uses this model (thread dedup)
   - Reduces storage costs (67% reduction: 601 → ~200 docs)
   - Email content includes history (quoted text)

3. **If preservation needed:** Add email archive table
   ```sql
   CREATE TABLE email_archive (
       id BIGSERIAL PRIMARY KEY,
       tenant_id TEXT,
       message_id TEXT UNIQUE,
       thread_id TEXT,
       content TEXT,
       archived_at TIMESTAMPTZ DEFAULT NOW()
   );
   ```

**Decision:** ⚠️ REQUIRED BEFORE IMPLEMENTATION

---

#### Risk 2: Attachment Loss in Thread Merge
**Scenario:**
- Email 1 in thread: Has attachment A
- Email 2 (reply): Has attachment B
- After refactor: Email 2 overwrites Email 1
- Result: Attachment A lost?

**Impact:** HIGH - Users lose attachments from earlier emails

**Likelihood:** MEDIUM - Depends on attachment handling

**Mitigation:**
1. **Attachments are separate documents** (not children in JSON)
   - Each attachment has own row in documents table
   - source_id: `{thread_id}_att_{attachment_id}`
   - parent_document_id: Links to parent email

2. **When email updates (upsert):**
   - Attachments remain separate (not affected by parent upsert)
   - New attachments added with new compound IDs
   - Old attachments remain (orphaned if parent changes)

3. **Orphaned attachment cleanup** (optional):
   ```sql
   -- Find orphaned attachments (parent no longer exists)
   SELECT a.id, a.source_id, a.title
   FROM documents a
   WHERE a.document_type = 'attachment'
     AND a.parent_document_id IS NOT NULL
     AND NOT EXISTS (
         SELECT 1 FROM documents p
         WHERE p.id = a.parent_document_id
     );
   ```

**Status:** ✅ MITIGATED - Attachments are independent documents

---

#### Risk 3: Race Condition in Concurrent Sync
**Scenario:**
- Two sync jobs fetch same thread simultaneously
- Both try to upsert with same canonical_id
- PostgreSQL handles with SERIALIZABLE isolation

**Impact:** LOW - PostgreSQL ensures consistency

**Likelihood:** LOW - Syncs are typically sequential

**Mitigation:**
1. PostgreSQL's unique constraint handles race conditions atomically
2. Last write wins (determined by transaction commit order)
3. No data corruption possible (database-level guarantee)

**Status:** ✅ SAFE - Database handles this

---

### Medium Risks

#### Risk 4: Missing thread_id Fallback
**Scenario:** Email has empty or null thread_id

**Impact:** MEDIUM - Falls back to message_id (no deduplication)

**Likelihood:** LOW - Most emails have thread_id

**Mitigation:**
1. Canonical ID function has fallback logic (see design)
2. Logs warning when falling back to message_id
3. Monitor logs for frequency of fallback

```python
if not thread_id or not thread_id.strip():
    logger.warning(f"Email missing thread_id, using message_id: {message_id}")
    return message_id
```

**Status:** ✅ HANDLED in design

---

#### Risk 5: QuickBooks Record Updates
**Scenario:** QuickBooks invoice updated (amount changes)

**Impact:** MEDIUM - Old version lost (upsert behavior)

**Likelihood:** MEDIUM - Common business operation

**Mitigation:**
1. **By design:** Upsert updates to latest version (correct behavior)
2. QuickBooks API provides versioning (`doc_number`, `updated_at`)
3. Store `source_modified_at` for audit trail
4. If version history needed, use QuickBooks audit log API

**Status:** ✅ ACCEPTABLE - Business requirement (latest version)

---

### Low Risks

#### Risk 6: Canonical ID Collision Across Sources
**Scenario:** Gmail thread_id matches Outlook conversationId

**Impact:** LOW - Unique constraint includes source field

**Likelihood:** VERY LOW - IDs are globally unique

**Mitigation:**
- Unique constraint: `(tenant_id, source, source_id)`
- Source field prevents cross-source collisions
- Example:
  ```sql
  -- These don't conflict (different source)
  ('user1', 'gmail', 'thread_abc', ...)
  ('user1', 'outlook', 'thread_abc', ...)
  ```

**Status:** ✅ SAFE - Schema design prevents this

---

#### Risk 7: Upload Content Hash Collision
**Scenario:** Two different files generate same SHA256 hash

**Impact:** LOW - Second file overwrites first

**Likelihood:** EXTREMELY LOW - SHA256 collision probability: 1 in 2^256

**Mitigation:**
1. SHA256 is cryptographically secure (collision-resistant)
2. If paranoid: Use SHA256 + file size compound key
3. Real risk: Intentional upload of same file (desired deduplication)

**Status:** ✅ ACCEPTABLE - Collision probability negligible

---

#### Risk 8: Performance Degradation
**Scenario:** Removing thread dedup increases Qdrant storage

**Impact:** LOW - Actually improves performance

**Likelihood:** N/A - Refactor reduces operations

**Mitigation:**
- **Before:** Ingest all emails, then delete old ones (wasteful)
- **After:** Only ingest latest (single upsert operation)
- **Result:** Faster ingestion, less storage, fewer API calls

**Performance comparison:**
```
Thread with 5 emails (Before):
1. Ingest email 1 → 12 Qdrant points
2. Ingest email 2 → 12 points → Delete email 1 (12 deletions)
3. Ingest email 3 → 12 points → Delete emails 1&2 (24 deletions)
4. Ingest email 4 → 12 points → Delete emails 1-3 (36 deletions)
5. Ingest email 5 → 12 points → Delete emails 1-4 (48 deletions)
Total: 60 ingestions + 120 deletions = 180 operations

Thread with 5 emails (After):
1. Upsert (skip, exists in Supabase)
2. Upsert (skip, exists)
3. Upsert (skip, exists)
4. Upsert (skip, exists)
5. Upsert (update) → 12 Qdrant points (replaces old chunks)
Total: 12 ingestions = 12 operations

Speedup: 180 / 12 = 15x faster!
```

**Status:** ✅ IMPROVEMENT - Performance benefit

---

## Phase 5: Rollback Plan

### If Things Go Wrong

**Scenario:** Refactor causes issues in production

**Rollback options:**

#### Option 1: Code Rollback (Immediate)
```bash
# Revert to previous Git commit
git revert <refactor_commit_hash>
git push origin main

# Redeploy
# (Render.com auto-deploys on push)
```

**Impact:** System reverts to old behavior
**Data impact:** None (data already written remains)
**Time:** 5 minutes

---

#### Option 2: Database Rollback (If migration ran)
```sql
-- Only needed if migration script was run
-- Reverses column rename

ALTER TABLE documents RENAME COLUMN source_id TO canonical_source_id;
ALTER TABLE documents RENAME COLUMN old_source_id TO source_id;

ALTER TABLE documents DROP CONSTRAINT documents_tenant_id_source_canonical_key;
ALTER TABLE documents ADD CONSTRAINT documents_tenant_id_source_source_id_key
  UNIQUE(tenant_id, source, source_id);
```

**Impact:** Restores old schema
**Data impact:** Canonical IDs become metadata
**Time:** 1 minute

---

#### Option 3: Feature Flag (Preventive)
**Recommended for safety-critical deployment**

```python
# app/core/config.py
USE_CANONICAL_IDS = os.getenv("USE_CANONICAL_IDS", "false").lower() == "true"

# app/services/preprocessing/normalizer.py
if settings.USE_CANONICAL_IDS:
    canonical_id = get_canonical_id(source, normalized_data)
    actual_source_id = canonical_id
else:
    # Old behavior
    actual_source_id = source_id

document_row = {
    'source_id': actual_source_id,
    ...
}
```

**Deployment:**
1. Deploy code with feature flag OFF
2. Test in production with flag OFF
3. Enable flag for single tenant: `USE_CANONICAL_IDS=true` (restart required)
4. Monitor for issues
5. Enable for all tenants if successful

**Rollback:** Set `USE_CANONICAL_IDS=false`, restart

---

## Summary & Recommendations

### Key Findings

1. **Well-architected ingestion:** All 5 sources converge on `ingest_document_universal()` - perfect for refactor
2. **Thread dedup is wasteful:** 180 operations per thread vs 12 with canonical IDs
3. **Clean separation:** Canonical ID logic can be isolated in single module
4. **Risk is manageable:** Mostly data model changes, no algorithm complexity
5. **Performance improvement:** 15x faster ingestion, 67% storage reduction

### Recommendations

#### Must Do Before Starting
- ☐ **DECISION:** Preserve all emails or latest-only? (Affects data model)
- ☐ **DECISION:** Content hash uploads or UUID uploads? (Affects deduplication)
- ☐ **BACKUP:** Full database backup before refactor
- ☐ **STAGING:** Test on non-production tenant first

#### Implementation Order (Recommended)
1. ✅ Create canonical ID module (isolated, testable)
2. ✅ Update Gmail provider (highest volume, test first)
3. ✅ Update Outlook provider (similar to Gmail)
4. ✅ Update universal ingestion (remove thread dedup)
5. ✅ Test Gmail + Outlook thoroughly
6. ✅ Update Upload route (low volume, lower risk)
7. ✅ Verify Drive + QuickBooks (should need no changes)
8. ✅ Monitor production for 24 hours
9. ✅ Remove old thread dedup scripts (cleanup)

#### Deployment Strategy
- **Option A (Aggressive):** Deploy all at once, monitor closely
- **Option B (Safe):** Use feature flag, enable per-tenant
- **Option C (Hybrid):** Deploy to staging tenant first, then production

**Recommendation:** Option B (feature flag) for zero-downtime rollback capability

#### Success Metrics
- **Supabase:** Document count drops from 601 → ~200 (67% reduction)
- **Qdrant:** No change in point count (already deduplicated)
- **Logs:** No "Deleted X older thread chunks" messages
- **Performance:** Sync speed increases (fewer operations)
- **Errors:** No duplicate key constraint violations

#### Timeline Estimate
- Implementation: 4-6 hours
- Testing: 2-3 hours
- Deployment: 1 hour
- Monitoring: 24 hours
- **Total:** 2-3 days for complete rollout

---

## Next Steps

1. **Review this document with team**
2. **Make critical decisions** (data preservation model)
3. **Create feature branch:** `feature/canonical-id-deduplication`
4. **Implement Step 1** (canonical ID module)
5. **Write unit tests** for canonical ID functions
6. **Implement Steps 2-6** (provider updates)
7. **Test in local environment**
8. **Deploy to staging tenant**
9. **Monitor for 24 hours**
10. **Deploy to production**

---

## Appendix: File Change Summary

| File | Action | Lines Changed | Risk |
|------|--------|---------------|------|
| `app/core/canonical_ids.py` | CREATE | +150 | LOW |
| `app/services/sync/providers/gmail.py` | MODIFY | +2 | LOW |
| `app/services/sync/providers/outlook.py` | MODIFY | +2 | LOW |
| `app/services/sync/providers/google_drive.py` | VERIFY | 0 | NONE |
| `app/services/sync/orchestration/quickbooks_sync.py` | VERIFY | 0 | NONE |
| `app/api/v1/routes/upload.py` | MODIFY | +8 | LOW |
| `app/services/preprocessing/normalizer.py` | MODIFY | -72 | MEDIUM |
| `app/services/sync/persistence.py` | MODIFY | +10 | LOW |
| `app/services/sync/orchestration/email_sync.py` | MODIFY | +20 | MEDIUM |
| `create_qdrant_thread_index.py` | DELETE | -all | LOW |
| **TOTAL** | | **+120 / -72 = +48 net** | **MEDIUM** |

---

**Document Status:** ✅ COMPLETE - Ready for implementation
**Last Updated:** 2025-11-14
**Author:** Claude (Discovery Analysis)
**Approver:** [Team Lead]
