"""
API Routes
All v1 API endpoints
"""
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.oauth import router as oauth_router
from app.api.v1.routes.webhook import router as webhook_router
from app.api.v1.routes.sync import router as sync_router
from app.api.v1.routes.search import router as search_router
from app.api.v1.routes.emails import router as emails_router
from app.api.v1.routes.upload import router as upload_router
from app.api.v1.routes.chat import router as chat_router

__all__ = [
    "health_router",
    "oauth_router",
    "webhook_router",
    "sync_router",
    "search_router",
    "emails_router",
    "upload_router",
    "chat_router",
]
