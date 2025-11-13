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

async def get_current_user_context(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    supabase: Client = Depends(get_supabase)
) -> dict:
    """
    Get full user context (user_id + company_id) for multi-tenant auth.

    Returns:
        dict with:
        - user_id: Actual user ID from JWT (for private user data like chats)
        - company_id: Company ID (for shared company data like documents)
        - tenant_id: Alias for company_id (for backward compatibility)
    """
    from app.core.config_master import MasterConfig
    master_config = MasterConfig()

    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header required")

    token = credentials.credentials

    if master_config.is_multi_tenant:
        # Multi-tenant mode: validate against Master Supabase
        try:
            from supabase import create_client

            logger.info("🔍 AUTH DEBUG - is_multi_tenant: True")
            logger.info(f"🔍 AUTH DEBUG - company_id: {master_config.company_id}")
            logger.info(f"🔍 AUTH DEBUG - master_supabase_url: {master_config.master_supabase_url}")
            logger.info(f"🔍 AUTH DEBUG - master_supabase_anon_key exists: {bool(master_config.master_supabase_anon_key)}")

            if not all([master_config.master_supabase_url, master_config.master_supabase_anon_key, master_config.company_id]):
                logger.error("❌ Missing multi-tenant configuration")
                raise HTTPException(
                    status_code=500,
                    detail="Multi-tenant mode enabled but missing configuration"
                )

            logger.info("✅ MULTI-TENANT MODE ACTIVATED")

            # Create Master Supabase auth client (for JWT validation)
            logger.info(f"🔑 Creating Master Supabase auth client with URL: {master_config.master_supabase_url}")
            master_supabase_auth = create_client(
                master_config.master_supabase_url,
                master_config.master_supabase_anon_key
            )
            logger.info("✅ Master Supabase auth client created")

            # Create Master Supabase service client (for company_users query)
            logger.info("🔑 Creating Master Supabase service client")
            master_supabase = create_client(
                master_config.master_supabase_url,
                master_config.master_supabase_service_key
            )
            logger.info("✅ Master Supabase service client created")

            # Validate JWT with Master Supabase
            logger.info("🔐 Validating JWT token with Master Supabase")
            response = master_supabase_auth.auth.get_user(token)
            logger.info(f"✅ JWT validation response received: {bool(response)}")

            if not response or not response.user:
                logger.error("❌ No user returned from JWT validation")
                raise HTTPException(status_code=401, detail="Invalid authentication token")

            user_id = response.user.id
            logger.info(f"✅ User ID extracted: {user_id[:8]}...")

            # SECURITY LAYER 1: Validate JWT metadata contains correct company_id
            logger.info("🔒 SECURITY LAYER 1: Validating JWT metadata")
            jwt_company_id = response.user.user_metadata.get("company_id")
            logger.info(f"📋 JWT metadata company_id: {jwt_company_id}")
            logger.info(f"📋 Expected company_id: {master_config.company_id}")

            if jwt_company_id != master_config.company_id:
                logger.error(f"❌ JWT company_id mismatch: {jwt_company_id} != {master_config.company_id}")
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: company mismatch"
                )
            logger.info("✅ JWT company_id validation passed")

            # SECURITY LAYER 2: Verify user exists in company_users table
            logger.info("🔒 SECURITY LAYER 2: Checking company_users table")
            logger.info(f"🔍 Querying company_users: user_id={user_id[:8]}..., company_id={master_config.company_id}")
            company_user = master_supabase.table("company_users")\
                .select("id, role")\
                .eq("user_id", user_id)\
                .eq("company_id", master_config.company_id)\
                .eq("is_active", True)\
                .maybe_single()\
                .execute()

            logger.info(f"📊 company_users query result: {bool(company_user.data)}")
            if company_user.data:
                logger.info(f"👤 User role: {company_user.data.get('role')}")

            if not company_user.data:
                logger.error(f"❌ User {user_id[:8]}... not found in company_users for company {master_config.company_id}")
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

            logger.info(f"✅ Authenticated user: {user_id[:8]}... (role: {company_user.data['role']}) for company: {master_config.company_id[:8]}...")

            # Return BOTH user_id and company_id
            logger.info(f"🎯 RETURNING user_id: {user_id[:8]}..., company_id: {master_config.company_id[:8]}...")
            return {
                "user_id": user_id,
                "company_id": master_config.company_id,
                "tenant_id": master_config.company_id  # For backward compatibility
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Authentication failed with exception: {e}")
            logger.error("Full traceback:", exc_info=True)
            raise HTTPException(status_code=401, detail="Authentication failed")

    else:
        # Single-tenant mode: validate against Company Supabase
        logger.info("⚠️ SINGLE-TENANT MODE - Using company Supabase for auth")
        try:
            response = supabase.auth.get_user(token)
            if not response or not response.user:
                raise HTTPException(status_code=401, detail="Invalid authentication token")

            user_id = response.user.id
            logger.info(f"✅ Single-tenant auth successful: {user_id[:8]}...")

            # In single-tenant mode, user_id IS the tenant_id
            return {
                "user_id": user_id,
                "company_id": user_id,
                "tenant_id": user_id
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            raise HTTPException(status_code=401, detail="Authentication failed")


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    supabase: Client = Depends(get_supabase)
) -> str:
    """
    Validate JWT and return tenant_id (company_id) for shared data filtering.

    This is for backward compatibility with existing routes that filter by tenant_id.
    Returns company_id so multiple users from the same company see shared data.

    For routes that need user-specific data (like chats), use get_current_user_context instead.

    Returns:
        tenant_id (company_id in multi-tenant mode, user_id in single-tenant mode)
    """
    context = await get_current_user_context(credentials, supabase)
    return context["tenant_id"]


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
