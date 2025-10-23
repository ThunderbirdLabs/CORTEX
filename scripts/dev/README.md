# Database Tools

Utilities for inspecting, auditing, and managing Neo4j, Qdrant, and Supabase databases.

## Scripts

### Audit & Inspection
- **`audit_databases.py`** - Complete audit of Neo4j and Qdrant data
- **`audit_qdrant_complete.py`** - Detailed Qdrant collection analysis
- **`audit_qdrant_storage.py`** - Qdrant storage and vector analysis
- **`check_databases.py`** - Quick health check for all databases
- **`check_chunks.py`** - Inspect document chunking
- **`check_neo4j_embeddings.py`** - Verify Neo4j node embeddings
- **`check_supabase_tables.py`** - List Supabase tables
- **`inspect_node_content.py`** - Inspect individual node content
- **`preview_supabase_data.py`** - Preview Supabase data

### Storage Analysis
- **`analyze_storage.py`** - Analyze storage patterns across databases

### Cleanup
- **`clear_databases.py`** - Clear all data from Neo4j and Qdrant

## Usage

```bash
# Run from project root
python scripts/database_tools/audit_databases.py
python scripts/database_tools/check_databases.py
python scripts/database_tools/clear_databases.py
```

## ⚠️ Warning

The `clear_databases.py` script will DELETE all data. Use with caution!
