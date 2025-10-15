# Scripts Directory

Organized collection of utility scripts for development, testing, and database operations.

## 📁 Structure

```
scripts/
├── database_tools/    # Database inspection and management utilities
├── ingestion/         # Data ingestion scripts
└── testing/           # Test scripts for the hybrid RAG system
```

## Usage

All scripts should be run from the project root directory:

```bash
# Example
python scripts/testing/test_hybrid.py
python scripts/ingestion/ingest_from_supabase.py --limit 10
```
