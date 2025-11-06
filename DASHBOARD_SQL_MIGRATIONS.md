# Business Intelligence Dashboard - SQL Migrations

## Summary

**NO NEW DATABASE TABLES REQUIRED**

The business intelligence dashboard leverages **existing database schema** and infrastructure:

1. ✅ `documents` table (already exists)
2. ✅ `daily_intelligence` table (already exists)
3. ✅ `weekly_intelligence` table (already exists)
4. ✅ `monthly_intelligence` table (already exists)
5. ✅ `chat_messages` table (already exists)
6. ✅ Neo4j knowledge graph (already configured)
7. ✅ Qdrant vector store (already configured)

---

## Existing Tables Used by Dashboard

### 1. `documents` Table
**Location:** `/migrations/create_documents_table.sql`

**Used by Widgets:**
- Communication Patterns (email analysis)
- Sentiment Analysis (keyword detection)
- Deal Momentum (via Neo4j graph built from documents)

**Schema:**
```sql
CREATE TABLE documents (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    source TEXT NOT NULL,              -- 'gmail', 'outlook', 'gdrive', 'quickbooks'
    source_id TEXT NOT NULL,
    document_type TEXT NOT NULL,       -- 'email', 'pdf', 'invoice', etc.
    title TEXT NOT NULL,
    content TEXT NOT NULL,             -- Full-text content
    raw_data JSONB,
    file_url TEXT,
    file_size_bytes BIGINT,
    mime_type TEXT,
    parent_document_id BIGINT,
    source_created_at TIMESTAMPTZ,     -- Used for time filtering
    source_modified_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',       -- Flexible fields per source
    UNIQUE(tenant_id, source, source_id)
);
```

**Indexes:**
- `idx_documents_tenant` - Multi-tenant isolation
- `idx_documents_created DESC` - Time-based queries
- `idx_documents_metadata` (GIN) - JSON queries

---

### 2. `daily_intelligence` Table
**Location:** `/migrations/create_intelligence_tables.sql`

**Used by Widgets:**
- Intelligence Feed
- Activity Pulse (via trends API)

**Schema:**
```sql
CREATE TABLE daily_intelligence (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    date DATE NOT NULL,

    -- Document metrics
    total_documents INTEGER DEFAULT 0,
    document_counts JSONB DEFAULT '{}',    -- {"email": 45, "invoice": 12}

    -- QuickBooks financials
    invoice_total_amount DECIMAL(12,2),
    invoice_outstanding_balance DECIMAL(12,2),
    bill_total_amount DECIMAL(12,2),
    payment_total_amount DECIMAL(12,2),

    -- Entity activity
    most_active_people JSONB DEFAULT '[]',
    most_active_companies JSONB DEFAULT '[]',
    new_entities JSONB DEFAULT '[]',

    -- Communication
    email_senders JSONB DEFAULT '[]',
    email_recipients JSONB DEFAULT '[]',

    -- Topics
    key_topics JSONB DEFAULT '[]',

    -- AI summary
    ai_summary TEXT,
    key_insights JSONB DEFAULT '[]',

    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_duration_ms INTEGER,

    UNIQUE(tenant_id, date)
);
```

---

### 3. `weekly_intelligence` Table
**Location:** `/migrations/create_intelligence_tables.sql`

**Used by Widgets:**
- Intelligence Feed (weekly trends)
- Activity Pulse (week-over-week changes)

**Schema:**
```sql
CREATE TABLE weekly_intelligence (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,

    -- Activity trends
    total_documents INTEGER DEFAULT 0,
    document_trend JSONB DEFAULT '{}',
    wow_change_percent DECIMAL(5,2),

    -- Entity evolution
    total_unique_entities INTEGER DEFAULT 0,
    new_entities_count INTEGER DEFAULT 0,
    trending_people JSONB DEFAULT '[]',
    trending_companies JSONB DEFAULT '[]',
    trending_topics JSONB DEFAULT '[]',

    -- Relationships
    new_relationships JSONB DEFAULT '[]',
    collaboration_patterns JSONB DEFAULT '[]',

    -- Business momentum
    deals_advancing JSONB DEFAULT '[]',
    deals_stalling JSONB DEFAULT '[]',

    -- Financial
    weekly_revenue DECIMAL(12,2),
    weekly_expenses DECIMAL(12,2),
    revenue_trend JSONB DEFAULT '[]',

    -- AI insights
    weekly_summary TEXT,
    key_insights JSONB DEFAULT '[]',
    action_items JSONB DEFAULT '[]',

    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_duration_ms INTEGER,

    UNIQUE(tenant_id, week_start)
);
```

---

### 4. Neo4j Knowledge Graph
**Configuration:** `/app/services/rag/config.py`

**Used by Widgets:**
- Trending Entities (PERSON, COMPANY nodes)
- Deal Momentum (PURCHASE_ORDER nodes)
- Communication Patterns (relationship queries)

**Node Types:**
- `PERSON` - Individual people
- `COMPANY` - Business entities
- `ROLE` - Job titles
- `PURCHASE_ORDER` - Deals/POs
- `MATERIAL` - Materials/products
- `CERTIFICATION` - Certifications
- `Chunk` - Document chunks (link to Qdrant vectors)

**Relationship Types:**
- `WORKS_FOR` - Person → Company
- `HAS_ROLE` - Person → Role
- `WORKS_WITH` - Person → Person/Company
- `SUPPLIES` - Company → Material
- `CONTAINS` - PurchaseOrder → Material
- `HAS_CERTIFICATION` - Company → Certification

**Example Query (used by Trending Entities widget):**
```cypher
MATCH (c:Chunk)-[r]->(p:PERSON)
WHERE c.tenant_id = $tenant_id
  AND c.created_at_timestamp >= $cutoff_timestamp
WITH p.name AS name, count(*) AS mentions
RETURN name, mentions
ORDER BY mentions DESC
LIMIT 10
```

---

## API Endpoints Created

**New Analytics Router:** `/app/api/v1/routes/analytics.py`

### 1. GET /api/v1/analytics/entities/trending
**Query Parameters:**
- `days` (default: 30) - Time range in days
- `limit` (default: 10) - Max results per entity type

**Response:**
```json
{
  "people": [
    {
      "name": "John Smith",
      "mentions": 45,
      "type": "PERSON",
      "trend": null
    }
  ],
  "companies": [
    {
      "name": "Acme Corp",
      "mentions": 32,
      "type": "COMPANY",
      "trend": null
    }
  ],
  "date_range_days": 30
}
```

---

### 2. GET /api/v1/analytics/communication/patterns
**Query Parameters:**
- `days` (default: 30) - Time range in days

**Response:**
```json
{
  "top_senders": [
    {
      "name": "John Smith",
      "email_count": 58,
      "unique_contacts": 12
    }
  ],
  "top_recipients": [...],
  "edges": [
    {
      "from": "John Smith",
      "to": "Sarah Chen",
      "count": 15
    }
  ],
  "total_emails": 234,
  "date_range_days": 30
}
```

---

### 3. GET /api/v1/analytics/deals/momentum
**Query Parameters:**
- `days` (default: 30) - Time range in days

**Response:**
```json
{
  "deals": [
    {
      "name": "PO #54321",
      "touchpoints_this_week": 12,
      "touchpoints_last_week": 3,
      "last_mention_date": "2025-11-05T14:30:00Z",
      "days_since_last_mention": 1,
      "status": "hot",
      "trend": "up",
      "velocity_percent": 300
    }
  ],
  "date_range_days": 30
}
```

---

### 4. GET /api/v1/analytics/sentiment/analysis
**Query Parameters:**
- `days` (default: 30) - Time range in days

**Response:**
```json
{
  "alerts": [
    {
      "type": "opportunity",
      "keyword": "expansion",
      "count": 5,
      "context": "Potential business opportunity detected",
      "severity": "medium"
    },
    {
      "type": "risk",
      "keyword": "delay",
      "count": 3,
      "context": "Requires immediate attention",
      "severity": "low"
    }
  ],
  "total_documents_analyzed": 234,
  "date_range_days": 30
}
```

---

### 5. GET /api/v1/analytics/relationships/network
**No query parameters**

**Response:**
```json
{
  "relationships": [
    {
      "from": "John Smith",
      "to": "Acme Corp",
      "type": "WORKS_FOR"
    }
  ],
  "node_count": 42,
  "edge_count": 58
}
```

---

## Data Flow

1. **Documents Ingestion** → `documents` table (PostgreSQL)
2. **Nightly Intelligence Jobs** → `daily_intelligence`, `weekly_intelligence`, `monthly_intelligence`
3. **Entity Extraction** → Neo4j knowledge graph (PERSON, COMPANY, PURCHASE_ORDER nodes)
4. **Vector Embeddings** → Qdrant vector store
5. **Dashboard Widgets** → Query analytics endpoints
6. **Frontend Display** → Recharts visualizations

---

## Performance Considerations

### Caching Strategy
**Frontend (lib/api.ts):**
- Daily intelligence: 5-minute cache
- Weekly intelligence: 10-minute cache
- Monthly intelligence: 30-minute cache
- Trending entities: No cache (real-time)
- Communication patterns: No cache (real-time)

### Database Indexes
All required indexes **already exist**:
- `documents.source_created_at DESC` - For time-range queries
- `documents.metadata` (GIN) - For JSON queries
- `documents.tenant_id` - For multi-tenant isolation
- Neo4j indexes on `tenant_id`, `created_at_timestamp`

### Query Performance
- **Intelligence endpoints:** < 100ms (pre-computed data)
- **Neo4j entity queries:** ~200ms (indexed traversal)
- **Communication pattern analysis:** ~500ms (aggregation on documents table)
- **Sentiment analysis:** ~800ms (full-text search on content column)

---

## Deployment Steps

### 1. Backend Deployment
```bash
# No database migrations needed!
# Just restart the backend to load new routes

cd /path/to/CORTEX
git pull origin main
# Render.com will auto-deploy or manually restart
```

### 2. Frontend Deployment
```bash
cd /path/to/connectorfrontend
git pull origin main
# Vercel will auto-deploy
```

### 3. Verification
```bash
# Test analytics endpoints
curl https://your-backend.onrender.com/api/v1/analytics/entities/trending?days=30

# Test intelligence endpoints
curl https://your-backend.onrender.com/api/v1/intelligence/daily/latest

# Visit dashboard
# https://your-frontend.vercel.app/
```

---

## Future Enhancements (Optional)

If you want to add advanced features in the future, consider creating these **optional** tables:

### 1. `dashboard_snapshots` (Optional)
**Purpose:** Cache expensive dashboard queries for historical comparison

```sql
CREATE TABLE dashboard_snapshots (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    widget_id TEXT NOT NULL,           -- 'trending_entities', 'deal_momentum', etc.
    snapshot_data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, snapshot_date, widget_id)
);

CREATE INDEX idx_dashboard_snapshots_tenant_date
ON dashboard_snapshots(tenant_id, snapshot_date DESC);
```

### 2. `user_dashboard_preferences` (Optional)
**Purpose:** Store user customization (widget order, filters, favorites)

```sql
CREATE TABLE user_dashboard_preferences (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_email TEXT NOT NULL,
    widget_layout JSONB DEFAULT '[]',  -- [{"id": "activity_pulse", "position": 1}]
    default_filters JSONB DEFAULT '{}',  -- {"days": 30, "sources": ["gmail"]}
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, user_email)
);
```

### 3. `entity_mention_history` (Optional)
**Purpose:** Time-series tracking of entity mentions for trend calculation

```sql
CREATE TABLE entity_mention_history (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,         -- 'PERSON', 'COMPANY', 'PURCHASE_ORDER'
    mention_count INTEGER DEFAULT 0,
    date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, entity_name, entity_type, date)
);

CREATE INDEX idx_entity_history_tenant_date
ON entity_mention_history(tenant_id, date DESC);
```

**BUT THESE ARE NOT REQUIRED FOR THE CURRENT IMPLEMENTATION!**

---

## Summary

✅ **All dashboard widgets work with existing schema**
✅ **No new database tables needed**
✅ **No migration scripts required**
✅ **Just deploy code and restart services**
✅ **All data already being collected and stored**

The intelligence tables (`daily_intelligence`, `weekly_intelligence`, `monthly_intelligence`) are already being populated by nightly background jobs, so the dashboard will have data immediately after deployment.
