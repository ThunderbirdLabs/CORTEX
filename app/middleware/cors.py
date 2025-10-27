"""
CORS Configuration
Cross-Origin Resource Sharing settings for frontend access

SECURITY:
- Production: Only HTTPS origins
- Development: Localhost + HTTPS
- NO "null" origin (prevents file:// attacks)
"""
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware
from app.core.config import settings


def get_cors_middleware():
    """
    Returns configured CORS middleware with environment-based settings.

    SECURITY:
    - Production: Strict HTTPS-only origins
    - Dev/Staging: Include localhost for development
    - Never allows "null" origin (file:// protocol attacks)
    """
    # Production: HTTPS only
    if settings.environment == "production":
        allowed_origins = [
            "https://connectorfrontend.vercel.app",
            # Add your production frontend domains here
        ]
    else:
        # Development/Staging: HTTPS + localhost
        allowed_origins = [
            "https://connectorfrontend.vercel.app",
            "http://localhost:3000",  # Next.js dev server
            "http://localhost:5173",  # Vite dev server
            "http://localhost:8080",  # Backend dev
        ]
        # SECURITY: Do NOT include "null" - it allows file:// based attacks

    return FastAPICORSMiddleware, {
        "allow_origins": allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicit methods
        "allow_headers": [
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Request-ID",
        ],  # Explicit headers (more secure than "*")
        "expose_headers": ["X-Request-ID"],  # Headers frontend can read
        "max_age": 600,  # Cache preflight requests for 10 minutes
    }
