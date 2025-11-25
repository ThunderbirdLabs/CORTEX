"""
Unified Configuration
All environment variables and settings in one place

MULTI-TENANT MODE:
- If COMPANY_ID + MASTER_SUPABASE_URL + MASTER_SUPABASE_SERVICE_KEY are set,
  infrastructure credentials are loaded from master Supabase automatically
- Otherwise, all credentials must be provided as environment variables (backward compatible)
"""
from typing import Optional
import logging
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Unified application settings.
    Validates all environment variables at startup.
    """

    # ============================================================================
    # SERVER
    # ============================================================================

    environment: str = Field(default="production", description="Environment: dev/staging/production")
    port: int = Field(default=8080, description="Server port")
    debug: bool = Field(default=False, description="Debug mode")

    # ============================================================================
    # DATABASE (Supabase PostgreSQL)
    # ============================================================================

    database_url: Optional[str] = Field(default=None, description="PostgreSQL connection string")
    supabase_url: Optional[str] = Field(default=None, description="Supabase project URL")
    supabase_anon_key: Optional[str] = Field(default=None, description="Supabase anonymous key")
    supabase_service_key: Optional[str] = Field(default=None, description="Supabase service key (for Cortex)")
    supabase_db_url: Optional[str] = Field(default=None, description="Direct Supabase DB URL")

    # ============================================================================
    # MULTI-TENANT (Master Supabase)
    # ============================================================================

    company_id: Optional[str] = Field(default=None, description="Company ID for multi-tenant deployment")
    master_supabase_url: Optional[str] = Field(default=None, description="Master Supabase URL (control plane)")
    master_supabase_service_key: Optional[str] = Field(default=None, description="Master Supabase service key")

    # ============================================================================
    # OAUTH (Nango)
    # ============================================================================

    nango_secret_key: Optional[str] = Field(default=None, description="Nango API secret key")

    # Provider configurations
    nango_provider_key_outlook: Optional[str] = Field(default=None, description="Nango provider key for Outlook")
    nango_provider_key_gmail: Optional[str] = Field(default=None, description="Nango provider key for Gmail")
    nango_provider_key_google_drive: Optional[str] = Field(default=None, description="Nango provider key for Google Drive")
    nango_provider_key_quickbooks: Optional[str] = Field(default=None, description="Nango provider key for QuickBooks")

    # Connection IDs (optional - set after OAuth)
    nango_connection_id_outlook: Optional[str] = Field(default=None)
    nango_connection_id_gmail: Optional[str] = Field(default=None)

    # Microsoft Graph
    graph_tenant_id: Optional[str] = Field(default=None, description="Azure AD tenant ID")

    # ============================================================================
    # HYBRID RAG SYSTEM
    # ============================================================================

    # Vector Database (Qdrant)
    qdrant_url: Optional[str] = Field(default=None, description="Qdrant Cloud URL")
    qdrant_api_key: Optional[str] = Field(default=None, description="Qdrant API key")
    qdrant_collection_name: str = Field(default="cortex_documents", description="Qdrant collection name")

    # LLM & Embeddings (OpenAI)
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")

    # Redis (job queue)
    redis_url: Optional[str] = Field(default=None, description="Redis connection URL")

    # ============================================================================
    # API KEYS
    # ============================================================================

    cortex_api_key: Optional[str] = Field(default=None, description="API key for Cortex search endpoint")

    # ============================================================================
    # ENTITY DEDUPLICATION
    # ============================================================================

    dedup_enabled: bool = Field(default=True, description="Enable periodic entity deduplication")
    dedup_interval_hours: int = Field(default=1, description="Deduplication run interval (hours)")
    dedup_similarity_threshold: float = Field(default=0.85, description="Vector similarity threshold (0.85-0.90 recommended)")
    dedup_levenshtein_max_distance: int = Field(default=3, description="Max Levenshtein distance (2-5)")
    dedup_batch_size: int = Field(default=50, description="Merge batch size (20-100, tune based on load)")

    # ============================================================================
    # PRODUCTION INFRASTRUCTURE
    # ============================================================================

    # Error tracking (Sentry)
    sentry_dsn: Optional[str] = Field(default=None, description="Sentry DSN for error tracking")

    # ============================================================================
    # SPAM FILTERING
    # ============================================================================
    
    enable_spam_filtering: bool = Field(default=True, description="Enable OpenAI-powered spam/newsletter filtering")
    spam_filter_log_skipped: bool = Field(default=True, description="Log filtered spam emails for monitoring")
    spam_filter_batch_size: int = Field(default=10, description="Number of emails to classify per OpenAI API call")

    # ============================================================================
    # OPTIONAL SETTINGS
    # ============================================================================

    save_jsonl: bool = Field(default=False, description="Save emails to JSONL for debugging")
    semaphore_limit: int = Field(default=10, description="LlamaIndex concurrency limit")

    # ============================================================================
    # ADMIN DASHBOARD
    # ============================================================================

    admin_session_duration: int = Field(default=3600, description="Admin session duration in seconds (default 1 hour)")
    admin_ip_whitelist: Optional[str] = Field(default=None, description="Comma-separated list of allowed admin IPs (optional)")

    @model_validator(mode='after')
    def load_from_master_supabase(self):
        """
        Load infrastructure credentials from master Supabase if multi-tenant mode is enabled.
        Priority: Environment variables > Master Supabase > Error
        """
        # Check if multi-tenant mode
        if not (self.company_id and self.master_supabase_url and self.master_supabase_service_key):
            logger.info("🏠 Single-tenant mode: Using environment variables for all credentials")
            return self

        logger.info(f"🏢 Multi-tenant mode detected (Company ID: {self.company_id})")
        logger.info("🔍 Attempting to load credentials from master Supabase...")

        try:
            from supabase import create_client

            # Connect to master Supabase
            master_client = create_client(self.master_supabase_url, self.master_supabase_service_key)

            # Fetch deployment credentials
            result = master_client.table("company_deployments")\
                .select("*")\
                .eq("company_id", self.company_id)\
                .maybe_single()\
                .execute()

            if not result.data:
                logger.warning(f"⚠️  No deployment found for company_id: {self.company_id}")
                logger.warning("⚠️  This is expected for new companies. Using environment variables only.")
                # Don't raise error - allow new companies with placeholder deployments
                return self

            deployment = result.data
            logger.info("✅ Successfully loaded deployment credentials from master Supabase")

            # Load credentials with fallback to env vars
            # Priority: ENV VAR > MASTER SUPABASE > None
            def load_with_fallback(field_name: str, supabase_key: str, current_value):
                """Load from Supabase if env var not set, with logging"""
                if current_value is not None:
                    logger.debug(f"  ✓ {field_name}: Using environment variable")
                    return current_value

                supabase_value = deployment.get(supabase_key)
                if supabase_value:
                    logger.info(f"  ✓ {field_name}: Loaded from master Supabase")
                    return supabase_value

                logger.warning(f"  ⚠️  {field_name}: Not found in env or master Supabase")
                return None

            # Supabase (company operational database)
            self.supabase_url = load_with_fallback("supabase_url", "supabase_url", self.supabase_url)
            self.supabase_anon_key = load_with_fallback("supabase_anon_key", "supabase_anon_key", self.supabase_anon_key)
            self.supabase_service_key = load_with_fallback("supabase_service_key", "supabase_service_key", self.supabase_service_key)

            # Derive database_url from supabase_url if not set
            if not self.database_url and self.supabase_url:
                # Extract project ref from URL (e.g., slhntddytmzpqqrfndgg from https://slhntddytmzpqqrfndgg.supabase.co)
                project_ref = self.supabase_url.replace("https://", "").replace(".supabase.co", "")
                # Note: We don't have the password in master Supabase, so this won't work perfectly
                # User should provide DATABASE_URL as env var or we need to store it in master Supabase
                logger.warning("  ⚠️  database_url: Cannot derive from supabase_url (password not stored)")

            # Qdrant
            self.qdrant_url = load_with_fallback("qdrant_url", "qdrant_url", self.qdrant_url)
            self.qdrant_api_key = load_with_fallback("qdrant_api_key", "qdrant_api_key", self.qdrant_api_key)
            if not self.qdrant_collection_name and deployment.get("qdrant_collection_name"):
                self.qdrant_collection_name = deployment["qdrant_collection_name"]

            # Redis
            self.redis_url = load_with_fallback("redis_url", "redis_url", self.redis_url)

            # OpenAI
            self.openai_api_key = load_with_fallback("openai_api_key", "openai_api_key", self.openai_api_key)

            # Nango
            self.nango_secret_key = load_with_fallback("nango_secret_key", "nango_secret_key", self.nango_secret_key)
            self.nango_provider_key_gmail = load_with_fallback("nango_provider_key_gmail", "nango_provider_key_gmail", self.nango_provider_key_gmail)
            self.nango_provider_key_outlook = load_with_fallback("nango_provider_key_outlook", "nango_provider_key_outlook", self.nango_provider_key_outlook)
            self.nango_provider_key_google_drive = load_with_fallback("nango_provider_key_google_drive", "nango_provider_key_google_drive", self.nango_provider_key_google_drive)
            self.nango_provider_key_quickbooks = load_with_fallback("nango_provider_key_quickbooks", "nango_provider_key_quickbooks", self.nango_provider_key_quickbooks)

            # Validate critical Supabase credentials are present
            # These are REQUIRED for backend to function
            if not self.supabase_url or not self.supabase_anon_key:
                logger.error("❌ CRITICAL: Company Supabase credentials not configured!")
                logger.error("   Required: supabase_url and supabase_anon_key")
                logger.error("   Company may still be provisioning. Please configure via master dashboard.")
                raise ValueError(
                    f"Company Supabase not configured for company_id: {self.company_id}. "
                    "Please update deployment credentials via master dashboard."
                )

            logger.info("🎉 Multi-tenant configuration complete!")

        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"❌ Failed to load from master Supabase: {e}")
            logger.warning("⚠️  Falling back to environment variables (if available)")
            # Don't raise - allow fallback to env vars

        return self

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore deprecated NEO4J_* env vars


# Global settings instance
settings = Settings()
