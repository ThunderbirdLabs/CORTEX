"""
Dramatiq Background Worker
Processes long-running sync jobs (Gmail, Drive, Outlook) asynchronously

Run with:
    dramatiq app.services.background.tasks -p 4 -t 4

Deployment (Render):
    - Type: Background Worker
    - Build Command: pip install -r requirements.txt
    - Start Command: dramatiq app.services.background.tasks -p 4 -t 4
    - Environment: Same as main app + REDIS_URL + SENTRY_DSN
"""
import logging
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Sentry for error tracking (if configured)
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=os.getenv("ENVIRONMENT", "production"),
            traces_sample_rate=0.1,  # 10% of requests for performance monitoring
            profiles_sample_rate=0.1,
            integrations=[
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
            ]
        )
        logger.info("✅ Sentry initialized in worker")
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize Sentry in worker: {e}")
else:
    logger.info("ℹ️  Sentry not configured (SENTRY_DSN not set)")

# Import broker and tasks (this registers them with Dramatiq)
from app.services.background import broker
from app.services.background.tasks import sync_gmail_task, sync_drive_task, sync_outlook_task

logger.info("🚀 Dramatiq worker initialized")
logger.info(f"   Redis: {os.getenv('REDIS_URL', 'NOT_SET')[:30]}...")
logger.info(f"   Registered tasks: sync_gmail_task, sync_drive_task, sync_outlook_task")
logger.info("   Waiting for jobs...")

