"""
DEPRECATED: Use app.services.sync.providers.quickbooks instead

This module has been consolidated into the sync system.
All new code should import from app.services.sync.providers
"""

# Re-export from new location for backward compatibility
from app.services.sync.providers.quickbooks import fetch_all_quickbooks_data

__all__ = ["fetch_all_quickbooks_data"]
