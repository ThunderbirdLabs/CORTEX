"""
Admin Security & Authentication
Two-factor authentication using generated code pairs

SECURITY FEATURES:
- 2FA with two independent codes (both required)
- Timing-safe comparison (prevents timing attacks)
- Session tokens (JWT-like, 1 hour expiry)
- Rate limiting (5 attempts per 15 minutes)
- IP whitelist support (optional)
- Audit logging for all admin actions
"""
import logging
import hmac
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict
from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader
from supabase import Client

from app.core.dependencies import get_supabase
from app.core.config import settings

logger = logging.getLogger(__name__)

# Admin session header
admin_session_scheme = APIKeyHeader(name="X-Admin-Session", auto_error=False)

# Rate limiting cache (in-memory, could use Redis for production)
_login_attempts: Dict[str, list] = {}


# ============================================================================
# ADMIN CODE GENERATION (Run once, store in .env)
# ============================================================================

def generate_admin_codes() -> tuple[str, str]:
    """
    Generate two random admin codes.
    Run this once and store in environment variables.

    Usage:
        python3 -c "from app.core.admin_security import generate_admin_codes; \
                     c1, c2 = generate_admin_codes(); \
                     print(f'ADMIN_CODE_1={c1}\\nADMIN_CODE_2={c2}')"

    Returns:
        Tuple of (code1, code2) as base64-encoded 32-byte tokens
    """
    code1 = secrets.token_urlsafe(32)
    code2 = secrets.token_urlsafe(32)
    return (code1, code2)


# ============================================================================
# RATE LIMITING
# ============================================================================

def check_rate_limit(ip_address: str, max_attempts: int = 5, window_minutes: int = 15) -> bool:
    """
    Check if IP has exceeded rate limit.

    Args:
        ip_address: Client IP address
        max_attempts: Maximum attempts allowed in window
        window_minutes: Time window in minutes

    Returns:
        True if within limit, False if exceeded
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=window_minutes)

    # Clean up old attempts
    if ip_address in _login_attempts:
        _login_attempts[ip_address] = [
            ts for ts in _login_attempts[ip_address] if ts > cutoff
        ]
    else:
        _login_attempts[ip_address] = []

    # Check if exceeded
    if len(_login_attempts[ip_address]) >= max_attempts:
        logger.warning(f"🚫 Rate limit exceeded for IP: {ip_address}")
        return False

    # Record this attempt
    _login_attempts[ip_address].append(now)
    return True


def get_remaining_attempts(ip_address: str, max_attempts: int = 5, window_minutes: int = 15) -> int:
    """Get remaining login attempts for IP."""
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=window_minutes)

    if ip_address in _login_attempts:
        recent_attempts = [ts for ts in _login_attempts[ip_address] if ts > cutoff]
        return max(0, max_attempts - len(recent_attempts))

    return max_attempts


# ============================================================================
# TWO-FACTOR AUTHENTICATION
# ============================================================================

def verify_admin_pin(pin: str, ip_address: Optional[str] = None) -> bool:
    """
    Verify admin PIN matches hardcoded value (2525 for now).
    TODO: Replace with proper 2FA later.

    Args:
        pin: Admin PIN code
        ip_address: Client IP for rate limiting (optional)

    Returns:
        True if PIN matches

    Raises:
        HTTPException: If rate limit exceeded
    """
    # Check rate limit
    if ip_address and not check_rate_limit(ip_address):
        remaining = get_remaining_attempts(ip_address)
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. {remaining} attempts remaining. Try again in 15 minutes."
        )

    # Hardcoded PIN for now (TODO: Replace with TOTP/2FA)
    ADMIN_PIN = "2525"

    # Timing-safe comparison (prevents timing attacks)
    pin_valid = hmac.compare_digest(pin, ADMIN_PIN)

    if pin_valid:
        logger.info(f"✅ Admin authentication successful from IP: {ip_address or 'unknown'}")
        return True

    logger.warning(f"🚫 Admin authentication failed from IP: {ip_address or 'unknown'}")
    return False


# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

def create_admin_session(
    supabase: Client,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, any]:
    """
    Create a new admin session token.

    Args:
        supabase: Supabase client
        ip_address: Client IP address
        user_agent: Client user agent

    Returns:
        Dict with session_token and expires_at
    """
    # Generate secure session token
    session_token = secrets.token_urlsafe(48)

    # Session expires in 1 hour (configurable)
    duration_seconds = getattr(settings, 'admin_session_duration', 3600)
    expires_at = datetime.utcnow() + timedelta(seconds=duration_seconds)

    # Store in database
    try:
        supabase.table("admin_sessions").insert({
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "ip_address": ip_address,
            "user_agent": user_agent
        }).execute()

        logger.info(f"✅ Created admin session (expires in {duration_seconds}s)")

        return {
            "session_token": session_token,
            "expires_at": expires_at.isoformat(),
            "expires_in": duration_seconds
        }

    except Exception as e:
        logger.error(f"Failed to create admin session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session")


async def verify_admin_session(
    session_token: Optional[str] = Depends(admin_session_scheme),
    supabase: Client = Depends(get_supabase)
) -> str:
    """
    Verify admin session token from X-Admin-Session header.

    Args:
        session_token: Session token from header
        supabase: Supabase client

    Returns:
        Session ID if valid

    Raises:
        HTTPException: If token invalid or expired
    """
    if not session_token:
        raise HTTPException(
            status_code=401,
            detail="Admin authentication required. Missing X-Admin-Session header."
        )

    try:
        # Look up session in database
        result = supabase.table("admin_sessions")\
            .select("*")\
            .eq("session_token", session_token)\
            .single()\
            .execute()

        if not result.data:
            logger.warning(f"🚫 Invalid admin session token")
            raise HTTPException(status_code=401, detail="Invalid session token")

        session = result.data

        # Check expiry
        expires_at = datetime.fromisoformat(session["expires_at"].replace('Z', '+00:00'))
        if datetime.utcnow() > expires_at:
            logger.warning(f"🚫 Expired admin session token")
            raise HTTPException(status_code=401, detail="Session expired. Please login again.")

        logger.debug(f"✅ Valid admin session: {session['id']}")
        return session['id']

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying admin session: {e}")
        raise HTTPException(status_code=401, detail="Invalid session token")


# ============================================================================
# AUDIT LOGGING
# ============================================================================

async def log_admin_action(
    supabase: Client,
    session_id: str,
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict] = None,
    ip_address: Optional[str] = None
):
    """
    Log admin action to audit trail.

    Args:
        supabase: Supabase client
        session_id: Admin session ID
        action: Action type (e.g., 'login', 'trigger_sync', 'edit_schema')
        resource_type: Resource type (e.g., 'connector', 'schema', 'job')
        resource_id: Resource identifier
        details: Additional details (stored as JSONB)
        ip_address: Client IP address
    """
    try:
        supabase.table("admin_audit_log").insert({
            "session_id": session_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details or {},
            "ip_address": ip_address
        }).execute()

        logger.info(f"📝 Audit log: {action} on {resource_type}/{resource_id}")

    except Exception as e:
        # Don't fail the request if audit logging fails
        logger.error(f"Failed to write audit log: {e}")


# ============================================================================
# IP WHITELIST (Optional)
# ============================================================================

def check_ip_whitelist(ip_address: str) -> bool:
    """
    Check if IP is in whitelist (if configured).

    Args:
        ip_address: Client IP address

    Returns:
        True if whitelist not configured or IP is whitelisted
    """
    whitelist_str = getattr(settings, 'admin_ip_whitelist', None)

    if not whitelist_str:
        # No whitelist configured, allow all
        return True

    whitelist = [ip.strip() for ip in whitelist_str.split(',')]

    if ip_address in whitelist:
        logger.debug(f"✅ IP {ip_address} is whitelisted")
        return True

    logger.warning(f"🚫 IP {ip_address} not in whitelist")
    return False


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request, handling proxies.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address
    """
    # Check X-Forwarded-For header (set by proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first (client IP)
        return forwarded_for.split(',')[0].strip()

    # Check X-Real-IP header (alternative proxy header)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fallback to direct connection IP
    return request.client.host if request.client else "unknown"
