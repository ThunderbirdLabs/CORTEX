"""
CORS Configuration
Cross-Origin Resource Sharing settings for frontend access
"""
from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware


def get_cors_middleware():
    """
    Returns configured CORS middleware.

    Allows frontend applications to call the API.
    """
    return FastAPICORSMiddleware, {
        "allow_origins": [
            "https://connectorfrontend.vercel.app",
            "http://localhost:3000",
            "http://localhost:5173",
        ],
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
