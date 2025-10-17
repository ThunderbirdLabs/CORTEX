# Cortex - Enterprise RAG Platform
**v0.5.0 - Production Ready**

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
                         │ - Full metadata     │         │ - COMPANY nodes      │
                         └─────────────────────┘         │ - MENTIONED_IN rels  │
                                                         │ - Entity embeddings  │
                                                         │                      │
                                                         │ + Hourly entity      │
                                                         │   deduplication      │
                                                         │   (vector similarity)│
                                                         └──────────────────────┘
                                                     ┬────────────────┘
                                                     │
                                                     ▼
                                    ┌─────────────────────────────────┐
                                    │     HYBRID QUERY ENGINE         │
                                    │     (HybridQueryEngine)         │
                                    │                                 │
                                    │  SubQuestionQueryEngine:        │
                                    │  ├─ VectorStoreIndex (Qdrant)   │
                                    │  └─ PropertyGraphIndex (Neo4j)  │
                                    │                                 │
                                    │  Routes sub-questions to best   │
                                    │  index and synthesizes answers  │
                                    └─────────────────▲───────────────┘
                                                      │
                                           User queries via:
                                           /api/v1/chat
                                           /api/v1/search
```

---

## 🚀 What's New in v0.5.0

### **Production Code Cleanup** ✅
- ✅ Removed all deprecated code (hybrid_property_graph_pipeline.py, hybrid_retriever.py)
- ✅ Organized scripts into logical directories (archive/, maintenance/, utilities/)
- ✅ Cleaned up 15 one-time debug/fix scripts → archived
- ✅ Removed 5 .DS_Store files and improved .gitignore
- ✅ Updated documentation to match actual codebase structure
- ✅ Zero deprecated imports or dead code

### **Schema-Validated Knowledge Graph** ✅
- ✅ **SchemaLLMPathExtractor** - Strict entity/relationship validation
- ✅ 10 entity types (PERSON, COMPANY, EMAIL, DOCUMENT, etc.)
- ✅ 18 relationship types (SENT_BY, WORKS_AT, MENTIONS, etc.)
- ✅ Entity embeddings for graph-aware retrieval
- ✅ Unique document IDs (`title|doc_id`) - prevents duplicate merging
- ✅ MENTIONED_IN relationships - enables full graph traversal
- ✅ Clean entity properties (no document metadata pollution)

### **Hybrid Query Engine** ✅
- ✅ **SubQuestionQueryEngine** - Intelligent query decomposition
- ✅ **VectorStoreIndex** (Qdrant) - Semantic search over chunks
- ✅ **PropertyGraphIndex** (Neo4j) - Graph queries over entities
- ✅ Automatic routing to best retrieval strategy
- ✅ Multi-strategy synthesis for comprehensive answers

### **Entity Deduplication System** ✅
- ✅ **Vector similarity** (cosine > 0.92) + Levenshtein distance (< 3 chars)
- ✅ Hourly scheduled deduplication (APScheduler)
- ✅ API endpoints for manual triggering (`/api/v1/deduplication/run`)
- ✅ Dry-run mode for preview before merging
- ✅ Prevents array IDs (fixed `title|doc_id` bug)
- ✅ Configurable thresholds via environment variables

### **Universal Ingestion Pipeline** ✅
- ✅ Dual ingestion: Qdrant (chunks) + Neo4j (entities/documents)
- ✅ Dual metadata strategy: Full for Qdrant, minimal for Neo4j entities
- ✅ Content-based deduplication (SHA256 hashing)
- ✅ Batch processing with 4 workers (3-4x faster)
- ✅ 100k character limit per document (cost control)
- ✅ Any source → unified format → RAG
- ✅ Lightweight file parsing (lazy-loaded)

### **Production Fixes** ✅
- ✅ Fixed array ID bug (toString() errors in Neo4j queries)
- ✅ Fixed entity extraction field names (sender_name, to_addresses)
- ✅ Removed 464 lines of dead code
- ✅ Fixed encoding issues for Python 3.13
- ✅ Memory-optimized for Render (512MB)
- ✅ Updated all docstrings to reflect current architecture

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
   │   └─> Store chunks + embeddings + FULL metadata in Qdrant
   │       (Metadata includes: title, file_size, owner, source, etc.)
   │
   └─> NEO4J PATH:
       ├─> Create document node (EMAIL/DOCUMENT)
       │   └─> Unique ID: "title|doc_id" (prevents duplicate merging)
       ├─> SchemaLLMPathExtractor (GPT-4o-mini)
       │   ├─> Extract with MINIMAL metadata (document_id, title, type only)
       │   ├─> Extracts entities: PERSON, COMPANY, etc.
       │   └─> Extracts relationships: SENT_BY, WORKS_AT, etc.
       ├─> Create MENTIONED_IN relationships
       │   └─> (Entity)-[:MENTIONED_IN]->(Document)
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
CORTEX/
├── main.py                              # FastAPI entry point with APScheduler
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
│   │   └── ingestion.py                 # Document models
│   │
│   ├── services/                        # Business logic
│   │   ├── connectors/                  # Data connectors
│   │   │   ├── gmail.py                 # Gmail normalization
│   │   │   ├── google_drive.py          # Drive file handling
│   │   │   ├── microsoft_graph.py       # Outlook sync
│   │   │   └── slack.py                 # Slack (TODO: activate)
│   │   │
│   │   ├── nango/                       # OAuth & sync
│   │   │   ├── nango_client.py          # Nango API client
│   │   │   ├── drive_client.py          # Drive-specific actions
│   │   │   ├── drive_sync.py            # Drive sync engine
│   │   │   ├── sync_engine.py           # Email sync orchestration
│   │   │   ├── database.py              # Connection management
│   │   │   └── persistence.py           # Data persistence
│   │   │
│   │   ├── ingestion/                   # RAG pipeline (v0.5.0 structure)
│   │   │   └── llamaindex/
│   │   │       ├── __init__.py          # Exports UniversalIngestionPipeline, HybridQueryEngine
│   │   │       ├── config.py            # LlamaIndex configuration
│   │   │       ├── ingestion_pipeline.py # Universal ingestion (replaces old hybrid_property_graph_pipeline)
│   │   │       └── query_engine.py      # Hybrid query engine (replaces old hybrid_retriever)
│   │   │
│   │   ├── parsing/                     # File parsing
│   │   │   └── file_parser.py           # Universal file parser (lazy-loaded)
│   │   │
│   │   ├── deduplication/               # Content & entity deduplication
│   │   │   ├── dedupe_service.py        # SHA256 hash-based deduping
│   │   │   └── entity_deduplication.py  # Vector similarity entity merging
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
│       ├── chat.py                      # Chat interface
│       └── deduplication.py             # Entity deduplication API
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
├── scripts/                             # Utility scripts (organized in v0.5.0)
│   ├── analysis/                        # Graph analysis
│   │   └── analyze_neo4j_graph.py       # Comprehensive Neo4j stats
│   │
│   ├── database_tools/                  # DB inspection & management
│   │   ├── audit_databases.py           # Multi-DB audit
│   │   ├── audit_qdrant_complete.py     # Qdrant deep inspection
│   │   ├── check_databases.py           # Quick health check
│   │   ├── check_supabase_tables.py     # Supabase table stats
│   │   ├── clear_databases.py           # Clear Neo4j + Qdrant
│   │   ├── create_production_indexes_v2.py # Create Neo4j indexes
│   │   ├── inspect_node_content.py      # Inspect specific nodes
│   │   └── preview_supabase_data.py     # Preview Supabase data
│   │
│   ├── setup/                           # Initial setup
│   │   └── create_neo4j_indexes.py      # Create graph indexes
│   │
│   ├── maintenance/                     # Ongoing maintenance
│   │   └── deduplicate_entities.py      # Entity deduplication script
│   │
│   ├── utilities/                       # Utility scripts
│   │   └── clear_and_reingest.py        # Clear DBs and reingest
│   │
│   ├── testing/                         # Test scripts
│   │   ├── test_deduplication.py        # Test entity dedupe
│   │   ├── test_entity_extraction.py    # Test extraction
│   │   ├── test_production_flow.py      # End-to-end test
│   │   ├── test_query.py                # Test query engine
│   │   ├── test_retrieval_detailed.py   # Detailed retrieval test
│   │   └── test_universal_ingestion.py  # Test ingestion pipeline
│   │
│   └── archive/                         # Archived scripts (one-time fixes, old tests)
│
├── migrations/                          # Database migrations
│   ├── schema.sql                       # Main schema
│   ├── create_documents_table.sql       # Documents table
│   ├── create_chat_tables.sql           # Chat tables
│   ├── add_content_hash_column.sql      # Content deduplication
│   └── add_episode_id_column.sql        # Episode tracking
│
├── docs/                                # Documentation
│   ├── PRODUCTION_READY_SUMMARY.md      # Production readiness summary
│   ├── PRODUCTION_ARCHITECTURE.md       # Architecture deep dive
│   ├── PRODUCTION_DEDUPLICATION_STRATEGY.md # Deduplication strategy
│   ├── FIXES_IMPLEMENTED.md             # Bug fixes log
│   ├── SUPABASE_INGESTION_STRATEGY.md   # Supabase integration guide
│   ├── CONTINUOUS_INGESTION_OPTIMIZATION.md # Optimization guide
│   ├── SCALING_FIX_ENTITY_PROPERTIES.md # Entity property cleanup
│   └── GRAPH_ANALYSIS_CRITICAL_ISSUES.md # Graph issues found & fixed
│
├── nango-integrations/                  # Nango OAuth integrations
│   ├── google-drive/                    # Google Drive connector
│   ├── dist/                            # Compiled integrations
│   └── nango.yaml                       # Nango configuration
│
├── archive/                             # Archived code
│   └── legacy-ui/                       # Old standalone UI
│
├── requirements.txt                     # Python dependencies
├── runtime.txt                          # Python 3.13
├── .gitignore                           # Comprehensive gitignore (v0.5.0)
├── .env.example                         # Environment variables template
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
| `GET /api/v1/chat/health` | GET | None | Query engine health |

### **File Management**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `POST /api/v1/upload/file` | POST | JWT + API Key | Upload file for ingestion |
| `GET /api/v1/emails/{episode_id}` | GET | JWT | Get full email by episode ID |

### **Entity Deduplication**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `POST /api/v1/deduplication/run` | POST | JWT | Trigger entity deduplication |
| `GET /api/v1/deduplication/status` | GET | JWT | Deduplication status |

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
git clone https://github.com/ThunderbirdLabs/CORTEX.git
cd CORTEX

# Install dependencies
pip install -r requirements.txt

# Set environment variables (see .env.example)
cp .env.example .env
# Edit .env with your credentials

# Run locally
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

### **Environment Variables**

```bash
# Server
ENVIRONMENT=production
PORT=8080
DEBUG=false

# Database (Supabase)
DATABASE_URL=postgresql://...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...

# Nango OAuth
NANGO_SECRET=...
NANGO_PROVIDER_KEY_GMAIL=gmail-connector
NANGO_PROVIDER_KEY_GOOGLE_DRIVE=google-drive
NANGO_PROVIDER_KEY_OUTLOOK=outlook-connector

# RAG System
QDRANT_URL=https://...
QDRANT_API_KEY=...
QDRANT_COLLECTION_NAME=cortex_documents
NEO4J_URI=neo4j+s://...
NEO4J_USER=neo4j
NEO4J_PASSWORD=...
NEO4J_DATABASE=neo4j
OPENAI_API_KEY=sk-proj-...

# Entity Deduplication (v0.5.0)
DEDUP_ENABLED=true
DEDUP_INTERVAL_HOURS=1
DEDUP_SIMILARITY_THRESHOLD=0.92
DEDUP_LEVENSHTEIN_MAX_DISTANCE=3

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

### **Neo4j Setup**

```bash
# Run index creation script
python scripts/setup/create_neo4j_indexes.py
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

### **Test Entity Deduplication**
```bash
# Dry run (preview only)
python scripts/maintenance/deduplicate_entities.py --dry-run

# Actually merge
python scripts/maintenance/deduplicate_entities.py
```

---

## 🔐 Security

### **Authentication**

1. **JWT (Supabase)** - User authentication
   - Used for: OAuth, sync, general API access
   - Header: `Authorization: Bearer <token>`

2. **API Key** - Search endpoint protection
   - Used for: `/api/v1/search`, `/api/v1/upload`
   - Header: `X-API-Key: <key>`

### **Data Privacy**

- All user data isolated by `tenant_id`
- OAuth tokens managed by Nango (never stored in app)
- Content hashing for deduplication (SHA256)
- Supabase RLS policies (recommended)

---

## 🔧 Key Features

### **Dual Metadata Strategy (v0.5.0)**
- **Qdrant**: Full metadata for rich filtering (file_size, owner, source, dates, etc.)
- **Neo4j Entities**: Minimal metadata only (prevents property pollution)
- **Neo4j Documents**: Full metadata preserved

### **Content Deduplication**
- SHA256 hash-based detection
- Prevents duplicate ingestion across sources
- Saves RAG processing costs
- Indexed for fast lookup

### **Entity Deduplication**
- Vector similarity matching (> 0.92 cosine)
- Levenshtein distance verification (< 3 edits)
- Scheduled hourly (configurable)
- Manual API trigger available
- Dry-run mode for safety

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
- Scheduled background jobs (APScheduler)

---

## 🐛 Troubleshooting

### **"Empty Response" in chat**
- No data indexed yet. Go to Connections → Sync Gmail/Drive first

### **"Out of Memory" on Render**
- Verify you're using lazy-loaded parsers
- Check memory usage in Render dashboard
- Upgrade to paid tier if needed

### **Google Workspace files show garbled text**
- Fixed in v0.3.0+ - uses proper export MIME types
- Docs/Slides → `text/plain`
- Sheets → `text/csv`

### **"Column content_hash does not exist"**
- Run the database migration (see Database Setup)

### **Entity deduplication errors**
- Ensure Neo4j has APOC plugin installed
- Check similarity threshold isn't too aggressive
- Run in dry-run mode first to preview changes

---

## 📚 Version History

### **v0.5.0 (Current) - Production Ready & Code Cleanup** 
- ✅ Complete code cleanup and organization
- ✅ Removed all deprecated code (hybrid_property_graph_pipeline, hybrid_retriever)
- ✅ Organized scripts into logical directories
- ✅ Updated all documentation to match current state
- ✅ Comprehensive .gitignore
- ✅ Fixed all docstrings and comments
- ✅ Zero deprecated imports or dead code

### **v0.4.5 - RAG Architecture Documentation**
- ✅ Comprehensive README with accurate architecture
- ✅ Document all fixes and improvements
- ✅ Entity deduplication system fully documented

### **v0.4.0 - Production Fixes & Entity Deduplication**
- ✅ Fixed array ID bug in Neo4j
- ✅ Entity deduplication system (vector similarity + Levenshtein)
- ✅ Scheduled background jobs (APScheduler)
- ✅ Clean entity properties (no metadata pollution)
- ✅ MENTIONED_IN relationships for graph traversal

### **v0.3.0 - Google Drive & Universal Ingestion**
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

**Built with ❤️ by Nicolas Codet & Alex Kashkarian**  
**Stack:** FastAPI, LlamaIndex, Qdrant, Neo4j, OpenAI, Supabase, Next.js
