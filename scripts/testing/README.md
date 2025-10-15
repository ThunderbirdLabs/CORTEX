# Testing Scripts

Test scripts for validating the Hybrid Property Graph retrieval system.

## Scripts

- **`test_hybrid.py`** - Comprehensive test of ingestion and retrieval pipeline
  - Tests document ingestion into PropertyGraphIndex
  - Verifies multi-strategy retrieval (VectorContext + LLMSynonym)
  - Validates Neo4j entity/relationship extraction
  - Includes sample email data for testing

- **`test_query.py`** - Quick query testing script
  - Minimal test for retrieval functionality
  - Fast iteration testing

## Usage

```bash
# Run full hybrid system test
python scripts/testing/test_hybrid.py

# Run quick query test
python scripts/testing/test_query.py
```

## Architecture Tested

These scripts test the **production** Hybrid Property Graph architecture:
- Single PropertyGraphIndex (Neo4j + Qdrant)
- VectorContextRetriever (graph-aware vector search)
- LLMSynonymRetriever (query expansion)
- Schema-guided entity extraction
- Implicit relationship extraction
