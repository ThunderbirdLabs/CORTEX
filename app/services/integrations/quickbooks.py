"""
DEPRECATED: Use app.services.sync.providers.quickbooks instead

This file is maintained for backward compatibility only.
All new code should import from app.services.sync.providers
"""

# Re-export everything from new location for backward compatibility
from app.services.sync.providers.quickbooks import *  # noqa: F401, F403
