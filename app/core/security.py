"""
Security and Authentication
Handles JWT validation and API key authentication
"""
import logging
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
    Validate Supabase JWT and extract user UUID.

    Args:
        credentials: HTTP Bearer token from Authorization header
        supabase: Supabase client

    Returns:
        User's UUID from Supabase auth (used as tenant_id)

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    try:
        # Verify JWT using Supabase client
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

        logger.debug(f"Authenticated user: {user_id}")
        return user_id

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
        # No API key configured - allow access (dev mode)
        logger.warning("CORTEX_API_KEY not configured - skipping authentication")
        return api_key

    if api_key != settings.cortex_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return api_key
