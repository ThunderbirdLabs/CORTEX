# 🚀 Cortex Implementation Guide for Client Deployment

**Version:** v0.4.5
**Last Updated:** 2025
**For:** On-premise client deployment where client owns all infrastructure

---

## 📋 Table of Contents

1. [Overview - What You're Setting Up](#overview)
2. [Prerequisites Checklist](#prerequisites)
3. [Part 1: Create Cloud Accounts](#part-1-create-cloud-accounts)
4. [Part 2: Configure Environment Variables](#part-2-configure-environment-variables)
5. [Part 3: Database Setup](#part-3-database-setup)
6. [Part 4: Verify Installation](#part-4-verify-installation)
7. [Part 5: Customization Options](#part-5-customization-options)
8. [Troubleshooting](#troubleshooting)

---

## Overview - What You're Setting Up

**Cortex is an AI-powered knowledge system that:**
- Reads all company emails and documents
- Extracts people, companies, deals, and relationships (Knowledge Graph)
- Enables natural language search over all company data
- Answers questions like "What did Sarah say about the Q4 report?" with sources

**The Stack (All Client-Owned):**
```
┌─────────────────────────────────────────────────┐
│  SUPABASE (PostgreSQL)                          │
│  → Stores all emails, documents, user data      │
└─────────────────┬───────────────────────────────┘
                  │
    ┌─────────────┴─────────────┐
    │                           │
┌───▼──────────┐      ┌────────▼─────────┐
│ QDRANT       │      │ NEO4J AURA       │
│ Vector Store │      │ Knowledge Graph  │
│              │      │                  │
│ • Text chunks│      │ • People         │
│ • Embeddings │      │ • Companies      │
│ • Fast search│      │ • Relationships  │
└──────────────┘      └──────────────────┘
                  ▲
                  │
         ┌────────┴────────┐
         │ OPENAI API      │
         │ • Embeddings    │
         │ • LLM (GPT-4o)  │
         └─────────────────┘
```

**What Each Service Does:**

- **Supabase** = The main database. Stores every email, document, and user in raw form
- **Qdrant** = Fast semantic search. Finds relevant text chunks based on meaning (not just keywords)
- **Neo4j** = Knowledge Graph. Understands relationships like "Sarah works at Acme Corp" and "sent email about Q4"
- **OpenAI** = The AI brain. Converts text to numbers (embeddings) and generates answers

**Key Concept:** The client owns EVERYTHING. You're creating accounts in their name with their credit cards. We never touch their data.

---

## Prerequisites

Before you start, make sure the client has:

- [ ] **Credit card** (for Neo4j, Qdrant, OpenAI accounts)
- [ ] **Email address** (preferably company email for account creation)
- [ ] **Company name** and basic info
- [ ] **This codebase cloned** to client's server/computer
- [ ] **Python 3.13+** installed
- [ ] **PostgreSQL client** (for Supabase database inspection)

**Your role:** Walk the client through creating these accounts OR create them together while they watch. Hand over all credentials immediately after.

---

## Part 1: Create Cloud Accounts

### 1.1 Supabase (PostgreSQL Database)

**What it does:** Main database that stores all emails, documents, and user data in raw form.

**Setup Steps:**

1. Go to https://supabase.com/
2. Click **"Start your project"**
3. Sign up with client's email
4. Click **"New Project"**
   - Organization: Create new (use company name)
   - Project name: `cortex-production` or `[company-name]-cortex`
   - Database Password: Generate strong password (save it!)
   - Region: Choose closest to client's location
   - Pricing Plan: **Pro ($25/month)** recommended for production
5. Wait 2-3 minutes for database to provision

**Get These Values:**

```bash
# On Supabase dashboard, go to Project Settings → API
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # "anon public" key

# Go to Project Settings → API → "service_role" key (expand to see)
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Secret! Don't share

# Go to Project Settings → Database → Connection String → URI
SUPABASE_DB_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
```

**Important:** The `SUPABASE_SERVICE_KEY` has admin privileges. Keep it secret!

---

### 1.2 Qdrant (Vector Database)

**What it does:** Stores text chunks and embeddings for fast semantic search. Think of it like Google for the company's documents - finds relevant content based on meaning, not just keywords.

**Setup Steps:**

1. Go to https://cloud.qdrant.io/
2. Click **"Get Started"** or **"Sign Up"**
3. Sign up with client's email (or Google/GitHub)
4. Click **"Create Cluster"**
   - Cluster name: `cortex-vectors` or `[company-name]-vectors`
   - Cloud provider: **AWS** (recommended)
   - Region: **Same as Supabase** (for low latency)
   - Cluster configuration:
     - **1 GB RAM / 0.5 vCPU** ($25/month) - Good for 100k documents
     - **2 GB RAM / 1 vCPU** ($95/month) - Good for 500k+ documents
5. Click **"Create"** and wait 2-3 minutes

**Get These Values:**

```bash
# After cluster is created, click on cluster name
# You'll see "Cluster URL" at the top
QDRANT_URL=https://xxxxx-xxxxx-xxxxx.us-east.aws.cloud.qdrant.io:6333

# Click "API Keys" tab → "Create API Key"
# Give it a name like "cortex-api-key"
QDRANT_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Collection name (this is created automatically by code, just set the env var)
QDRANT_COLLECTION_NAME=cortex_documents
```

**Note:** The collection `cortex_documents` will be created automatically when you first ingest data. No manual setup needed!

---

### 1.3 Neo4j Aura (Knowledge Graph)

**What it does:** Stores the "brain" - understanding of people, companies, relationships. Answers questions like "Who works where?" and "What deals is Sarah working on?"

**Setup Steps:**

1. Go to https://neo4j.com/cloud/aura-free/
2. Click **"Start Free"** or **"Sign Up"**
3. Sign up with client's email
4. Click **"New Instance"**
   - Instance name: `cortex-graph` or `[company-name]-graph`
   - Region: **Same as other services**
   - Instance size:
     - **Free tier** (good for testing, ~200k nodes)
     - **Professional ($65/month)** - 8GB memory, 1M+ nodes (recommended for production)
5. Click **"Create"**
6. **IMPORTANT:** Save the auto-generated password! It's shown only once!

**Get These Values:**

```bash
# After instance is created, click "View Instance"
# Connection URI is shown at top
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io

# Username is always "neo4j"
NEO4J_USER=neo4j

# Password was shown during creation (if you lost it, you can reset it)
NEO4J_PASSWORD=xxxxxxxxxxxxx
```

**Pro Tip:** Click "Open with Neo4j Browser" to visualize the knowledge graph later!

---

### 1.4 OpenAI (LLM & Embeddings)

**What it does:**
- **Embeddings** = Converts text into numbers that computers understand (for Qdrant search)
- **LLM (GPT-4o-mini)** = Reads documents, extracts entities, answers questions

**Setup Steps:**

1. Go to https://platform.openai.com/
2. Sign up with client's email
3. Go to **"API Keys"** (https://platform.openai.com/api-keys)
4. Click **"Create new secret key"**
   - Name: `cortex-production`
   - Permissions: **All** (default)
5. Copy the key immediately (only shown once!)

**Get This Value:**

```bash
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Cost Estimation:**
- Embeddings: ~$0.02 per 1,000 documents
- Entity extraction: ~$0.10 per 1,000 documents
- Queries: ~$0.001 per question

**Example:** 10,000 emails = ~$1.20 one-time ingestion + ~$0.10/day for queries

**Set Usage Limits:**
1. Go to **Settings → Limits**
2. Set monthly budget (e.g., $50/month) to avoid surprises

---

### 1.5 Nango (OAuth Management) - Optional

**What it does:** Manages OAuth connections for Gmail, Outlook, Google Drive. Required if client wants to sync emails/documents automatically.

**Setup Steps:**

1. Go to https://www.nango.dev/
2. Click **"Sign Up"**
3. Create account with client's email
4. Follow their setup guide for Gmail/Outlook/Drive integrations
5. Get your **Secret Key**

**Get This Value:**

```bash
NANGO_SECRET=nango_secret_xxxxxxxxxxxxxxxxxxxxx

# Provider keys (created in Nango dashboard)
NANGO_PROVIDER_KEY_GMAIL=gmail-connector
NANGO_PROVIDER_KEY_OUTLOOK=outlook-connector
```

**Note:** Skip this if client is only uploading files manually (not syncing email/drive).

---

## Part 2: Configure Environment Variables

### 2.1 Copy Example Environment File

```bash
cd /path/to/cortex
cp .env.example .env
```

### 2.2 Fill In All Values

Open `.env` in a text editor and fill in ALL the values you collected:

```bash
# ============================================
# SERVER CONFIGURATION
# ============================================
ENVIRONMENT=production
PORT=8080

# ============================================
# SUPABASE (Main Database)
# ============================================
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_DB_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
DATABASE_URL=postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres

# ============================================
# QDRANT (Vector Database)
# ============================================
QDRANT_URL=https://xxxxx.cloud.qdrant.io:6333
QDRANT_API_KEY=xxxxxxxxxxxxxxxxxxxxx
QDRANT_COLLECTION_NAME=cortex_documents

# ============================================
# NEO4J (Knowledge Graph)
# ============================================
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USER=neo4j
NEO4J_PASSWORD=xxxxxxxxxxxxx

# ============================================
# OPENAI (AI Brain)
# ============================================
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxx

# ============================================
# NANGO (OAuth - Optional)
# ============================================
NANGO_SECRET=nango_secret_xxxxxxxxxxxxx
NANGO_PROVIDER_KEY_GMAIL=gmail-connector
NANGO_PROVIDER_KEY_OUTLOOK=outlook-connector
NANGO_CONNECTION_ID_GMAIL=  # Set after OAuth flow
NANGO_CONNECTION_ID_OUTLOOK=  # Set after OAuth flow

# ============================================
# API SECURITY
# ============================================
CORTEX_API_KEY=change-this-to-random-string-xyz123
```

**Generate Random API Key:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Part 3: Database Setup

### 3.1 Create Supabase Tables

**What we're creating:**
- `documents` - Stores all emails, documents, files (main storage)
- `chats` - Chat history
- `chat_messages` - Individual chat messages
- `connections` - OAuth connections (Gmail/Drive/Outlook)
- `user_cursors`, `gmail_cursors` - For incremental email sync
- `emails` - Original emails (optional, before normalization)

**Steps:**

1. Go to Supabase dashboard → **SQL Editor**
2. Click **"New Query"**
3. **Copy the ENTIRE SQL block below** (all 7 tables!)
4. Paste and click **"Run"**

**⚠️ IMPORTANT: Copy ALL of this SQL - it creates 7 tables at once:**

```sql
-- ============================================
-- DOCUMENTS TABLE (Main Storage)
-- ============================================
CREATE TABLE IF NOT EXISTS documents (
  id BIGSERIAL PRIMARY KEY,
  tenant_id TEXT NOT NULL,                    -- User/company ID (isolation)
  source TEXT NOT NULL,                       -- "gmail", "googledrive", "upload", etc.
  source_id TEXT NOT NULL,                    -- Original ID from source system
  document_type TEXT NOT NULL,                -- "email", "googledoc", "pdf", etc.
  title TEXT NOT NULL,                        -- Email subject or document name
  content TEXT NOT NULL,                      -- Full text content
  content_hash TEXT,                          -- SHA256 hash for deduplication
  raw_data JSONB,                             -- Original JSON from source
  metadata JSONB,                             -- Extra metadata (tags, etc.)
  file_type TEXT,                             -- MIME type for files
  file_size BIGINT,                           -- File size in bytes
  source_created_at TIMESTAMPTZ,              -- When created in source system
  source_modified_at TIMESTAMPTZ,             -- When last modified in source
  ingested_at TIMESTAMPTZ DEFAULT NOW(),      -- When ingested into Cortex

  -- Prevent duplicate ingestion from same source
  UNIQUE(tenant_id, source, source_id)
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(tenant_id, content_hash, source);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(tenant_id, source);
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(source_created_at DESC);

-- ============================================
-- CHATS TABLE (Chat History)
-- ============================================
CREATE TABLE IF NOT EXISTS chats (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  company_id TEXT NOT NULL,                   -- Tenant/company ID
  user_email TEXT NOT NULL,                   -- User who created chat
  title TEXT,                                 -- Chat title (first few words)
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_email);
CREATE INDEX IF NOT EXISTS idx_chats_company ON chats(company_id);

-- ============================================
-- CHAT MESSAGES TABLE
-- ============================================
CREATE TABLE IF NOT EXISTS chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id UUID NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
  role TEXT NOT NULL,                         -- "user" or "assistant"
  content TEXT NOT NULL,                      -- Message text
  sources JSONB,                              -- Source documents (for assistant)
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_chat ON chat_messages(chat_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at);

-- ============================================
-- ROW LEVEL SECURITY (Optional but Recommended)
-- ============================================
-- Enable RLS for multi-tenant isolation
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chats ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own tenant's data
CREATE POLICY documents_isolation ON documents
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant', TRUE));

CREATE POLICY chats_isolation ON chats
  FOR ALL
  USING (company_id = current_setting('app.current_tenant', TRUE));

-- ============================================
-- CONNECTIONS TABLE (OAuth - Gmail/Drive/Outlook)
-- ============================================
CREATE TABLE IF NOT EXISTS connections (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider_key TEXT NOT NULL,  -- 'gmail', 'google-drive', 'outlook'
    connection_id TEXT NOT NULL,  -- Nango connection ID
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, provider_key)
);

CREATE INDEX IF NOT EXISTS idx_connections_tenant ON connections(tenant_id);

-- ============================================
-- CURSOR TABLES (For incremental sync)
-- ============================================
-- Outlook delta links
CREATE TABLE IF NOT EXISTS user_cursors (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider_key TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_principal_name TEXT NOT NULL,
    delta_link TEXT NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, provider_key, user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_cursors_tenant ON user_cursors(tenant_id);

-- Gmail cursors
CREATE TABLE IF NOT EXISTS gmail_cursors (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider_key TEXT NOT NULL,
    cursor TEXT NOT NULL,
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, provider_key)
);

CREATE INDEX IF NOT EXISTS idx_gmail_cursors_tenant ON gmail_cursors(tenant_id);

-- ============================================
-- EMAILS TABLE (Original emails - optional)
-- ============================================
CREATE TABLE IF NOT EXISTS emails (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_principal_name TEXT NOT NULL,
    message_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('outlook', 'gmail')),
    subject TEXT,
    sender_name TEXT,
    sender_address TEXT,
    to_addresses JSONB,
    received_datetime TIMESTAMPTZ,
    web_link TEXT,
    full_body TEXT,
    change_key TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, source, message_id)
);

CREATE INDEX IF NOT EXISTS idx_emails_tenant ON emails(tenant_id);
CREATE INDEX IF NOT EXISTS idx_emails_source ON emails(source);
CREATE INDEX IF NOT EXISTS idx_emails_received ON emails(received_datetime DESC);
```

### 3.2 Verify Tables Created

Run this query to verify ALL 7 tables were created:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

**You should see these 7 tables:**
- `chat_messages`
- `chats`
- `connections`
- `documents`
- `emails`
- `gmail_cursors`
- `user_cursors`

If any are missing, re-run the SQL from 3.1!

---

## Part 4: Verify Installation

### 4.1 Install Python Dependencies

```bash
cd /path/to/cortex
pip install -r requirements.txt
```

### 4.2 Test Environment Variables

```bash
python3 -c "
from dotenv import load_dotenv
import os
load_dotenv()

required_vars = [
    'SUPABASE_URL', 'SUPABASE_SERVICE_KEY',
    'QDRANT_URL', 'QDRANT_API_KEY',
    'NEO4J_URI', 'NEO4J_PASSWORD',
    'OPENAI_API_KEY'
]

missing = [var for var in required_vars if not os.getenv(var)]
if missing:
    print('❌ Missing required variables:', missing)
else:
    print('✅ All required environment variables set!')
"
```

### 4.3 Test Database Connections

```bash
python3 -c "
from supabase import create_client
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# Test Supabase
try:
    sb = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))
    result = sb.table('documents').select('id').limit(1).execute()
    print('✅ Supabase connected')
except Exception as e:
    print(f'❌ Supabase error: {e}')

# Test Qdrant
try:
    qd = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY'))
    collections = qd.get_collections()
    print('✅ Qdrant connected')
except Exception as e:
    print(f'❌ Qdrant error: {e}')

# Test Neo4j
try:
    driver = GraphDatabase.driver(
        os.getenv('NEO4J_URI'),
        auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD'))
    )
    with driver.session() as session:
        result = session.run('RETURN 1')
    print('✅ Neo4j connected')
    driver.close()
except Exception as e:
    print(f'❌ Neo4j error: {e}')

# Test OpenAI
try:
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    models = client.models.list()
    print('✅ OpenAI connected')
except Exception as e:
    print(f'❌ OpenAI error: {e}')
"
```

All 4 should show ✅!

### 4.4 Start the Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

**Expected output:**
```
INFO:     🚀 Initializing Hybrid Query Engine...
INFO:     ✅ Qdrant Vector Store: cortex_documents
INFO:     ✅ VectorStoreIndex created for semantic search
INFO:     ✅ Neo4j Graph Store: neo4j+s://xxxxx.databases.neo4j.io
INFO:     ✅ PropertyGraphIndex created for graph queries
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

### 4.5 Test Health Endpoint

Open browser: http://localhost:8080/health

Should see:
```json
{
  "status": "healthy",
  "timestamp": "2025-10-21T12:34:56Z"
}
```

**🎉 If all tests pass, you're ready to ingest data!**

---

## Part 5: Customization Options

This section covers how to customize Cortex for different client needs.

### 5.1 Knowledge Graph Schema (Entities & Relationships)

**File:** `app/services/ingestion/llamaindex/config.py`

**What is this?** The "brain structure" - defines what types of things (entities) and connections (relationships) the AI extracts from documents.

---

## ⚠️ CRITICAL: Schema Update Guidelines

**If you modify the schema (add/remove entities or relationships), you MUST update 4 locations to keep everything in sync:**

### Location 1: Entity & Relationship Lists
**File:** `app/services/ingestion/llamaindex/config.py` (lines 57-86)
- `POSSIBLE_ENTITIES` - List of entity types
- `POSSIBLE_RELATIONS` - List of relationship types

### Location 2: Validation Schema (Triplets)
**File:** `app/services/ingestion/llamaindex/config.py` (lines 91-229)
- `KG_VALIDATION_SCHEMA` - Defines which entities can connect with which relationships
- **Every new entity/relationship MUST have validation rules here**

### Location 3: Extraction Prompt
**File:** `app/services/ingestion/llamaindex/ingestion_pipeline.py` (lines 104-190)
- The `extraction_prompt` teaches the LLM what entities/relationships mean
- **Update the entity descriptions (lines 125-136)**
- **Update the relationship descriptions (lines 138-173)**
- **Update entity count comment** (line 125: "ENTITY TYPES (11 total)")
- **Update relationship count comment** (line 138: "RELATIONSHIP TYPES (26 total)")

### Location 4: Legacy Type Definitions (Optional)
**File:** `app/services/ingestion/llamaindex/config.py` (lines 232-244)
- `ENTITIES` Literal type
- `RELATIONS` Literal type
- These are for backward compatibility - update if using type hints elsewhere

---

## 🤖 Recommended Workflow for Schema Changes

**IMPORTANT:** When using Claude Code to make schema changes, use this exact prompt:

```
I need to update the knowledge graph schema. Please:

1. Read the CURRENT schema from:
   - app/services/ingestion/llamaindex/config.py (lines 57-229)
   - app/services/ingestion/llamaindex/ingestion_pipeline.py (lines 104-190)

2. Make the following changes: [describe your changes]

3. Verify consistency across ALL 4 locations:
   - POSSIBLE_ENTITIES and POSSIBLE_RELATIONS lists
   - KG_VALIDATION_SCHEMA (all triplets)
   - extraction_prompt (entity/relationship descriptions + counts)
   - Legacy Literal types

4. Show me a summary of all changes before applying them.

5. After changes, verify the schema makes logical sense:
   - Every entity should have at least one incoming and one outgoing relationship
   - Relationship names should be clear and unambiguous
   - Validation schema should cover the most common use cases
```

**Example Schema Change Request:**

```
Add a "PRODUCT" entity type for tracking products manufactured by the company.

Products should:
- Be MANUFACTURED_BY companies
- CONTAIN materials
- Be mentioned in deals, documents, emails
- Be ASSIGNED_TO people (product managers)

Please update all 4 locations and show me what you changed.
```

---

## ✅ Schema Validation Checklist

After making schema changes, verify:

- [ ] Entity count matches in `extraction_prompt` comment
- [ ] Relationship count matches in `extraction_prompt` comment
- [ ] Every entity in `POSSIBLE_ENTITIES` appears in `KG_VALIDATION_SCHEMA` at least once
- [ ] Every relationship in `POSSIBLE_RELATIONS` appears in `KG_VALIDATION_SCHEMA` at least once
- [ ] Every entity/relationship is described in `extraction_prompt`
- [ ] Logical consistency: Can PERSON really PAID_BY PAYMENT? (check direction)
- [ ] No orphan entities (entities with no valid connections)

**Quick Validation Script:**

```python
# Run this to verify schema consistency
python3 << 'EOF'
from app.services.ingestion.llamaindex.config import (
    POSSIBLE_ENTITIES, POSSIBLE_RELATIONS, KG_VALIDATION_SCHEMA
)

print(f"Entities defined: {len(POSSIBLE_ENTITIES)}")
print(f"Relations defined: {len(POSSIBLE_RELATIONS)}")
print(f"Validation triplets: {len(KG_VALIDATION_SCHEMA)}")

# Check all entities appear in validation schema
entities_in_schema = set()
for head, rel, tail in KG_VALIDATION_SCHEMA:
    entities_in_schema.add(head)
    entities_in_schema.add(tail)

missing_entities = set(POSSIBLE_ENTITIES) - entities_in_schema
if missing_entities:
    print(f"⚠️  Entities missing from validation schema: {missing_entities}")
else:
    print("✅ All entities have validation rules")

# Check all relations appear in validation schema
relations_in_schema = set(rel for _, rel, _ in KG_VALIDATION_SCHEMA)
missing_relations = set(POSSIBLE_RELATIONS) - relations_in_schema
if missing_relations:
    print(f"⚠️  Relations missing from validation schema: {missing_relations}")
else:
    print("✅ All relations have validation rules")

# Check for undefined entities/relations in validation schema
undefined_entities = entities_in_schema - set(POSSIBLE_ENTITIES)
if undefined_entities:
    print(f"⚠️  Validation schema uses undefined entities: {undefined_entities}")

undefined_relations = relations_in_schema - set(POSSIBLE_RELATIONS)
if undefined_relations:
    print(f"⚠️  Validation schema uses undefined relations: {undefined_relations}")

print("\n✅ Schema validation complete!")
EOF
```

---

## 🗄️ After Schema Changes: Database Cleanup

**Important:** Changing the schema does NOT automatically update existing data in Neo4j!

**Option 1: Fresh Start (Recommended for Major Changes)**
```bash
# Clear Neo4j database
python3 << 'EOF'
from neo4j import GraphDatabase
import os

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session(database="neo4j") as session:
    # Delete all nodes and relationships
    session.run("MATCH (n) DETACH DELETE n")
    print("✅ Neo4j cleared - ready for re-ingestion")

driver.close()
EOF

# Re-ingest all documents
python3 scripts/utilities/ingest_from_documents_table.py
```

**Option 2: Incremental Update (For Minor Changes)**
- Old entities/relationships remain unchanged
- New schema only applies to newly ingested documents
- May cause inconsistency - use with caution

---

## 📊 CURRENT SCHEMA (As Deployed in Code)

### Entity Types (11 Total)

These are the ONLY entity types that will be extracted:

```python
POSSIBLE_ENTITIES = [
    "PERSON",      # Anyone: employees, customers, vendors, contacts
    "COMPANY",     # Any business: clients, suppliers, competitors, departments
    "EMAIL",       # Email messages (extracted from content, not document nodes)
    "DOCUMENT",    # Files: contracts, invoices, reports, PDFs (extracted from content)
    "DEAL",        # Opportunities, sales, orders, quotes
    "TASK",        # Action items, follow-ups, requests
    "MEETING",     # Calls, meetings, appointments
    "PAYMENT",     # Invoices, payments, expenses, POs
    "TOPIC",       # Subjects, projects, products, issues
    "EVENT",       # Catch-all: conferences, launches, deadlines, milestones
    "MATERIAL"     # Raw materials, supplies, components, parts used in manufacturing/operations
]
```

### Relationship Types (26 Total)

These are the ONLY relationship types that will be extracted:

```python
POSSIBLE_RELATIONS = [
    # Who did what
    "SENT_BY", "SENT_TO", "CREATED_BY", "ASSIGNED_TO", "ATTENDED_BY",
    # Organization
    "WORKS_FOR", "WORKS_WITH", "REPORTS_TO", "FOUNDED", "MANAGES",
    # Business relationships
    "CLIENT_OF", "VENDOR_OF", "SUPPLIES",
    # Content connections
    "ABOUT", "MENTIONS", "RELATES_TO", "ATTACHED_TO",
    # Status & actions
    "REQUIRES", "FOLLOWS_UP", "RESOLVES", "USED_IN",
    # Financial
    "PAID_BY", "PAID_TO"
]
```

### Validation Schema (All 139 Allowed Triplets)

This defines EXACTLY which entities can connect with which relationships. Format: `(HEAD_ENTITY, RELATIONSHIP, TAIL_ENTITY)`

```python
KG_VALIDATION_SCHEMA = [
    # ============================================
    # EMPLOYMENT & ORGANIZATION (PERSON relationships)
    # ============================================
    ("PERSON", "WORKS_FOR", "COMPANY"),
    ("PERSON", "FOUNDED", "COMPANY"),
    ("PERSON", "WORKS_WITH", "PERSON"),
    ("PERSON", "REPORTS_TO", "PERSON"),
    ("PERSON", "MANAGES", "COMPANY"),
    ("PERSON", "CLIENT_OF", "COMPANY"),
    ("PERSON", "VENDOR_OF", "COMPANY"),

    # ============================================
    # COMPANY RELATIONSHIPS (B2B)
    # ============================================
    ("COMPANY", "CLIENT_OF", "COMPANY"),
    ("COMPANY", "VENDOR_OF", "COMPANY"),
    ("COMPANY", "WORKS_WITH", "COMPANY"),

    # ============================================
    # COMMUNICATION (Who sent what)
    # ============================================
    ("EMAIL", "SENT_BY", "PERSON"),
    ("EMAIL", "SENT_BY", "COMPANY"),
    ("EMAIL", "SENT_TO", "PERSON"),
    ("EMAIL", "SENT_TO", "COMPANY"),
    ("DOCUMENT", "SENT_BY", "PERSON"),
    ("DOCUMENT", "SENT_BY", "COMPANY"),
    ("DOCUMENT", "SENT_TO", "PERSON"),
    ("DOCUMENT", "SENT_TO", "COMPANY"),

    # ============================================
    # CREATION & AUTHORSHIP
    # ============================================
    ("DOCUMENT", "CREATED_BY", "PERSON"),
    ("DEAL", "CREATED_BY", "PERSON"),
    ("TASK", "CREATED_BY", "PERSON"),
    ("EVENT", "CREATED_BY", "PERSON"),
    ("MEETING", "CREATED_BY", "PERSON"),

    # ============================================
    # ASSIGNMENT & RESPONSIBILITY
    # ============================================
    ("DEAL", "ASSIGNED_TO", "PERSON"),
    ("TASK", "ASSIGNED_TO", "PERSON"),

    # ============================================
    # ATTENDANCE
    # ============================================
    ("MEETING", "ATTENDED_BY", "PERSON"),
    ("EVENT", "ATTENDED_BY", "PERSON"),

    # ============================================
    # FINANCIAL
    # ============================================
    ("PERSON", "PAID_BY", "PAYMENT"),
    ("COMPANY", "PAID_BY", "PAYMENT"),
    ("PERSON", "PAID_TO", "PAYMENT"),
    ("COMPANY", "PAID_TO", "PAYMENT"),

    # ============================================
    # CONTENT RELATIONSHIPS - EMAILS
    # ============================================
    ("EMAIL", "ABOUT", "TOPIC"),
    ("EMAIL", "ABOUT", "PERSON"),
    ("EMAIL", "ABOUT", "COMPANY"),
    ("EMAIL", "ABOUT", "DEAL"),
    ("EMAIL", "MENTIONS", "PERSON"),
    ("EMAIL", "MENTIONS", "COMPANY"),
    ("EMAIL", "MENTIONS", "TOPIC"),
    ("EMAIL", "RELATES_TO", "TOPIC"),
    ("EMAIL", "RELATES_TO", "DEAL"),
    ("EMAIL", "RELATES_TO", "TASK"),

    # ============================================
    # CONTENT RELATIONSHIPS - DOCUMENTS
    # ============================================
    ("DOCUMENT", "ABOUT", "TOPIC"),
    ("DOCUMENT", "ABOUT", "PERSON"),
    ("DOCUMENT", "ABOUT", "COMPANY"),
    ("DOCUMENT", "MENTIONS", "PERSON"),
    ("DOCUMENT", "MENTIONS", "COMPANY"),
    ("DOCUMENT", "MENTIONS", "TOPIC"),
    ("DOCUMENT", "RELATES_TO", "TOPIC"),
    ("DOCUMENT", "RELATES_TO", "DEAL"),

    # ============================================
    # CONTENT RELATIONSHIPS - DEALS
    # ============================================
    ("DEAL", "ABOUT", "TOPIC"),
    ("DEAL", "ABOUT", "COMPANY"),
    ("DEAL", "MENTIONS", "PERSON"),
    ("DEAL", "MENTIONS", "COMPANY"),
    ("DEAL", "RELATES_TO", "TOPIC"),
    ("DEAL", "SENT_BY", "COMPANY"),
    ("DEAL", "SENT_TO", "COMPANY"),

    # ============================================
    # CONTENT RELATIONSHIPS - TASKS
    # ============================================
    ("TASK", "ABOUT", "TOPIC"),
    ("TASK", "ABOUT", "PERSON"),
    ("TASK", "RELATES_TO", "TOPIC"),
    ("TASK", "RELATES_TO", "DEAL"),

    # ============================================
    # CONTENT RELATIONSHIPS - MEETINGS
    # ============================================
    ("MEETING", "ABOUT", "TOPIC"),
    ("MEETING", "ABOUT", "DEAL"),
    ("MEETING", "MENTIONS", "PERSON"),
    ("MEETING", "MENTIONS", "COMPANY"),
    ("MEETING", "RELATES_TO", "TOPIC"),
    ("MEETING", "RELATES_TO", "DEAL"),

    # ============================================
    # CONTENT RELATIONSHIPS - EVENTS
    # ============================================
    ("EVENT", "ABOUT", "TOPIC"),
    ("EVENT", "ABOUT", "COMPANY"),
    ("EVENT", "ABOUT", "DEAL"),
    ("EVENT", "MENTIONS", "PERSON"),
    ("EVENT", "RELATES_TO", "TOPIC"),
    ("EVENT", "RELATES_TO", "DEAL"),

    # ============================================
    # CONTENT RELATIONSHIPS - PAYMENTS
    # ============================================
    ("PAYMENT", "ABOUT", "DEAL"),
    ("PAYMENT", "RELATES_TO", "TOPIC"),

    # ============================================
    # TOPIC CONNECTIONS
    # ============================================
    ("TOPIC", "RELATES_TO", "TOPIC"),

    # ============================================
    # MATERIALS (Manufacturing-specific)
    # ============================================
    ("MATERIAL", "RELATES_TO", "TOPIC"),
    ("MATERIAL", "USED_IN", "DEAL"),
    ("DOCUMENT", "MENTIONS", "MATERIAL"),
    ("DOCUMENT", "ABOUT", "MATERIAL"),
    ("EMAIL", "MENTIONS", "MATERIAL"),
    ("TASK", "ABOUT", "MATERIAL"),
    ("TASK", "REQUIRES", "MATERIAL"),
    ("DEAL", "ABOUT", "MATERIAL"),
    ("DEAL", "REQUIRES", "MATERIAL"),
    ("MEETING", "ABOUT", "MATERIAL"),
    ("PAYMENT", "RELATES_TO", "MATERIAL"),
    ("COMPANY", "VENDOR_OF", "MATERIAL"),
    ("COMPANY", "SUPPLIES", "MATERIAL"),
    ("PERSON", "MANAGES", "MATERIAL"),

    # ============================================
    # ATTACHMENTS
    # ============================================
    ("EMAIL", "ATTACHED_TO", "DOCUMENT"),
    ("DOCUMENT", "ATTACHED_TO", "DOCUMENT"),

    # ============================================
    # WORKFLOW & DEPENDENCIES
    # ============================================
    ("TASK", "REQUIRES", "TASK"),
    ("TASK", "REQUIRES", "DOCUMENT"),
    ("DEAL", "REQUIRES", "TASK"),
    ("DEAL", "REQUIRES", "DOCUMENT"),
    ("EMAIL", "FOLLOWS_UP", "EMAIL"),
    ("EMAIL", "FOLLOWS_UP", "MEETING"),
    ("DEAL", "FOLLOWS_UP", "MEETING"),
    ("MEETING", "FOLLOWS_UP", "MEETING"),
    ("EMAIL", "RESOLVES", "TASK"),
    ("TASK", "RESOLVES", "TASK"),
]
```

**Total:** 139 validated relationship patterns

---

**How to Customize for Different Industries:**

#### Example 1: Law Firm
```python
POSSIBLE_ENTITIES = [
    "PERSON",      # Lawyers, clients, witnesses
    "COMPANY",     # Clients, opposing counsel
    "CASE",        # Legal cases (replaces DEAL)
    "DOCUMENT",    # Contracts, briefs, evidence
    "HEARING",     # Court dates (replaces MEETING)
    "STATUTE",     # Laws, regulations (replaces MATERIAL)
    "TOPIC",       # Legal issues
    "PAYMENT",     # Billing
    "EMAIL",
    "TASK",
    "EVENT"
]

# Add relationships like:
"REPRESENTS",     # Lawyer represents Client in Case
"OPPOSING",       # Company opposing Company in Case
"CITES",          # Document cites Statute
"FILED_IN",       # Document filed in Case
```

#### Example 2: Real Estate
```python
POSSIBLE_ENTITIES = [
    "PERSON",      # Agents, buyers, sellers
    "COMPANY",     # Brokerages, banks
    "PROPERTY",    # Buildings, land (replaces MATERIAL)
    "LISTING",     # Properties for sale (replaces DEAL)
    "SHOWING",     # Property tours (replaces MEETING)
    "OFFER",       # Purchase offers (new)
    "DOCUMENT",    # Contracts, disclosures
    "PAYMENT",     # Deposits, commissions
    "EMAIL",
    "TASK",
    "TOPIC"
]

# Add relationships like:
"LISTED_BY",      # Property listed by Agent
"LOCATED_IN",     # Property located in City
"INTERESTED_IN",  # Person interested in Property
```

#### Example 3: Healthcare
```python
POSSIBLE_ENTITIES = [
    "PERSON",      # Patients, doctors, staff
    "PROVIDER",    # Hospitals, clinics (replaces COMPANY)
    "PATIENT",     # Specific patient entity (new)
    "APPOINTMENT", # Medical appointments (replaces MEETING)
    "PROCEDURE",   # Treatments, surgeries (replaces DEAL)
    "MEDICATION",  # Drugs, prescriptions (replaces MATERIAL)
    "DIAGNOSIS",   # Medical conditions (new)
    "DOCUMENT",    # Medical records, test results
    "PAYMENT",     # Billing, insurance
    "TASK"
]

# Add relationships like:
"TREATED_BY",     # Patient treated by Doctor
"DIAGNOSED_WITH", # Patient diagnosed with Condition
"PRESCRIBED",     # Doctor prescribed Medication
"SCHEDULED_AT",   # Appointment scheduled at Clinic
```

**Where to Add Custom Entities:**

1. Open `app/services/ingestion/llamaindex/config.py`
2. Edit `POSSIBLE_ENTITIES` list (lines 57-69)
3. Edit `POSSIBLE_RELATIONS` list (lines 73-86)
4. Edit `KG_VALIDATION_SCHEMA` (lines 91-229) - defines which entities can connect with which relationships

**Example - Adding "PRODUCT" entity:**

```python
# In config.py
POSSIBLE_ENTITIES = [
    # ... existing entities ...
    "PRODUCT"  # Add this
]

POSSIBLE_RELATIONS = [
    # ... existing relations ...
    "MANUFACTURED_BY",  # Add this
    "CONTAINS"          # Add this
]

# Add validation rules
KG_VALIDATION_SCHEMA = [
    # ... existing rules ...
    ("PRODUCT", "MANUFACTURED_BY", "COMPANY"),
    ("PRODUCT", "CONTAINS", "MATERIAL"),
    ("DEAL", "ABOUT", "PRODUCT"),
    ("DOCUMENT", "MENTIONS", "PRODUCT"),
]
```

**Update the extraction prompt** (lines 104-190) to guide the LLM:

```python
extraction_prompt = PromptTemplate(
    """You are extracting a knowledge graph for a CEO...

    ENTITY TYPES (12 total):  # Update count
    - PERSON: Any individual mentioned
    - COMPANY: Any organization
    - PRODUCT: Products manufactured or sold  # Add description
    - EMAIL: Specific emails referenced
    ...

    RELATIONSHIP TYPES (28 total):  # Update count
    ...
    - MANUFACTURED_BY: Product manufactured by Company  # Add examples
    - CONTAINS: Product contains Material
    ...
    """
)
```

---

### 5.2 Text Chunking Settings

**File:** `app/services/ingestion/llamaindex/config.py` **(Lines 253-254)**

**What is this?** Long documents are split into smaller "chunks" for efficient search. These settings control chunk size.

**Current Settings:**

```python
# Line 253
CHUNK_SIZE = 512        # Characters per chunk
CHUNK_OVERLAP = 50      # Characters that overlap between chunks
```

**How to Change:**
1. Open `app/services/ingestion/llamaindex/config.py`
2. Go to lines 253-254
3. Edit the values
4. Save and restart server
5. **Re-ingest documents** for changes to take effect (old chunks remain unchanged)

**How Chunk Size Affects Performance:**

| Chunk Size | Pros | Cons | Best For |
|------------|------|------|----------|
| **256** | Very precise search, low LLM cost | May lose context, more chunks to manage | Short documents (emails, tweets) |
| **512** (current) | Balanced precision & context | Default - works for most use cases | General business docs |
| **1024** | More context per chunk, fewer chunks | Higher LLM cost, less precise search | Long reports, articles |
| **2048** | Maximum context | Expensive, slow search | Technical manuals, books |

**When to Adjust:**

- **Increase to 1024** if client has long technical documents where context matters (research papers, legal contracts)
- **Decrease to 256** if client has short messages (Slack, Twitter, SMS logs)
- **Overlap:** Keep at 50 for continuity, increase to 100 for critical documents where breaking context is risky

**Example - Adjust for Legal Firm:**

```python
CHUNK_SIZE = 1024       # Legal docs need more context
CHUNK_OVERLAP = 100     # Don't break clauses mid-sentence
```

---

### 5.3 Entity Extraction Settings

**File:** `app/services/ingestion/llamaindex/ingestion_pipeline.py` **(Lines 195-203)**

**What is this?** Controls how many entities/relationships are extracted per chunk of text.

**Current Settings:**

```python
# Line 195 - SchemaLLMPathExtractor configuration
self.entity_extractor = SchemaLLMPathExtractor(
    llm=self.extraction_llm,
    max_triplets_per_chunk=10,  # Extract up to 10 entity relationships per chunk
    num_workers=4,              # Parallel processing (4 workers)
    possible_entities=POSSIBLE_ENTITIES,
    possible_relations=POSSIBLE_RELATIONS,
    kg_validation_schema=KG_VALIDATION_SCHEMA,
    strict=False,               # Allow schema flexibility
    extract_prompt=extraction_prompt
)
```

**How to Change:**
1. Open `app/services/ingestion/llamaindex/ingestion_pipeline.py`
2. Go to line 197 for `max_triplets_per_chunk`
3. Go to line 198 for `num_workers`
4. Go to line 202 for `strict` mode
5. Edit the values
6. Save and restart server
7. **Re-ingest documents** for changes to take effect

**What are "triplets"?**
A triplet is one relationship: `(Sarah, WORKS_FOR, Acme Corp)`

**How to Adjust:**

| Setting | Effect | When to Change |
|---------|--------|----------------|
| `max_triplets_per_chunk=5` | Fewer relationships extracted | Use for simple documents (emails, notes) - faster & cheaper |
| `max_triplets_per_chunk=10` (current) | Balanced extraction | Default - good for business docs |
| `max_triplets_per_chunk=20` | More relationships extracted | Use for dense documents (contracts, reports) - slower & more expensive |

**Cost Impact:**
- 5 triplets: ~$0.10 per 1,000 docs
- 10 triplets: ~$0.15 per 1,000 docs
- 20 triplets: ~$0.25 per 1,000 docs

**Parallel Processing (Line 198):**
```python
num_workers=4  # Default - uses 4 CPU cores
```
- Increase to 8 for faster ingestion (if server has 8+ cores)
- Decrease to 2 for low-resource servers
- **Check CPU cores:** `python3 -c "import os; print(f'CPU Cores: {os.cpu_count()}')"`
- **Recommendation:** Set to 50% of available cores for safety

**Schema Strictness (Line 202):**
```python
strict=False  # Allows LLM flexibility - may create relationships not in schema
strict=True   # Forces LLM to only use defined schema - more predictable but may miss creative connections
```

**Recommendation:** Keep `strict=False` unless client has very rigid data requirements.

**Verification After Changes:**
```bash
# Test that extraction still works
python3 -c "
from app.services.ingestion.llamaindex import UniversalIngestionPipeline
pipeline = UniversalIngestionPipeline()
print('✅ Entity extractor initialized successfully')
print(f'Max triplets: {pipeline.entity_extractor.max_triplets_per_chunk}')
print(f'Workers: {pipeline.entity_extractor.num_workers}')
print(f'Strict mode: {pipeline.entity_extractor.strict}')
"
```

---

### 5.4 LLM Models & Cost Optimization

**File:** `app/services/ingestion/llamaindex/config.py` **(Lines 39-49)**

**What is this?** Which OpenAI models to use for different tasks.

**Current Settings:**

```python
# Line 40 - LLM for entity extraction (runs on EVERY document during ingestion)
EXTRACTION_MODEL = "gpt-4o-mini"
EXTRACTION_TEMPERATURE = 0.0  # Deterministic

# Line 44 - LLM for queries and synthesis (runs on EVERY user question)
QUERY_MODEL = "gpt-4o-mini"
QUERY_TEMPERATURE = 0.3  # Slightly creative

# Line 48 - Embeddings (converts text to numbers)
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
```

**How to Change:**
1. Open `app/services/ingestion/llamaindex/config.py`
2. Edit lines 40, 41 for extraction model/temperature
3. Edit lines 44, 45 for query model/temperature
4. Edit lines 48, 49 for embedding model/dimensions
5. Save and restart server
6. **For extraction model changes:** Re-ingest documents
7. **For query model changes:** Immediate effect on new queries
8. **For embedding model changes:** Must clear Qdrant and re-ingest (dimensions must match!)

**Model Options & Trade-offs:**

#### For Entity Extraction:

| Model | Speed | Cost | Quality | Best For |
|-------|-------|------|---------|----------|
| `gpt-4o-mini` (current) | Fast | $0.15/1M tokens | Good | Most businesses |
| `gpt-4o` | Slow | $2.50/1M tokens | Excellent | Critical data, complex schemas |
| `gpt-3.5-turbo` | Very Fast | $0.50/1M tokens | Decent | High-volume, simple data |

#### For Query Answering:

| Model | Speed | Cost | Quality | Best For |
|-------|-------|------|---------|----------|
| `gpt-4o-mini` (current) | Fast | $0.15/1M tokens | Good | Daily queries |
| `gpt-4o` | Slow | $2.50/1M tokens | Excellent | Executive reports |
| `gpt-4-turbo` | Medium | $10/1M tokens | Best | Mission-critical answers |

#### For Embeddings:

| Model | Dimensions | Cost | Quality | Best For |
|-------|------------|------|---------|----------|
| `text-embedding-3-small` (current) | 1536 | $0.02/1M tokens | Good | Most use cases |
| `text-embedding-3-large` | 3072 | $0.13/1M tokens | Better | High-precision search |
| `ada-002` (legacy) | 1536 | $0.10/1M tokens | Good | Backward compatibility |

**Example - Premium Setup (High Quality):**

```python
EXTRACTION_MODEL = "gpt-4o"         # Best entity extraction
QUERY_MODEL = "gpt-4o"              # Best answers
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 3072
```

**Example - Budget Setup (High Volume):**

```python
EXTRACTION_MODEL = "gpt-3.5-turbo"  # Cheaper extraction
QUERY_MODEL = "gpt-4o-mini"         # Keep good query quality
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
```

**Temperature Settings (Lines 41, 45):**

```python
EXTRACTION_TEMPERATURE = 0.0  # Deterministic (no randomness)
QUERY_TEMPERATURE = 0.3       # Slightly creative
```

- `0.0` = Always same output (use for extraction)
- `0.3` = Slightly varied (use for conversational answers)
- `0.7` = More creative (use for brainstorming)
- `1.0` = Maximum creativity (rarely needed)

**Verification After Changes:**
```bash
# Verify models are valid and accessible
python3 -c "
from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Test extraction model
try:
    response = client.chat.completions.create(
        model='gpt-4o-mini',  # Change to your EXTRACTION_MODEL
        messages=[{'role': 'user', 'content': 'test'}],
        max_tokens=5
    )
    print('✅ Extraction model accessible')
except Exception as e:
    print(f'❌ Extraction model error: {e}')

# Test embedding model
try:
    response = client.embeddings.create(
        model='text-embedding-3-small',  # Change to your EMBEDDING_MODEL
        input='test'
    )
    print(f'✅ Embedding model accessible ({len(response.data[0].embedding)} dimensions)')
except Exception as e:
    print(f'❌ Embedding model error: {e}')
"
```

---

### 5.5 Search Settings

**File:** `app/services/ingestion/llamaindex/config.py` **(Line 257)**

**What is this?** How many results to retrieve from vector search.

**Current Settings:**

```python
# Line 257
SIMILARITY_TOP_K = 10  # Return top 10 most similar chunks
```

**How to Change:**
1. Open `app/services/ingestion/llamaindex/config.py`
2. Go to line 257
3. Edit the value
4. Save and restart server
5. **Immediate effect** on new queries (no re-ingestion needed)

**How to Adjust:**

| Value | Effect | Best For |
|-------|--------|----------|
| `5` | Fast, focused answers | Simple questions, low latency |
| `10` (current) | Balanced - good default | Most business queries |
| `20` | More context, slower | Complex multi-part questions |
| `50` | Maximum context | Research queries, comprehensive reports |

**Cost Impact:**
- Higher `top_k` = More text sent to LLM = Higher cost
- 10 chunks ≈ 5,000 tokens ≈ $0.0007 per query
- 50 chunks ≈ 25,000 tokens ≈ $0.0037 per query

---

### 5.6 Custom Prompts (Advanced)

**File:** `app/services/ingestion/llamaindex/query_engine.py`

**What is this?** The instructions given to the AI when answering questions. These prompts control the AI's personality, tone, and how it synthesizes information.

**⚠️ Important:** Prompt changes take effect immediately after server restart. No re-ingestion needed.

---

#### System Prompt (CEO Personality)

**Location:** `app/services/ingestion/llamaindex/query_engine.py` **(Lines 62-83)**

**What it controls:** The AI's overall personality and approach to answering questions.

**Current Prompt:**
```python
# Line 62 - System prompt for HybridQueryEngine LLM
system_prompt=(
    "You are an intelligent personal assistant to the CEO. "
    "You have access to the entire company's knowledge - "
    "all emails, documents, deals, activities, orders...\n"
    "Your job is to knock the CEO's socks off with how much you know."
)
```

**How to Change:**
1. Open `app/services/ingestion/llamaindex/query_engine.py`
2. Find the `self.llm = OpenAI(...)` initialization (line 58)
3. Edit the `system_prompt` parameter (lines 62-83)
4. Save and restart server
5. Test with a sample query to verify tone/personality

**Customization Examples:**

**For Legal Firm:**
```python
system_prompt=(
    "You are a legal research assistant. "
    "You have access to all case files, contracts, and correspondence. "
    "Always cite specific documents and remain factual. "
    "Flag any potential compliance issues or risks."
)
```

**For Sales Team:**
```python
system_prompt=(
    "You are a sales intelligence assistant. "
    "You track all deals, customer interactions, and opportunities. "
    "Always highlight revenue implications and next steps. "
    "Be proactive about identifying at-risk deals."
)
```

**For Customer Support:**
```python
system_prompt=(
    "You are a customer support assistant. "
    "You have access to all tickets, conversations, and product docs. "
    "Always prioritize customer satisfaction and quick resolution. "
    "Suggest relevant knowledge base articles."
)
```

#### Vector Search Prompt (Document Retrieval)

**Location:** `app/services/ingestion/llamaindex/query_engine.py` **(Lines 128-140)**

**What it controls:** How the AI reads and interprets retrieved text chunks from Qdrant

**How to Change:**
1. Open `app/services/ingestion/llamaindex/query_engine.py`
2. Find `vector_qa_prompt = PromptTemplate(...)` (line 128)
3. Edit the prompt text
4. Save and restart server

**Current Focus:** Cite sources by title, quote meaningful content only

**Customization Example - More Formal:**
```python
vector_qa_prompt = PromptTemplate(
    "Context information from documents:\n"
    "{context_str}\n\n"
    "Given the context, provide a detailed, formal response. "
    "Include document references in footnote format. "
    "Use professional business language.\n\n"
    "Question: {query_str}\n"
    "Answer: "
)
```

#### Graph Search Prompt (Relationship Retrieval)

**Location:** `app/services/ingestion/llamaindex/query_engine.py` **(Lines 142-153)**

**What it controls:** How the AI interprets knowledge graph data (entities and relationships from Neo4j)

**How to Change:**
1. Open `app/services/ingestion/llamaindex/query_engine.py`
2. Find `graph_qa_prompt = PromptTemplate(...)` (line 142)
3. Edit the prompt text
4. Save and restart server

**Current Focus:** Natural language, hide technical relationship names (e.g., say "works for" not "WORKS_FOR")

#### CEO Synthesis Prompt (Final Answer)

**Location:** `app/services/ingestion/llamaindex/query_engine.py` **(Lines 191-211)**

**What it controls:** How the AI combines vector search + graph search results into the final answer

**How to Change:**
1. Open `app/services/ingestion/llamaindex/query_engine.py`
2. Find `ceo_assistant_prompt = PromptTemplate(...)` (line 191)
3. Edit the prompt text
4. Save and restart server

**Current Focus:** Conversational, insightful, cite by title (not document_id)

**Customization Example - Executive Report Style:**
```python
ceo_assistant_prompt = PromptTemplate(
    "Synthesize the information below into an executive summary.\n"
    "Use bullet points for key findings. "
    "Include a 'Recommendations' section. "
    "Maintain professional tone throughout.\n\n"
    "Context:\n{context_str}\n\n"
    "Question: {query_str}\n"
    "Executive Summary: "
)
```

---

### 5.7 Metadata & Properties

**What is this?** Extra information attached to each document/chunk/entity in the databases. This metadata is passed to the LLM during retrieval, so it affects answer quality.

**⚠️ Important:** Metadata changes require re-ingestion of documents.

---

#### Qdrant Point Metadata (Vector Search)

**Location:** `app/services/ingestion/llamaindex/ingestion_pipeline.py` **(Lines 345-355)**

**What it controls:** Metadata stored with each text chunk in Qdrant (used for filtering and context)

**Current Properties:**
```python
{
    "document_id": 123,           # Supabase ID
    "title": "Q4 Report",         # Document name
    "source": "googledrive",      # Where it came from
    "document_type": "googledoc", # Type of document
    "tenant_id": "user-uuid",     # User/company ID
    "created_at": "2025-01-15",   # ISO timestamp
    "created_at_timestamp": 1736899200  # Unix timestamp for filtering
}
```

**How to Add Custom Metadata:**

**Step 1: Update Supabase Table**
```sql
-- In Supabase SQL Editor, add new columns
ALTER TABLE documents ADD COLUMN department TEXT;
ALTER TABLE documents ADD COLUMN priority TEXT;
ALTER TABLE documents ADD COLUMN tags JSONB;
```

**Step 2: Update Ingestion Code**
1. Open `app/services/ingestion/llamaindex/ingestion_pipeline.py`
2. Find the `doc_metadata` dictionary (line 345)
3. Add your custom fields:

```python
# Line 345 - Add custom metadata
doc_metadata = {
    # ... existing fields ...
    "department": document_row.get("department", "unknown"),  # NEW
    "priority": document_row.get("priority", "normal"),       # NEW
    "tags": document_row.get("tags", []),                     # NEW
}
```

**Step 3: Re-ingest Documents**
```bash
python3 scripts/utilities/ingest_from_documents_table.py
```

**Step 4: Verify**
```bash
# Check Qdrant points have new metadata
python3 -c "
from qdrant_client import QdrantClient
import os
client = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY'))
points = client.scroll('cortex_documents', limit=1, with_payload=True)
print('Sample metadata:', points[0][0].payload.keys())
"
```

#### Neo4j Chunk Properties (Graph Nodes)

**Location:** `app/services/ingestion/llamaindex/ingestion_pipeline.py` **(Lines 524-532 and 899-906)**

**What it controls:** Properties stored with each chunk node in Neo4j (these are passed to LLM during graph retrieval!)

**Current Properties:**
```python
{
    "text": "...",                    # Full chunk text
    "document_id": 123,               # Links to Supabase
    "title": "Q4 Report",             # For citations
    "source": "googledrive",          # Source system
    "document_type": "googledoc",     # Document type
    "created_at_timestamp": 1736899200  # Unix timestamp
}
```

**How to Add Custom Properties:**

**Step 1: Update Chunk Creation (TWO locations!)**

Location 1 - Line 524:
```python
chunk_node = EntityNode(
    label="Chunk",
    properties={
        "text": llama_node.text,
        "document_id": doc_id,
        "title": title,
        "source": source,
        "document_type": document_type,
        "created_at_timestamp": created_at_timestamp,
        "department": document_row.get("department"),  # NEW
        "priority": document_row.get("priority")       # NEW
    }
)
```

Location 2 - Line 899 (fallback path - must update both!):
```python
chunk_node = EntityNode(
    label="Chunk",
    properties={
        "text": llama_node.text,
        "document_id": doc_row.get("id"),
        "title": title,
        "source": source,
        "document_type": document_type,
        "created_at_timestamp": created_at_timestamp,
        "department": doc_row.get("department"),  # NEW
        "priority": doc_row.get("priority")       # NEW
    }
)
```

**Step 2: Re-ingest Documents**
```bash
# Clear Neo4j first (properties don't auto-update)
python3 << 'EOF'
from neo4j import GraphDatabase
import os
driver = GraphDatabase.driver(os.getenv("NEO4J_URI"), auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD")))
with driver.session(database="neo4j") as session:
    session.run("MATCH (n) DETACH DELETE n")
driver.close()
EOF

# Re-ingest
python3 scripts/utilities/ingest_from_documents_table.py
```

**Step 3: Verify in Neo4j Browser**
```cypher
MATCH (c:Chunk)
RETURN c.title, c.department, c.priority
LIMIT 5
```

**Step 4: Use in Queries (Optional)**
```cypher
# Find all high-priority engineering documents
MATCH (c:Chunk {department: "engineering"})
WHERE c.priority = "high"
RETURN c
```

---

### 5.8 Time-Based Filtering (Optional)

**File:** `app/services/ingestion/llamaindex/query_engine.py` **(Lines 360-450)**

**What is this?** Filters results by date when user asks "Show me emails from last week"

**Current Status:** **Disabled** (line 360)

**Why?** It was adding latency and occasionally causing issues. Can be re-enabled if needed.

---

**How to Re-Enable:**

**Step 1: Uncomment Time Filtering Code**
1. Open `app/services/ingestion/llamaindex/query_engine.py`
2. Go to line 360 - change this:
```python
# Time filtering disabled - enabled if needed in future
# Can be re-enabled with keyword pre-check (see commented code below)
metadata_filters = None
```

To this:
```python
# Re-enabled time filtering
metadata_filters = None  # Will be set below if time keywords detected
```

**Step 2: Uncomment Lines 364-450**
- Remove the `#` from the beginning of each line
- This activates:
  - Keyword detection (line 367-377)
  - LLM time extraction (line 379-421)
  - Qdrant metadata filtering (line 423-450)

**Step 3: Save and Restart Server**
```bash
# Restart server to apply changes
pkill -f "uvicorn main:app"
uvicorn main:app --host 0.0.0.0 --port 8080
```

**Step 4: Test with Time Query**
```bash
curl -X POST http://localhost:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT" \
  -d '{"question": "Show me documents from last week"}'
```

**Pros:**
- More accurate time-based queries
- Better for "Show me what changed this month"
- Filters at database level (efficient)

**Cons:**
- Adds ~200ms latency per query
- Costs extra LLM call (~$0.0001 per query)
- May false-positive on non-time queries

**Recommendation:** Re-enable only if client frequently asks time-based questions (>20% of queries).

---

### 5.9 Parallel Processing

**File:** `app/services/ingestion/llamaindex/config.py` **(Line 263)**

**What is this?** How many documents to process simultaneously during ingestion. Higher = faster ingestion but more memory usage.

**Current Settings:**

```python
# Line 263
NUM_WORKERS = 4  # Process 4 documents in parallel
```

**How to Change:**
1. Open `app/services/ingestion/llamaindex/config.py`
2. Go to line 263
3. Edit the value based on server specs (see table below)
4. Save (no restart needed - loaded at ingestion time)
5. Run ingestion to use new setting

**How to Adjust Based on Server:**

| Server Type | Recommended Workers | Expected Speed |
|-------------|---------------------|----------------|
| Laptop (4 cores) | `2` | 10 docs/min |
| Desktop (8 cores) | `4` (current) | 20 docs/min |
| Server (16 cores) | `8` | 40 docs/min |
| Cloud (32 cores) | `16` | 80 docs/min |

**Trade-off:**
- More workers = Faster ingestion = Higher memory usage
- If you see "Out of Memory" errors, reduce `NUM_WORKERS`

**Determine Optimal Setting:**

**Step 1: Check CPU Cores**
```bash
python3 -c "import os; print(f'CPU Cores: {os.cpu_count()}')"
```

**Step 2: Check Available Memory**
```bash
# On Linux/Mac
free -h

# On Mac specifically
vm_stat | grep "Pages free"
```

**Step 3: Calculate Workers**
- **Rule of thumb:** Set to 50% of CPU cores
- **Memory check:** Each worker uses ~200MB RAM
- **Example:** 8 cores, 8GB RAM → Use 4 workers (4 × 200MB = 800MB safe)

**Step 4: Test Ingestion**
```bash
# Monitor memory while ingesting
python3 scripts/utilities/ingest_from_documents_table.py

# If you see "MemoryError" or process killed, reduce NUM_WORKERS
```

**Verification:**
```bash
# Check that worker setting is loaded
python3 -c "
from app.services.ingestion.llamaindex.config import NUM_WORKERS
print(f'✅ Workers configured: {NUM_WORKERS}')
"
```

---

### 5.10 Production Caching (Optional)

**File:** `app/services/ingestion/llamaindex/config.py` **(Lines 271-276)**

**What is this?** Caches intermediate processing results to avoid re-processing unchanged documents. Saves time and money on re-ingestion.

**Current Status:** **Disabled** (no Redis configured)

---

**How to Enable:**

**Step 1: Set Up Redis**

**Option A: Redis Cloud (Recommended)**
1. Go to https://redis.com/cloud/
2. Sign up / Log in
3. Create new database
   - Name: `cortex-cache`
   - Cloud: AWS (same region as other services)
   - Plan: **Free tier** (30MB) for testing, **$5-10/month** for production
4. Get connection details:
   - Endpoint: `redis-12345.c1.us-east-1-1.ec2.cloud.redislabs.com`
   - Port: `6379`
   - Password: (provided)

**Option B: Self-Hosted Docker**
```bash
docker run -d \
  --name cortex-redis \
  -p 6379:6379 \
  redis:latest
```

**Step 2: Add to `.env`**
```bash
# Add these lines
REDIS_HOST=your-redis-host.com  # Or localhost if Docker
REDIS_PORT=6379
```

**Step 3: Restart Server**
```bash
# Caching auto-enables when REDIS_HOST is set!
pkill -f "uvicorn main:app"
uvicorn main:app --host 0.0.0.0 --port 8080
```

**Step 4: Verify**
```bash
python3 -c "
from app.services.ingestion.llamaindex.config import ENABLE_CACHE, REDIS_HOST
print(f'Redis Host: {REDIS_HOST}')
print(f'Caching Enabled: {ENABLE_CACHE}')
"
```

**Step 5: Test Cache Performance**
```bash
# First ingestion (no cache)
time python3 scripts/utilities/ingest_from_documents_table.py

# Second ingestion (with cache - should be 10x faster!)
time python3 scripts/utilities/ingest_from_documents_table.py
```

---

**Benefits:**
- Re-ingestion is **10x faster** (skips already-processed docs)
- Saves **~80% on OpenAI costs** for re-ingestion
- Detects when documents haven't changed

**Cost:**
- **Redis Cloud:** $5-10/month (30MB-500MB)
- **Memory:** ~100MB per 1,000 documents cached
- **Example:** 10k docs = 1GB Redis = $10/month

**When to Enable:**
- ✅ Client updates documents frequently (versioned docs)
- ✅ Re-ingestion happens regularly (daily/weekly)
- ✅ Large document corpus (>5k documents)
- ❌ Small dataset that never changes
- ❌ One-time ingestion only

**How Cache Works:**
1. Before processing doc, check Redis for hash
2. If hash matches → Skip processing, reuse old result
3. If hash different → Process doc, cache new result
4. Saves expensive LLM calls for unchanged docs

**Cache Configuration (Lines 271-273):**
```python
# Line 271
REDIS_HOST = os.getenv("REDIS_HOST", None)  # Set in .env
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_COLLECTION = "cortex_ingestion_cache"  # Redis key prefix
```

**To Disable Cache:**
```bash
# Remove from .env
# REDIS_HOST=...

# Or set to empty
REDIS_HOST=
```

---

## Troubleshooting

### "Collection does not exist" (Qdrant)

**Cause:** Collection not created yet

**Fix:** Ingest at least 1 document - collection auto-creates

```bash
python3 scripts/utilities/ingest_from_documents_table.py
```

---

### "Authentication failed" (Neo4j)

**Cause:** Wrong password or URI

**Fix:**
1. Go to Neo4j Aura dashboard
2. Click your instance → "Reset password"
3. Update `.env` with new password
4. Ensure URI starts with `neo4j+s://` (with the `+s`)

---

### "Invalid API key" (OpenAI)

**Cause:** Key not activated or expired

**Fix:**
1. Go to https://platform.openai.com/api-keys
2. Verify key is Active (not Revoked)
3. Check billing: https://platform.openai.com/account/billing
4. Must have payment method on file

---

### "No such table: documents" (Supabase)

**Cause:** SQL migration not run

**Fix:** Re-run the SQL from Part 3.1 in Supabase SQL Editor

---

### "Out of Memory" during ingestion

**Cause:** Processing too many documents in parallel

**Fix:** Reduce workers in `config.py`:
```python
NUM_WORKERS = 2  # Down from 4
```

---

### Chat returns empty answers

**Cause:** No data ingested yet

**Fix:**
1. Check Qdrant has data:
```bash
python3 -c "
from qdrant_client import QdrantClient
import os
client = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY'))
collection = client.get_collection('cortex_documents')
print(f'Points in Qdrant: {collection.points_count}')
"
```

2. Check Neo4j has nodes:
```cypher
MATCH (n) RETURN count(n) AS total_nodes
```

3. If both show 0, run ingestion script

---

### "Rate limit exceeded" (OpenAI)

**Cause:** Hit OpenAI usage limits

**Fix:**
1. Go to https://platform.openai.com/account/limits
2. Request limit increase
3. Or add delay between requests in `ingestion_pipeline.py`:
```python
import asyncio
await asyncio.sleep(1)  # Add 1 second delay
```

---

### Neo4j Browser shows no relationships

**Cause:** Entities extracted but not connected

**Fix:**
1. Check if relationships exist:
```cypher
MATCH ()-[r]->() RETURN count(r) AS total_relationships
```

2. If 0, increase `max_triplets_per_chunk` in `ingestion_pipeline.py`:
```python
max_triplets_per_chunk=15  # Up from 10
```

3. Re-ingest documents

---

### Qdrant collection has wrong dimensions

**Cause:** Changed embedding model after collection created

**Fix:**
1. Delete collection:
```bash
python3 -c "
from qdrant_client import QdrantClient
import os
client = QdrantClient(url=os.getenv('QDRANT_URL'), api_key=os.getenv('QDRANT_API_KEY'))
client.delete_collection('cortex_documents')
print('✅ Collection deleted')
"
```

2. Re-ingest - collection recreates with new dimensions

---

## Final Checklist

Before handing over to client:

- [ ] All 4 cloud accounts created (Supabase, Qdrant, Neo4j, OpenAI)
- [ ] `.env` file completely filled out
- [ ] Supabase tables created (`documents`, `chats`, `chat_messages`)
- [ ] All 4 database connections tested (green checkmarks)
- [ ] Server starts without errors
- [ ] Health endpoint returns `{"status": "healthy"}`
- [ ] At least 1 test document ingested successfully
- [ ] Chat returns a valid answer (not empty)
- [ ] Neo4j Browser shows nodes and relationships
- [ ] Qdrant shows points in collection
- [ ] Client has all passwords/API keys saved securely
- [ ] Monthly costs explained to client (~$100-200/month typical)

---

## Cost Summary (Typical Client)

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| Supabase | Pro | $25 |
| Qdrant | 1GB RAM | $25 |
| Neo4j | Professional | $65 |
| OpenAI | Pay-per-use | $20-50 |
| Nango (optional) | Starter | $25 |
| **TOTAL** | | **$160-190/month** |

**Usage-based costs (OpenAI):**
- Initial ingestion (10k docs): ~$12
- Ongoing queries (1000/day): ~$30/month
- Re-ingestion: ~$2/month (updates only)

**Scaling costs:**
- 50k documents: +$50/month (Qdrant 2GB)
- 100k documents: +$100/month (Qdrant 4GB + Neo4j Pro+)
- 1M queries/day: +$200/month (OpenAI)

---

## Support & Next Steps

**After deployment:**

1. **Test with real data:** Have client upload 10-20 real documents and test queries
2. **Customize schema:** Adjust entities/relationships for their industry (Part 5.1)
3. **Tune prompts:** Customize AI personality for their use case (Part 5.6)
4. **Monitor costs:** Check OpenAI usage after first week
5. **Set up monitoring:** Use Neo4j Browser and Qdrant dashboard to verify data quality

**Documentation:**
- Neo4j Query Language: https://neo4j.com/docs/cypher-manual/current/
- Qdrant API: https://qdrant.tech/documentation/
- LlamaIndex: https://docs.llamaindex.ai/

**Need help?**
- Review codebase README.md
- Check logs: `tail -f logs/cortex.log`
- Neo4j Browser: Great for visualizing knowledge graph
- Qdrant Dashboard: See vector search in action

---

**You're all set! 🎉**

Drop this guide into Claude Code and it'll help configure everything correctly. Good luck with the client deployment!
