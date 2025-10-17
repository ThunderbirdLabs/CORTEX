"""
Nango Services
OAuth proxy and webhook handling
"""
from app.services.nango.nango_client import get_graph_token_via_nango, nango_list_gmail_records
from app.services.nango.database import save_connection, get_connection
from app.services.nango.sync_engine import run_gmail_sync, run_tenant_sync
from app.services.nango.persistence import append_jsonl, ingest_to_cortex

__all__ = [
    "get_graph_token_via_nango",
    "nango_list_gmail_records",
    "save_connection",
    "get_connection",
    "run_gmail_sync",
    "run_tenant_sync",
    "append_jsonl",
    "ingest_to_cortex",
]
