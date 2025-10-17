# Cortex - Enterprise RAG Platform
**v0.4.5**

Enterprise-grade unified backend for **multi-source data ingestion** (Gmail, Outlook, Google Drive, file uploads) with **AI-powered hybrid RAG search** (vector + knowledge graph).

Built with FastAPI, LlamaIndex, Qdrant, Neo4j, and OpenAI.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                      FRONTEND (Vercel - Next.js)                     │
│         Modern React UI with OAuth, Chat, and Connections            │
└─────────────┬───────────────────────────────────────┬───────────────┘
              │                                       │
              ▼                                       ▼
┌─────────────────────────┐           ┌──────────────────────────────┐
│   NANGO (OAuth Proxy)   │           │   CORTEX BACKEND (Render)    │
│   - Gmail OAuth         │           │   FastAPI - main.py          │
│   - Outlook OAuth       │◄──────────┤   - OAuth webhooks           │
│   - Google Drive OAuth  │           │   - Multi-source sync        │
│   - Token management    │           │   - Normalization            │
└─────────────────────────┘           └──────────────┬───────────────┘
                                                     │
                                                     ▼
                                      ┌──────────────────────────────┐
                                      │   SUPABASE (PostgreSQL)      │
                                      │   - documents table          │
                                      │   - emails table             │
                                      │   - Content dedupe (SHA256)  │
                                      └──────────────┬───────────────┘
                                                     │
                                    ┌────────────────┴────────────────┐
                                    │  UNIVERSAL INGESTION PIPELINE   │
                                    │  (UniversalIngestionPipeline)   │
                                    └────────────────┬────────────────┘
                                                     │
                                    ┌────────────────┴────────────────┐
                                    │                                 │
                         ┌──────────▼──────────┐         ┌───────────▼──────────┐
                         │   QDRANT CLOUD      │         │      NEO4J AURA      │
                         │   Vector Store      │         │   Property Graph     │
                         │                     │         │                      │
                         │ - Text chunks       │         │ - EMAIL nodes        │
                         │ - Embeddings        │         │ - PERSON nodes       │
                         │ - Metadata          │         │ - COMPANY nodes      │
                         └─────────────────────┘         │ - Relationships      │
                                                         │ - Entity embeddings  │
                                                         │                      │
                                                         │ + Hourly entity      │
                                                         │   deduplication      │
                                                         │   (vector similarity)│
                                                         └──────────────────────┘
                                                     ┬────────────────┘
                                                     │
                                                     |
                                                     │                 
                                    ┌────────────────▼─────────────────-──┐
                                    │     HYBRID QUERY ENGINE             │
                                    │     (HybridQueryEngine)             │
                                    │                                     │
                                    │  SubQuestionQueryEngine combines:   │
                                    │  ├─ VectorStoreIndex (Qdrant)       │
                                    │  └─ PropertyGraphIndex (Neo4j)      │
                                    │                                     │
                                    │  Routes sub-questions to best index │
                                    │  Synthesizes comprehensive answers  │
                                    └─────────────────▲───────────────────┘
                                                      │
                                           User queries via:
                                           /api/v1/chat
                                           /api/v1/search
```

---

## 🚀 What's New in v0.4.5

### **Schema-Validated Knowledge Graph**
- ✅ **SchemaLLMPathExtractor** - Strict entity/relationship validation
- ✅ 10 entity types (PERSON, COMPANY, EMAIL, DOCUMENT, etc.)
- ✅ 18 relationship types (SENT_BY, WORKS_AT, MENTIONS, etc.)
- ✅ Entity embeddings for graph-aware retrieval
- ✅ Unique document IDs (`title|doc_id`) - prevents duplicate merging
- ✅ Neo4j label reordering for better visualization

### **Hybrid Query Engine**
- ✅ **SubQuestionQueryEngine** - Intelligent query decomposition
- ✅ **VectorStoreIndex** (Qdrant) - Semantic search over chunks
- ✅ **PropertyGraphIndex** (Neo4j) - Graph queries over entities
- ✅ Automatic routing to best retrieval strategy
- ✅ Multi-strategy synthesis for comprehensive answers

### **Entity Deduplication System**
- ✅ **Vector similarity** (cosine > 0.92) + Levenshtein distance (< 3 chars)
- ✅ Hourly scheduled deduplication (APScheduler)
- ✅ API endpoints for manual triggering (`/api/v1/deduplication/run`)
- ✅ Dry-run mode for preview before merging
- ✅ Prevents array IDs (fixed `title|doc_id` bug)
- ✅ Configurable thresholds via environment variables

### **Universal Ingestion Pipeline**
- ✅ Dual ingestion: Qdrant (chunks) + Neo4j (entities/documents)
- ✅ Content-based deduplication (SHA256 hashing)
- ✅ Batch processing with 4 workers
- ✅ 100k character limit per document (cost control)
- ✅ Any source → unified format → RAG
- ✅ Lightweight file parsing (lazy-loaded)

### **Production Fixes**
- ✅ Fixed array ID bug (toString() errors in Neo4j queries)
- ✅ Fixed entity extraction field names (sender_name, to_addresses)
- ✅ Removed 464 lines of dead code
- ✅ Fixed encoding issues for Python 3.13
- ✅ Memory-optimized for Render (512MB)

---

## 📊 Data Flow

### **FLOW 1: Universal Document Ingestion**

```
1. DATA SOURCE (Gmail/Drive/Upload)
   └─> Fetch via Nango API or direct upload

2. NORMALIZATION
   ├─> Google Workspace files → Export to text/CSV
   ├─> PDFs → Fast text extraction (no OCR)
   ├─> Office files → Unstructured parsing
   └─> Content hash → SHA256 for deduplication

3. DEDUPLICATION CHECK
   └─> Query Supabase by (tenant_id + content_hash + source)
   └─> Skip if duplicate found

4. SAVE TO SUPABASE
   └─> Insert into documents table (full text + metadata)

5. DUAL INGESTION (UniversalIngestionPipeline)
   ├─> QDRANT PATH:
   │   ├─> SentenceSplitter (chunk_size=1024, overlap=200)
   │   ├─> OpenAIEmbedding (text-embedding-3-small)
   │   └─> Store chunks + embeddings in Qdrant
   │
   └─> NEO4J PATH:
       ├─> Create document node (EMAIL/DOCUMENT)
       │   └─> Unique ID: "title|doc_id" (prevents duplicate merging)
       ├─> SchemaLLMPathExtractor (GPT-4o-mini)
       │   ├─> Extract entities: PERSON, COMPANY, etc.
       │   ├─> Extract relationships: SENT_BY, WORKS_AT, etc.
       │   └─> Generate entity embeddings
       └─> Store in Neo4j Property Graph

6. HOURLY ENTITY DEDUPLICATION (Neo4j only)
   ├─> Find similar entities (vector similarity > 0.92)
   ├─> Verify with Levenshtein distance (< 3 chars)
   └─> Merge duplicates with apoc.refactor.mergeNodes
```

### **FLOW 2: AI Search (Hybrid RAG)**

```
1. USER QUERY → POST /api/v1/chat or /api/v1/search

2. HYBRID QUERY ENGINE (HybridQueryEngine)
   └─> SubQuestionQueryEngine breaks down complex questions

3. PARALLEL RETRIEVAL
   ├─> VectorStoreIndex (Qdrant):
   │   ├─> Embed query with OpenAI
   │   ├─> Semantic search over text chunks
   │   └─> Return top K similar chunks (default: 10)
   │
   └─> PropertyGraphIndex (Neo4j):
       ├─> Graph queries for relationships
       ├─> Entity lookups (PERSON, COMPANY, EMAIL)
       └─> Return relevant entities + relationships

4. SYNTHESIS
   ├─> SubQuestionQueryEngine combines results
   ├─> GPT-4o-mini generates comprehensive answer
   └─> Cites sources from both indexes

5. RESPONSE
   └─> {answer, source_count, sources: [{node_id, text, score}]}
```

---

## 🗂️ Codebase Structure

```
NANGO-CONNECTION-ONLY/
├── main.py                              # FastAPI entry point (v0.3.0)
│
├── app/                                 # Main application
│   ├── core/                            # Infrastructure
│   │   ├── config.py                    # Pydantic Settings (all env vars)
│   │   ├── dependencies.py              # DI (HTTP, Supabase, RAG pipeline)
│   │   └── security.py                  # JWT + API key auth
│   │
│   ├── middleware/                      # Request processing
│   │   ├── error_handler.py             # Global exception handling
│   │   ├── logging.py                   # Request logging
│   │   └── cors.py                      # CORS configuration
│   │
│   ├── models/schemas/                  # Pydantic models
│   │   ├── connector.py                 # OAuth, webhooks
│   │   ├── sync.py                      # Sync operations
│   │   ├── search.py                    # Search request/response
│   │   ├── ingestion.py                 # Document models
│   │   └── knowledge_graph.py           # Graph entity types
│   │
│   ├── services/                        # Business logic
│   │   ├── connectors/                  # Data connectors
│   │   │   ├── gmail.py                 # Gmail normalization
│   │   │   ├── google_drive.py          # Drive file handling
│   │   │   └── microsoft_graph.py       # Outlook sync
│   │   │
│   │   ├── nango/                       # OAuth & sync
│   │   │   ├── nango_client.py          # Nango API client
│   │   │   ├── drive_client.py          # Drive-specific actions
│   │   │   ├── drive_sync.py            # Drive sync engine
│   │   │   ├── sync_engine.py           # Email sync orchestration
│   │   │   ├── database.py              # Connection management
│   │   │   └── persistence.py           # Data persistence
│   │   │
│   │   ├── ingestion/                   # RAG pipeline
│   │   │   └── llamaindex/
│   │   │       ├── config.py            # LlamaIndex configuration
│   │   │       ├── hybrid_property_graph_pipeline.py
│   │   │       └── hybrid_retriever.py  # Multi-strategy retrieval
│   │   │
│   │   ├── parsing/                     # File parsing
│   │   │   └── file_parser.py           # Universal file parser (lazy-loaded)
│   │   │
│   │   ├── deduplication/               # Content deduplication
│   │   │   └── dedupe_service.py        # SHA256 hash-based deduping
│   │   │
│   │   ├── universal/                   # Universal ingestion
│   │   │   └── ingest.py                # Unified ingestion flow
│   │   │
│   │   └── search/
│   │       └── query_rewriter.py        # Context-aware query expansion
│   │
│   └── api/v1/routes/                   # API endpoints (v1)
│       ├── health.py                    # Health checks
│       ├── oauth.py                     # OAuth flow (Gmail/Drive/Outlook)
│       ├── webhook.py                   # Nango webhooks
│       ├── sync.py                      # Manual sync endpoints
│       ├── search.py                    # Hybrid RAG search
│       ├── emails.py                    # Email retrieval
│       ├── upload.py                    # File upload
│       └── chat.py                      # Chat interface
│
├── connectorfrontend/                   # Next.js frontend
│   ├── app/                             # App router
│   │   ├── page.tsx                     # Main chat page
│   │   ├── connections/page.tsx         # OAuth & sync UI
│   │   └── login/page.tsx               # Auth page
│   ├── components/
│   │   └── sidebar.tsx                  # Navigation sidebar
│   ├── contexts/
│   │   └── auth-context.tsx             # Supabase auth
│   └── lib/
│       └── api.ts                       # Backend API client
│
├── scripts/                             # Utility scripts
│   ├── database_tools/                  # DB inspection
│   ├── ingestion/                       # Data ingestion
│   └── testing/                         # Test scripts
│
├── requirements.txt                     # Python dependencies
├── runtime.txt                          # Python 3.13
└── README.md                            # This file
```

---

## 🔌 API Endpoints (v1)

### **OAuth & Connections**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `GET /` | GET | None | API info |
| `GET /health` | GET | None | Health check |
| `GET /status` | GET | JWT | Connection status (Gmail/Drive/Outlook) |
| `GET /connect/start?provider={gmail\|google-drive\|outlook}` | GET | JWT | Initiate OAuth |
| `POST /nango/webhook` | POST | None | Nango auth/sync webhook |

### **Data Sync**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `GET /sync/once` | GET | JWT | Manual Outlook sync |
| `GET /sync/once/gmail` | GET | JWT | Manual Gmail sync |
| `GET /sync/once/drive?folder_ids=id1,id2` | GET | JWT | Manual Drive sync |

### **Search & Chat**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `POST /api/v1/search` | POST | JWT + API Key | Hybrid RAG search |
| `POST /api/v1/chat` | POST | JWT | Chat interface |

### **File Management**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `POST /api/v1/upload/file` | POST | JWT + API Key | Upload file for ingestion |
| `GET /api/v1/emails/{episode_id}` | GET | JWT | Get full email by episode ID |

---

## 🚀 Quick Start

### **Prerequisites**

- Python 3.13+
- PostgreSQL (Supabase)
- Qdrant Cloud account
- Neo4j Aura database
- OpenAI API key
- Nango account

### **Installation**

```bash
# Clone repo
git clone https://github.com/ThunderbirdLabs/NANGO-CONNECTION-ONLY.git
cd NANGO-CONNECTION-ONLY

# Install dependencies
pip install -r requirements.txt

# Set environment variables (see .env.example)

# Run locally
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### **Environment Variables**

```bash
# Server
ENVIRONMENT=production
PORT=8080

# Database (Supabase)
DATABASE_URL=postgresql://...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...

# Nango OAuth
NANGO_SECRET=...
NANGO_PROVIDER_KEY_GMAIL=gmail-connector
NANGO_PROVIDER_KEY_GOOGLE_DRIVE=google-drive  # Optional, falls back to gmail
NANGO_PROVIDER_KEY_OUTLOOK=outlook-connector

# RAG System
QDRANT_URL=https://...
QDRANT_API_KEY=...
QDRANT_COLLECTION_NAME=cortex_documents
NEO4J_URI=neo4j+s://...
NEO4J_PASSWORD=...
OPENAI_API_KEY=sk-proj-...

# API Keys
CORTEX_API_KEY=your-search-api-key
```

### **Database Setup**

Run SQL migrations in Supabase:

```sql
-- Documents table (unified storage)
CREATE TABLE documents (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  source TEXT NOT NULL,
  source_id TEXT NOT NULL,
  document_type TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  content_hash TEXT,  -- For deduplication
  raw_data JSONB,
  file_type TEXT,
  file_size BIGINT,
  source_created_at TIMESTAMPTZ,
  source_modified_at TIMESTAMPTZ,
  ingested_at TIMESTAMPTZ DEFAULT NOW(),
  metadata JSONB,
  UNIQUE(tenant_id, source, source_id)
);

CREATE INDEX idx_documents_tenant ON documents(tenant_id);
CREATE INDEX idx_documents_content_hash ON documents(tenant_id, content_hash, source);
```

---

## 🧪 Testing

### **Health Check**
```bash
curl https://your-app.onrender.com/health
```

### **Connection Status**
```bash
curl -H "Authorization: Bearer <jwt>" \
  https://your-app.onrender.com/status
```

### **Manual Drive Sync**
```bash
curl -H "Authorization: Bearer <jwt>" \
  "https://your-app.onrender.com/sync/once/drive"
```

### **RAG Search**
```bash
curl -X POST https://your-app.onrender.com/api/v1/search \
  -H "Authorization: Bearer <jwt>" \
  -H "X-API-Key: <api-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the key points from the Q4 report?",
    "vector_limit": 5,
    "graph_limit": 5
  }'
```

---

## 🔐 Security

### **Authentication**

1. **JWT (Supabase)** - User authentication
   - Used for: OAuth, sync, general API access
   - Header: `Authorization: Bearer <token>`

2. **API Key** - Search endpoint protection
   - Used for: `/api/v1/search`
   - Header: `X-API-Key: <key>`

### **Data Privacy**

- All user data isolated by `tenant_id`
- OAuth tokens managed by Nango (never stored in app)
- Content hashing for deduplication (SHA256)
- Supabase RLS policies (recommended)

---

## 🔧 Key Features

### **Content Deduplication**
- SHA256 hash-based detection
- Prevents duplicate ingestion across sources
- Saves RAG processing costs
- Indexed for fast lookup

### **Incremental Sync**
- Google Drive: Uses `source_modified_at` timestamp
- Gmail: Cursor-based pagination
- Outlook: Delta links for changes only

### **Memory Optimization**
- Lazy-loaded PDF parser (no heavy ML at startup)
- Removed `unstructured[all-docs]` heavy dependencies
- Character limit (100k) per document
- Fits in Render's 512MB free tier

### **Enterprise Patterns**
- Dependency injection (FastAPI)
- Type-safe configuration (Pydantic)
- API versioning (`/api/v1/`)
- Centralized error handling
- Structured logging

---

## 🐛 Troubleshooting

### **"Empty Response" in chat**
- No data indexed yet. Go to Connections → Sync Gmail/Drive first

### **"Out of Memory" on Render**
- Verify you're on v0.3.0 (lazy-loaded parsers)
- Check memory usage in Render dashboard
- Upgrade to paid tier if needed

### **Google Workspace files show garbled text**
- Fixed in v0.3.0 - uses proper export MIME types
- Docs/Slides → `text/plain`
- Sheets → `text/csv`

### **"Column content_hash does not exist"**
- Run the database migration (see Database Setup)

---

## 📚 Version History

### **v0.3.0 (Current) - Google Drive & Universal Ingestion**
- ✅ Google Drive OAuth & incremental sync
- ✅ Universal ingestion pipeline (any source → RAG)
- ✅ Content-based deduplication (SHA256)
- ✅ Modern Aetheris-style frontend
- ✅ Memory optimizations (lazy loading, 512MB fit)
- ✅ Google Workspace proper export (Docs/Sheets/Slides)
- ✅ Comprehensive error handling

### **v0.2.0 - Enterprise Refactor**
- ✅ Unified backend architecture
- ✅ Dependency injection pattern
- ✅ Type-safe configuration
- ✅ API versioning (`/api/v1/`)

### **v0.1.0 - Initial Release**
- Email sync (Gmail/Outlook)
- Hybrid RAG search
- Basic frontend

---

## 📝 License

Proprietary - ThunderbirdLabs

---

**Built with ❤️ by Nicolas Codet using FastAPI, LlamaIndex, Graphiti, Qdrant, Neo4j, and OpenAI**
