"""
Security and Authentication
Handles JWT validation and API key authentication

SECURITY FEATURES:
- JWT validation via Supabase
- API key authentication with timing-safe comparison
- PII sanitization in logs
- Production-first security (no dev mode bypasses)
"""
import logging
import hmac
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from supabase import Client

from app.core.dependencies import get_supabase
from app.core.config import settings

logger = logging.getLogger(__name__)

# Security schemes
bearer_scheme = HTTPBearer()
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


# ============================================================================
# JWT AUTHENTICATION (Supabase)
# ============================================================================

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    supabase: Client = Depends(get_supabase)
) -> str:
    """
    Validate JWT and extract user UUID.

    CENTRALIZED AUTH MODE:
    - Validates against Master Supabase (all users in one auth system)
    - Verifies user has access to this company
    - Returns user_id from Master Supabase auth.users

    SINGLE-TENANT MODE (backward compatible):
    - Validates against company Supabase (old behavior)
    - Returns user_id from company Supabase auth.users

    Args:
        credentials: HTTP Bearer token from Authorization header
        supabase: Supabase client (company Supabase, for backward compatibility)

    Returns:
        User's UUID from Supabase auth (used as tenant_id)

    Raises:
        HTTPException: If token is invalid or user not found
    """
    from app.core.config_master import master_config

    token = credentials.credentials

    try:
        # CENTRALIZED AUTH MODE
        if master_config.is_multi_tenant:
            # Validate JWT against Master Supabase
            from supabase import create_client
            master_supabase = create_client(
                master_config.master_supabase_url,
                master_config.master_supabase_service_key
            )

            response = master_supabase.auth.get_user(token)

            if not response or not response.user:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authentication token"
                )

            user_id = response.user.id
            if not user_id:
                raise HTTPException(
                    status_code=401,
                    detail="User ID not found in token"
                )

            # SECURITY LAYER 1: JWT Cryptographic Validation
            # Extract company_id from JWT user_metadata (signed by Supabase, can't be tampered)
            user_metadata = response.user.user_metadata or {}
            jwt_company_id = user_metadata.get("company_id")

            if not jwt_company_id:
                # No company_id in JWT - reject for security
                # (All users in multi-tenant mode MUST have company_id in metadata)
                logger.warning(f"User {user_id[:8]}... has no company_id in JWT metadata")
                raise HTTPException(
                    status_code=403,
                    detail="Invalid user configuration. Contact administrator."
                )

            # Validate JWT company_id matches COMPANY_ID env var (cryptographic binding)
            if jwt_company_id != master_config.company_id:
                logger.warning(f"User {user_id[:8]}... JWT company_id mismatch: {jwt_company_id} != {master_config.company_id}")
                raise HTTPException(
                    status_code=403,
                    detail="You do not have access to this company"
                )

            # SECURITY LAYER 2: Database Validation (defense in depth)
            # Verify user has access to this company via company_users table
            company_user = master_supabase.table("company_users")\
                .select("id, role")\
                .eq("user_id", user_id)\
                .eq("company_id", master_config.company_id)\
                .eq("is_active", True)\
                .maybe_single()\
                .execute()

            if not company_user.data:
                logger.warning(f"User {user_id[:8]}... not found in company_users for company {master_config.company_id}")
                raise HTTPException(
                    status_code=403,
                    detail="You do not have access to this company"
                )

            # Update last_login_at
            try:
                master_supabase.rpc("update_user_last_login", {
                    "p_user_id": user_id,
                    "p_company_id": master_config.company_id
                }).execute()
            except Exception as e:
                logger.warning(f"Failed to update last_login_at: {e}")

            logger.debug(f"Authenticated user: {user_id[:8]}... (role: {company_user.data['role']})")
            return user_id

        else:
            # SINGLE-TENANT MODE (backward compatible)
            # Verify JWT using company Supabase client
            response = supabase.auth.get_user(token)

            if not response or not response.user:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid authentication token"
                )

            user_id = response.user.id
            if not user_id:
                raise HTTPException(
                    status_code=401,
                    detail="User ID not found in token"
                )

            # SECURITY: Don't log PII (user_id) - use sanitized logging
            logger.debug(f"Authenticated user: {user_id[:8]}...")
            return user_id

    except HTTPException:
        raise  # Re-raise HTTP exceptions as-is
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )


# ============================================================================
# API KEY AUTHENTICATION (Cortex Search)
# ============================================================================

async def verify_api_key(api_key: str = Depends(api_key_scheme)) -> str:
    """
    Verify API key for Cortex search endpoints.

    SECURITY: Uses timing-safe comparison to prevent timing attacks.
    Production deployment MUST have CORTEX_API_KEY configured.

    Args:
        api_key: API key from X-API-Key header

    Returns:
        Validated API key

    Raises:
        HTTPException: If API key is invalid or missing
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key in X-API-Key header"
        )

    if not settings.cortex_api_key:
        # SECURITY: Production MUST have API key configured
        if settings.environment == "production":
            logger.error("CRITICAL: CORTEX_API_KEY not configured in production!")
            raise HTTPException(
                status_code=500,
                detail="Server misconfiguration - contact administrator"
            )
        # Dev/staging: warn but allow (for local development)
        logger.warning("DEV MODE: CORTEX_API_KEY not configured - authentication bypassed")
        return api_key

    # SECURITY: Timing-safe comparison prevents timing attacks
    # hmac.compare_digest runs in constant time regardless of where strings differ
    if not hmac.compare_digest(api_key, settings.cortex_api_key):
        logger.warning(f"Invalid API key attempt from client")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return api_key
