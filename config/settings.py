"""
Configuration settings for Email Sync Connector
Centralized environment variable loading and validation
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# SERVER CONFIGURATION
# ============================================================================

PORT = int(os.getenv("PORT", "8080"))

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# ============================================================================
# NANGO CONFIGURATION
# ============================================================================

NANGO_SECRET = os.getenv("NANGO_SECRET")

# Outlook/Microsoft Graph configuration
NANGO_PROVIDER_KEY = os.getenv("NANGO_PROVIDER_KEY")  # Backward compatibility
NANGO_PROVIDER_KEY_OUTLOOK = os.getenv("NANGO_PROVIDER_KEY_OUTLOOK", os.getenv("NANGO_PROVIDER_KEY"))
NANGO_CONNECTION_ID = os.getenv("NANGO_CONNECTION_ID")  # Backward compatibility
NANGO_CONNECTION_ID_OUTLOOK = os.getenv("NANGO_CONNECTION_ID_OUTLOOK", os.getenv("NANGO_CONNECTION_ID"))
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID", "")

# Gmail configuration
NANGO_PROVIDER_KEY_GMAIL = os.getenv("NANGO_PROVIDER_KEY_GMAIL")
NANGO_CONNECTION_ID_GMAIL = os.getenv("NANGO_CONNECTION_ID_GMAIL")

# ============================================================================
# DEBUG CONFIGURATION
# ============================================================================

SAVE_JSONL = os.getenv("SAVE_JSONL", "false").lower() == "true"

# ============================================================================
# VALIDATION
# ============================================================================

def validate_config():
    """Validate required environment variables are set."""
    required_vars = [
        "DATABASE_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY",
        "NANGO_SECRET"
    ]
    for var in required_vars:
        if not os.getenv(var):
            raise RuntimeError(f"Missing required environment variable: {var}")

    # Validate at least one provider is configured
    if not NANGO_PROVIDER_KEY_OUTLOOK and not NANGO_PROVIDER_KEY_GMAIL:
        raise RuntimeError("At least one provider key must be set: NANGO_PROVIDER_KEY_OUTLOOK or NANGO_PROVIDER_KEY_GMAIL")


# Run validation on import
validate_config()
