# QuickBooks Integration Architecture - The Full Picture

## 🧠 Understanding Your Current System

### How Data Flows Today (Gmail/Outlook/Drive)

```
┌──────────────────────────────────────────────────────────────────────┐
│ 1. SYNC WORKER (Background Job via Dramatiq)                         │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  sync_gmail_task() or sync_outlook_task() runs:                     │
│                                                                       │
│  ├─ Fetch emails from Nango unified API                             │
│  ├─ Spam filter (OpenAI classifier)                                  │
│  └─ For each email:                                                  │
│      └─ ingest_to_cortex() →                                        │
│          └─ ingest_document_universal()                             │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ 2. UNIVERSAL INGESTION (ingest_document_universal)                   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Step 1: Extract text (if file → parse with OCR)                    │
│  Step 2: Check duplicates (SHA-256 hash)                             │
│  Step 3: Save to Supabase `documents` table ← SOURCE OF TRUTH       │
│  Step 4: Call UniversalIngestionPipeline.ingest_document()          │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ 3. LLAMAINDEX PIPELINE (UniversalIngestionPipeline)                  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌────────────────────────────────────────────────────────┐         │
│  │ A. VECTOR STORAGE (Qdrant)                            │         │
│  ├────────────────────────────────────────────────────────┤         │
│  │  • Chunk text into ~1000 char pieces                  │         │
│  │  • Generate embeddings (OpenAI text-embedding-3-small)│         │
│  │  • Store in Qdrant with metadata:                     │         │
│  │    - document_id (links back to Supabase)            │         │
│  │    - created_at_timestamp (for recency filtering)    │         │
│  │    - source, document_type, title, etc.              │         │
│  └────────────────────────────────────────────────────────┘         │
│                                                                       │
│  ┌────────────────────────────────────────────────────────┐         │
│  │ B. KNOWLEDGE GRAPH (Neo4j)                            │         │
│  ├────────────────────────────────────────────────────────┤         │
│  │  • Extract entities with SchemaLLMPathExtractor       │         │
│  │    (GPT-4o-mini with your custom schema)             │         │
│  │                                                        │         │
│  │  • Entities extracted:                                │         │
│  │    PERSON, COMPANY, ROLE, DEAL, PAYMENT,             │         │
│  │    MATERIAL, CERTIFICATION                            │         │
│  │    (loaded from master Supabase company_schemas)     │         │
│  │                                                        │         │
│  │  • Creates nodes in Neo4j:                            │         │
│  │    (Sarah Chen:PERSON)                                │         │
│  │    (Acme Corp:COMPANY)                                │         │
│  │    (PO-2024-183:DEAL)                                 │         │
│  │    (Polycarbonate PC-1000:MATERIAL)                   │         │
│  │                                                        │         │
│  │  • Creates relationships:                             │         │
│  │    (Sarah)-[WORKS_FOR]->(Acme)                       │         │
│  │    (Acme)-[PLACED]->(PO-2024-183)                    │         │
│  │    (PO-2024-183)-[INCLUDES]->(Polycarbonate)         │         │
│  └────────────────────────────────────────────────────────┘         │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│ 4. RESULT: Data is Searchable                                        │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ✅ Semantic search via Qdrant (vector similarity)                   │
│  ✅ Graph queries via Neo4j (relationships)                          │
│  ✅ Hybrid search combines both for best results                     │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🎯 How QuickBooks Should Work (Two Approaches)

### Approach A: Structured Financial Data (Recommended)

**QuickBooks data is STRUCTURED (not unstructured text like emails)**

Instead of ingesting into knowledge graph, store in Supabase and use for dashboard metrics:

```
┌──────────────────────────────────────────────────────────────────────┐
│ QUICKBOOKS SYNC FLOW (Structured Data Approach)                      │
└──────────────────────────────────────────────────────────────────────┘

1️⃣ NIGHTLY SYNC JOB (Dramatiq background task)
   └─ fetch_all_quickbooks_data() → Get invoices, bills, customers, etc.

2️⃣ STORE IN SUPABASE (New table: quickbooks_cache)
   └─ Cache entire QB response as JSONB
   └─ Timestamp for freshness tracking

3️⃣ CEO DASHBOARD READS FROM CACHE
   └─ GET /dashboard/ceo → Fetch cached QB data
   └─ Calculate metrics (revenue, expenses, etc.)
   └─ Search CORTEX knowledge graph for context

4️⃣ RAG ENHANCEMENT (The Magic!)
   └─ "Revenue: $47,500" ← From QuickBooks cache
   └─ Search Qdrant: "invoices paid this week"
   └─ Find: "Acme Corp paid Invoice #892 ($12.5k)" ← From emails!
   └─ Link them together in dashboard
```

**Why This Approach:**
- ✅ QB data is already structured (JSON)
- ✅ Metrics calculated from source data (accurate)
- ✅ Fast dashboard load (cached data)
- ✅ RAG adds context from emails/docs
- ✅ No need to extract entities from structured data

**Schema:**
```sql
CREATE TABLE quickbooks_cache (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  data_type TEXT NOT NULL,  -- 'full_dump', 'summary'
  data JSONB NOT NULL,       -- Entire QB response
  fetched_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, data_type)
);

CREATE INDEX idx_qb_cache_tenant ON quickbooks_cache(tenant_id);
```

---

### Approach B: Hybrid (QB + Knowledge Graph)

**If you want QB entities in Neo4j for graph queries:**

```
┌──────────────────────────────────────────────────────────────────────┐
│ QUICKBOOKS SYNC FLOW (Knowledge Graph Approach)                      │
└──────────────────────────────────────────────────────────────────────┘

1️⃣ NIGHTLY SYNC JOB
   └─ fetch_all_quickbooks_data()

2️⃣ FOR EACH INVOICE/BILL/PAYMENT:
   └─ Convert to "document" format
   └─ Call ingest_document_universal()

3️⃣ UNIVERSAL INGESTION PIPELINE:
   ├─ Save to documents table
   └─ Extract entities:
       • CUSTOMER → COMPANY node
       • INVOICE → DEAL node
       • PAYMENT → PAYMENT node

4️⃣ NEO4J KNOWLEDGE GRAPH:
   └─ (Acme Corp:COMPANY)-[OWES]->(Invoice #892:DEAL)
   └─ (Invoice #892)-[PAID_BY]->(Payment #123:PAYMENT)

5️⃣ GRAPH QUERIES:
   └─ "Who owes us money?" → Find unpaid invoices in graph
   └─ "Show me all deals with Acme Corp" → Graph traversal
```

**Why This Approach:**
- ✅ QB entities in knowledge graph
- ✅ Can query relationships ("Which customers haven't paid?")
- ✅ Unified search across emails + QB data
- ❌ More complex (need to format QB data as documents)
- ❌ Slower sync (entity extraction on every invoice)

---

## 🚀 Recommended Implementation (Approach A + RAG)

### Step 1: Create QuickBooks Cache Table

```sql
-- In Supabase
CREATE TABLE quickbooks_cache (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  data_type TEXT NOT NULL,  -- 'invoices', 'bills', 'summary', 'full'
  data JSONB NOT NULL,
  fetched_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, data_type)
);

CREATE INDEX idx_qb_cache_tenant ON quickbooks_cache(tenant_id);
CREATE INDEX idx_qb_cache_fetched_at ON quickbooks_cache(fetched_at DESC);
```

### Step 2: Create Sync Worker

```python
# app/services/background/tasks.py

@dramatiq.actor(max_retries=3)
def sync_quickbooks_task(user_id: str, job_id: str):
    """
    Background job for QuickBooks sync.
    Fetches ALL QB data and caches in Supabase.
    """
    logger.info(f"🚀 Starting QuickBooks sync job {job_id} for user {user_id}")

    http_client, supabase, _ = get_sync_dependencies()

    try:
        # Update job status
        supabase.table("sync_jobs").update({
            "status": "running",
            "started_at": "now()"
        }).eq("id", job_id).execute()

        # Fetch ALL QuickBooks data
        from app.services.integrations.quickbooks import fetch_all_quickbooks_data

        result = asyncio.run(fetch_all_quickbooks_data(
            http_client,
            user_id  # connection_id = user_id
        ))

        # Cache in Supabase
        supabase.table("quickbooks_cache").upsert({
            "tenant_id": user_id,
            "data_type": "full",
            "data": result,
            "fetched_at": "now()"
        }, on_conflict="tenant_id,data_type").execute()

        # Update job status
        supabase.table("sync_jobs").update({
            "status": "completed",
            "completed_at": "now()",
            "result": {
                "invoices_count": len(result.get("invoices", [])),
                "customers_count": len(result.get("customers", [])),
                "cached": True
            }
        }).eq("id", job_id).execute()

        logger.info(f"✅ QuickBooks sync job {job_id} complete")
        return result

    except Exception as e:
        logger.error(f"❌ QuickBooks sync job {job_id} failed: {e}")

        supabase.table("sync_jobs").update({
            "status": "failed",
            "completed_at": "now()",
            "error_message": str(e)
        }).eq("id", job_id).execute()

        raise
```

### Step 3: Create CEO Dashboard Endpoint

```python
# app/api/v1/routes/dashboard.py

@router.get("/dashboard/ceo")
async def get_ceo_dashboard(
    http_client: httpx.AsyncClient = Depends(get_http_client),
    supabase: Client = Depends(get_supabase),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    CEO dashboard with QuickBooks metrics + RAG context.

    Combines:
    1. Cached QuickBooks data (fast metrics)
    2. CORTEX RAG search (contextual insights)
    """
    user_id = current_user.get("id") or current_user.get("sub")

    # 1. Get cached QuickBooks data
    qb_cache = supabase.table("quickbooks_cache")\
        .select("data, fetched_at")\
        .eq("tenant_id", user_id)\
        .eq("data_type", "full")\
        .single()\
        .execute()

    if not qb_cache.data:
        raise HTTPException(status_code=404, detail="QuickBooks not synced yet")

    qb_data = qb_cache.data["data"]

    # 2. Calculate metrics from QB data
    invoices = qb_data.get("invoices", [])
    revenue = sum(float(inv.get("total", 0) or 0) for inv in invoices if float(inv.get("balance", 0) or 0) == 0)

    # 3. Search CORTEX for context (RAG!)
    from app.services.ingestion.llamaindex.query_engine import HybridQueryEngine

    query_engine = HybridQueryEngine()

    # Find emails about recent invoices
    context = await query_engine.query(
        "What invoices were paid this week? Show customer names and amounts.",
        filters={"source": ["gmail", "outlook"]}
    )

    return {
        "success": True,
        "quickbooks": {
            "revenue": revenue,
            "fetched_at": qb_cache.data["fetched_at"]
        },
        "context": {
            "recent_payments": context.response,
            "sources": [...]
        }
    }
```

### Step 4: Nightly Cron Job

Set up Render cron job:
```bash
# Every night at midnight
0 0 * * * python -m app.services.background.sync_quickbooks_cron
```

---

## 💡 The Beautiful Part

### Widget Example: Revenue with Context

```
┌────────────────────────────────────────────────────────┐
│ 💰 Revenue This Week: $47,500 ▲ 18%                   │
├────────────────────────────────────────────────────────┤
│                                                         │
│ From QuickBooks:                                       │
│ • 15 invoices paid                                     │
│ • $26,000 outstanding                                  │
│                                                         │
│ Recent Activity (from emails):                         │
│ ✅ Acme Corp paid Invoice #892 ($12,500)              │
│    📧 "Payment confirmation received" - Oct 26        │
│                                                         │
│ ✅ Precision Plastics paid PO-2024-183 ($20,000)      │
│    📧 "Wire transfer completed" - Oct 24              │
│                                                         │
│ ⏳ Superior Tooling Quote #445 pending ($15,000)      │
│    📧 "Waiting on quality resolution" - Oct 27        │
│                                                         │
│ [View All Transactions] [Search Related Emails]       │
└────────────────────────────────────────────────────────┘
```

**The Magic:**
- Numbers come from QuickBooks (accurate, real-time)
- Context comes from CORTEX (emails, communications)
- CEO sees both "what happened" AND "why/how"

---

## 🎯 Decision Time

**Which approach should we build?**

### Option 1: Structured Cache (Recommended for CEO Dashboard)
- ✅ Fast
- ✅ Accurate metrics
- ✅ RAG enhancement for context
- ✅ Simple to implement
- ❌ QB data not in knowledge graph

### Option 2: Full Knowledge Graph Integration
- ✅ QB entities in Neo4j
- ✅ Unified graph queries
- ✅ Deep relationship analysis
- ❌ Slower sync
- ❌ More complex

### Option 3: Hybrid (Best of Both)
- ✅ Cache for dashboard metrics
- ✅ Selective entities in graph (e.g., major customers)
- ✅ Flexible querying
- ❌ Most complex

**My recommendation: Start with Option 1 (Structured Cache + RAG) for the CEO dashboard, then add Option 3 later if you need deep graph queries.**

---

## Next Steps

1. Create `quickbooks_cache` table in Supabase
2. Build `sync_quickbooks_task()` background job
3. Add `/dashboard/ceo` endpoint
4. Build frontend CEO dashboard with widgets
5. Test end-to-end flow

Ready to implement?
