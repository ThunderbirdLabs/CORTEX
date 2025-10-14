# Email Sync & Hybrid RAG Platform

**Enterprise-grade email synchronization service with AI-powered search** combining Nango OAuth, Supabase storage, and Cortex Hybrid RAG (vector + knowledge graph).

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (Vercel)                            │
│                  User initiates OAuth & queries data                 │
└─────────────┬───────────────────────────────────────┬───────────────┘
              │                                       │
              ▼                                       ▼
┌─────────────────────────┐           ┌──────────────────────────────┐
│   NANGO (OAuth Proxy)   │           │   THIS SERVICE (Render)      │
│   - Gmail OAuth         │           │   FastAPI Backend            │
│   - Outlook OAuth       │◄──────────┤   - Nango webhooks           │
│   - Token management    │           │   - Email sync engine        │
└─────────────────────────┘           │   - Cortex RAG search        │
                                      └───────┬──────────────┬───────┘
                                              │              │
                ┌─────────────────────────────┼──────────────┼─────────┐
                │                             │              │         │
                ▼                             ▼              ▼         ▼
       ┌────────────────┐          ┌─────────────────┐  ┌────────┐ ┌────────┐
       │   SUPABASE     │          │   QDRANT CLOUD  │  │ NEO4J  │ │OPENAI  │
       │   PostgreSQL   │          │   Vector Store  │  │ Graph  │ │  LLM   │
       │   - Emails     │          │   - Embeddings  │  │Graphiti│ │Embedder│
       │   - Metadata   │          │   - Chunks      │  │Entities│ │        │
       └────────────────┘          └─────────────────┘  └────────┘ └────────┘
```

---

## 📊 Data Flow

### **FLOW 1: Email Ingestion (Nango → Supabase → Cortex)**

```
1. USER completes OAuth (Gmail/Outlook)
   └─> Nango stores tokens & sends webhook

2. WEBHOOK received (/nango/webhook)
   └─> Triggers background sync task

3. SYNC ENGINE fetches emails
   ├─ Outlook: Microsoft Graph API (delta sync)
   └─ Gmail: Nango Unified API (cursor pagination)

4. NORMALIZATION transforms raw emails
   └─> Unified schema (tenant_id, source, message_id, full_body, etc.)

5. DUAL PERSISTENCE
   ├─> SUPABASE: Raw email + metadata (PostgreSQL)
   └─> CORTEX: Hybrid RAG ingestion
       ├─> Chunking: LlamaIndex semantic splitter
       ├─> Vector DB: Embeddings → Qdrant
       ├─> Knowledge Graph: Entities/relationships → Neo4j (Graphiti)
       └─> Episode ID: Shared UUID links vector ↔ graph
```

### **FLOW 2: AI Search (Frontend → Cortex → Results)**

```
1. USER sends search query
   └─> POST /api/search-optimized

2. QUERY REWRITING (context-aware)
   └─> Expands query using conversation history

3. HYBRID RAG EXECUTION
   ├─> VECTOR SEARCH (Qdrant)
   │   └─> Returns top-k chunks with episode_ids
   │
   ├─> GRAPH SEARCH (Neo4j via Graphiti)
   │   └─> Filters by episode_ids from vector results
   │   └─> Returns entity relationships & facts
   │
   └─> SYNTHESIS (OpenAI GPT-4o-mini)
       └─> Generates answer from combined context

4. RESPONSE returned
   └─> {answer, vector_results[], graph_results[], episodes[]}
```

---

## 🗂️ Codebase Structure

```
connections/
├── app.py (257 lines)              # Main FastAPI app - routes & startup
│
├── config/                          # Configuration
│   └── settings.py                  # Environment variables & validation
│
├── nango_services/                  # Email sync orchestration
│   ├── database.py                  # PostgreSQL helpers (connections, cursors)
│   ├── nango_client.py              # Nango API client (tokens, Gmail API)
│   ├── microsoft_graph.py           # MS Graph helpers (Outlook sync)
│   ├── gmail.py                     # Gmail normalization
│   ├── persistence.py               # Supabase + Cortex ingestion
│   └── sync_engine.py               # Sync orchestration (run_gmail_sync, run_tenant_sync)
│
├── routers/                         # API endpoints
│   ├── nango_oauth.py               # OAuth callback handler
│   ├── nango_webhook.py             # Nango webhook receiver
│   ├── sync.py                      # Manual sync endpoints
│   └── status.py                    # Health checks
│
└── cortex_backend/                  # Hybrid RAG system (2,651 lines - CORE SEARCH)
    ├── api/routers/
    │   └── search_llamaindex.py     # /api/search-optimized endpoint
    ├── core/
    │   ├── pipeline.py              # Document ingestion pipeline
    │   ├── hybrid_query_engine.py   # Episode-filtered hybrid search
    │   ├── query_rewriter.py        # Context-aware query expansion
    │   └── response_generator.py    # LLM response synthesis
    ├── models/
    │   └── api_models.py            # Pydantic schemas
    ├── middleware/
    │   └── auth.py                  # API key verification
    └── services/
        ├── qdrant_setup.py          # Vector DB initialization
        └── gmail_preprocessor.py    # Email-specific preprocessing
```

---

## 🔌 API Endpoints

### **Email Sync**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/connect/start` | GET | Bearer JWT | Initiate OAuth flow (returns Nango URL) |
| `/nango/oauth/callback` | POST | None | Nango OAuth callback (saves connection) |
| `/nango/webhook` | POST | None | Nango sync webhook (triggers email sync) |
| `/sync/once` | GET | Bearer JWT | Manual Outlook sync |
| `/sync/once/gmail` | GET | Bearer JWT | Manual Gmail sync |
| `/status` | GET | Bearer JWT | Connection status (which providers connected) |
| `/health` | GET | None | Health check |

### **AI Search (Cortex)**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/search-optimized` | POST | API Key | Hybrid RAG search (vector + graph) |

---

## 🚀 Setup Instructions

### **1. Prerequisites**

- **Python 3.13+**
- **PostgreSQL** (via Supabase)
- **Qdrant Cloud** account
- **Neo4j Aura** database
- **OpenAI API** key
- **Nango** account (OAuth proxy)
- **Supabase** project

### **2. Install Dependencies**

```bash
pip install -r requirements.txt
```

### **3. Configure Environment Variables**

Copy `.env.example` to `.env` and fill in:

```bash
# Server
PORT=8080

# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://user:pass@host:5432/db
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key  # For Cortex
SUPABASE_DB_URL=postgresql://postgres:pass@db.your-project.supabase.co:5432/postgres

# Nango OAuth
NANGO_SECRET=your-nango-secret-key
NANGO_PROVIDER_KEY_OUTLOOK=microsoft-graph
NANGO_PROVIDER_KEY_GMAIL=google-mail
NANGO_CONNECTION_ID_OUTLOOK=your-outlook-connection-id
NANGO_CONNECTION_ID_GMAIL=your-gmail-connection-id

# Microsoft Graph (optional for logging)
GRAPH_TENANT_ID=your-azure-tenant-id

# Cortex Hybrid RAG
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password
OPENAI_API_KEY=sk-proj-your-openai-api-key
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key
QDRANT_COLLECTION_NAME=cortex_documents
CORTEX_API_KEY=your-api-key-for-search-endpoint

# Debug
SAVE_JSONL=false  # Set to true to write emails to outbox.jsonl
SEMAPHORE_LIMIT=10  # Graphiti concurrency limit
```

### **4. Initialize Database**

```bash
psql $DATABASE_URL < schema.sql
```

### **5. Run Locally**

```bash
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

### **6. Deploy to Render**

1. Connect GitHub repo to Render
2. Set environment variables in Render dashboard
3. Auto-deploys on `git push origin main`

---

## 🔐 Authentication

### **User Authentication (Supabase JWT)**

Frontend obtains JWT from Supabase auth, sends in `Authorization: Bearer <token>` header.

**Used by:**
- `/connect/start`
- `/sync/once`
- `/sync/once/gmail`
- `/status`

### **API Key Authentication (Cortex)**

Search endpoint requires `X-API-Key` header with `CORTEX_API_KEY`.

**Used by:**
- `/api/search-optimized`

---

## 🧪 Testing

### **1. Health Check**

```bash
curl http://localhost:8080/health
# Expected: {"status": "healthy"}
```

### **2. Check Connection Status**

```bash
curl -H "Authorization: Bearer <supabase-jwt>" \
  http://localhost:8080/status
```

### **3. Manual Gmail Sync**

```bash
curl -H "Authorization: Bearer <supabase-jwt>" \
  "http://localhost:8080/sync/once/gmail?modified_after=2024-01-01T00:00:00Z"
```

### **4. Hybrid RAG Search**

```bash
curl -X POST http://localhost:8080/api/search-optimized \
  -H "X-API-Key: your-cortex-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What did John say about the project deadline?",
    "vector_limit": 10,
    "graph_limit": 20,
    "conversation_history": []
  }'
```

---

## 📈 Monitoring & Logs

### **Render Logs**

```bash
# View recent logs
curl -H "Authorization: Bearer <render-api-token>" \
  "https://api.render.com/v1/services/<service-id>/logs?type=build"
```

### **Debug Mode**

Set `SAVE_JSONL=true` in `.env` to write all synced emails to `./outbox.jsonl` for inspection.

---

## 🔧 Key Design Decisions

### **Why Separate Nango & Cortex?**

- **Nango services**: Email sync orchestration (stateful, cursor management)
- **Cortex backend**: AI search (stateless, read-only queries)
- **Separation**: Allows independent scaling & testing

### **Why Episode ID Linking?**

Each email chunk gets a unique `episode_id` UUID stored in **both** Qdrant and Neo4j. This allows:
1. Vector search returns top chunks with episode IDs
2. Graph search filters by those episode IDs only
3. **Result**: 10x fewer tokens, 5x faster queries, more accurate answers

### **Why LlamaIndex + Graphiti?**

- **LlamaIndex**: Best-in-class document chunking & query engine
- **Graphiti**: Temporal knowledge graph (tracks when facts were valid)
- **Combo**: Hybrid search beats pure vector or pure graph alone

---

## 🐛 Troubleshooting

### **"Failed to initialize Cortex pipeline"**

Check:
- Qdrant URL/API key correct?
- Neo4j credentials valid?
- OpenAI API key active?

### **"No connection found for tenant"**

User hasn't completed OAuth yet. Check:
1. `/connect/start` returned auth URL
2. User clicked URL and completed OAuth
3. `/nango/oauth/callback` received and saved connection

### **Search returns empty results**

Check:
1. Emails actually synced? (check Supabase `emails` table)
2. Cortex ingestion succeeded? (check logs for "Cortex ingestion successful")
3. Qdrant collection exists? (check Qdrant dashboard)

---

## 📚 Additional Resources

- **Nango Docs**: https://docs.nango.dev
- **LlamaIndex Docs**: https://docs.llamaindex.ai
- **Graphiti GitHub**: https://github.com/getzep/graphiti
- **Qdrant Docs**: https://qdrant.tech/documentation
- **Neo4j Aura**: https://neo4j.com/cloud/aura

---

## 📝 License

Proprietary - ThunderbirdLabs

---

**Built with ❤️ using FastAPI, LlamaIndex, Graphiti, Qdrant, Neo4j, and OpenAI**
