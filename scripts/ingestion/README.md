# Ingestion Scripts

Production ingestion scripts for loading data into the Hybrid Property Graph system.

## Scripts

- **`ingest_from_supabase.py`** - Production ingestion from Supabase
  - Fetches emails/documents from Supabase tables
  - Ingests into PropertyGraphIndex (Neo4j + Qdrant)
  - Supports tenant filtering and batch limits

## Usage

```bash
# Ingest 25 emails (default)
python scripts/ingestion/ingest_from_supabase.py

# Ingest specific number of emails
python scripts/ingestion/ingest_from_supabase.py --limit 100

# Ingest from specific table
python scripts/ingestion/ingest_from_supabase.py --table documents --limit 50

# Filter by tenant
python scripts/ingestion/ingest_from_supabase.py --tenant tenant_123
```

## Data Flow

```
Supabase (emails table)
    ↓
HybridPropertyGraphPipeline
    ↓
├─→ Neo4j PropertyGraphStore (entities, relationships)
└─→ Qdrant VectorStore (embeddings)
```

## Architecture

Uses the production **HybridPropertyGraphPipeline** with:
- SchemaLLMPathExtractor for business entity extraction
- ImplicitPathExtractor for document structure relationships
- Unified PropertyGraphIndex with embedded graph nodes
