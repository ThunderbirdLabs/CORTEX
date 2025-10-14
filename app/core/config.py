"""
Unified Configuration
All environment variables and settings in one place
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


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

    database_url: str = Field(..., description="PostgreSQL connection string")
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_anon_key: str = Field(..., description="Supabase anonymous key")
    supabase_service_key: Optional[str] = Field(default=None, description="Supabase service key (for Cortex)")
    supabase_db_url: Optional[str] = Field(default=None, description="Direct Supabase DB URL")

    # ============================================================================
    # OAUTH (Nango)
    # ============================================================================

    nango_secret: str = Field(..., description="Nango API secret key")

    # Provider configurations
    nango_provider_key_outlook: Optional[str] = Field(default=None, description="Nango provider key for Outlook")
    nango_provider_key_gmail: Optional[str] = Field(default=None, description="Nango provider key for Gmail")

    # Connection IDs (optional - set after OAuth)
    nango_connection_id_outlook: Optional[str] = Field(default=None)
    nango_connection_id_gmail: Optional[str] = Field(default=None)

    # Microsoft Graph
    graph_tenant_id: Optional[str] = Field(default=None, description="Azure AD tenant ID")

    # ============================================================================
    # HYBRID RAG SYSTEM
    # ============================================================================

    # Vector Database (Qdrant)
    qdrant_url: str = Field(..., description="Qdrant Cloud URL")
    qdrant_api_key: str = Field(..., description="Qdrant API key")
    qdrant_collection_name: str = Field(default="cortex_documents", description="Qdrant collection name")

    # Knowledge Graph (Neo4j + Graphiti)
    neo4j_uri: str = Field(..., description="Neo4j Aura URI")
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: str = Field(..., description="Neo4j password")

    # LLM & Embeddings (OpenAI)
    openai_api_key: str = Field(..., description="OpenAI API key")

    # ============================================================================
    # API KEYS
    # ============================================================================

    cortex_api_key: Optional[str] = Field(default=None, description="API key for Cortex search endpoint")

    # ============================================================================
    # OPTIONAL SETTINGS
    # ============================================================================

    save_jsonl: bool = Field(default=False, description="Save emails to JSONL for debugging")
    semaphore_limit: int = Field(default=10, description="Graphiti concurrency limit")

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()
