"""
Master Control Plane Configuration
===================================
Handles multi-tenant configuration from master Supabase.

BACKWARD COMPATIBLE:
- If COMPANY_ID not set → Works like before (single-tenant mode)
- If COMPANY_ID set → Loads config from master Supabase (multi-tenant mode)
"""

import os
import logging
from typing import Optional
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

class MasterConfig(BaseSettings):
    """
    Master control plane configuration.
    Only used when running in multi-tenant mode.
    """

    # Company Identity
    company_id: Optional[str] = None  # If None, runs in single-tenant mode
    company_slug: Optional[str] = None

    # Master Supabase (control plane)
    master_supabase_url: Optional[str] = None
    master_supabase_service_key: Optional[str] = None

    # Multi-tenant mode flag
    is_multi_tenant: bool = False

    class Config:
        env_file = ".env"
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Auto-detect multi-tenant mode
        if self.company_id and self.master_supabase_url:
            self.is_multi_tenant = True
            logger.info(f"🏢 Multi-tenant mode ENABLED (Company ID: {self.company_id})")
        else:
            self.is_multi_tenant = False
            logger.info("🏠 Single-tenant mode (backward compatible)")


# Global instance
master_config = MasterConfig()


def is_multi_tenant() -> bool:
    """Check if running in multi-tenant mode."""
    return master_config.is_multi_tenant


def get_company_id() -> Optional[str]:
    """Get current company ID (None if single-tenant mode)."""
    return master_config.company_id


def get_master_supabase_url() -> Optional[str]:
    """Get master Supabase URL (None if single-tenant mode)."""
    return master_config.master_supabase_url


def get_master_supabase_key() -> Optional[str]:
    """Get master Supabase service key (None if single-tenant mode)."""
    return master_config.master_supabase_service_key
