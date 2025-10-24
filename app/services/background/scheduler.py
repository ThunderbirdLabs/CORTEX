"""
Dramatiq Periodic Task Scheduler with Distributed Lock
Handles recurring background jobs using Dramatiq APScheduler middleware.

IMPORTANT: Uses Redis distributed lock to prevent duplicate execution
when running multiple scheduler instances (e.g., Render auto-scaling).
"""
import logging
import os
import time
import redis
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.services.background.tasks import deduplicate_entities_task

logger = logging.getLogger(__name__)

# Distributed lock configuration
REDIS_URL = os.getenv("REDIS_URL")
SCHEDULER_LOCK_KEY = "cortex:scheduler:lock"
SCHEDULER_LOCK_TIMEOUT = 120  # seconds (2 minutes - longer to prevent race conditions)


def acquire_scheduler_lock(redis_client):
    """
    Acquire distributed lock to ensure only ONE scheduler runs across all instances.

    Returns:
        bool: True if lock acquired, False otherwise
    """
    try:
        # SET key value NX EX 60 - atomic operation
        # NX = only set if doesn't exist
        # EX = expiration in seconds
        acquired = redis_client.set(
            SCHEDULER_LOCK_KEY,
            "locked",
            nx=True,
            ex=SCHEDULER_LOCK_TIMEOUT
        )
        return bool(acquired)
    except Exception as e:
        logger.error(f"Failed to acquire scheduler lock: {e}")
        return False


def start_periodic_scheduler():
    """
    Start periodic task scheduler for Dramatiq workers.

    This should run in a SEPARATE process from the main FastAPI app.
    On Render, this runs as a background worker service.

    IMPORTANT: Uses distributed lock - only ONE instance will run scheduler,
    even if multiple processes start simultaneously.

    Usage:
        python -m app.services.background.scheduler
    """
    # Force print to stdout for Render logs
    print("🚀 Starting cortex-scheduler process...")
    print(f"   REDIS_URL configured: {bool(REDIS_URL)}")

    if not REDIS_URL:
        print("❌ REDIS_URL not set - scheduler requires Redis for distributed locking")
        logger.error("❌ REDIS_URL not set - scheduler requires Redis for distributed locking")
        return

    # Connect to Redis
    print("📡 Connecting to Redis...")
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    print("✅ Redis connected")

    # Check if lock exists and how long it's been held
    print("🔍 Checking for existing lock...")
    lock_ttl = redis_client.ttl(SCHEDULER_LOCK_KEY)
    if lock_ttl > 0:
        print(f"   ⚠️  Lock exists, TTL: {lock_ttl} seconds")
        print(f"   Will retry after lock expires (max {lock_ttl}s)")
    elif lock_ttl == -1:
        print("   ⚠️  Lock exists with NO expiration (stale lock from crash)")
        print("   🧹 Clearing stale lock...")
        redis_client.delete(SCHEDULER_LOCK_KEY)
        print("   ✅ Stale lock cleared")

    # Try to acquire distributed lock
    print("🔒 Attempting to acquire scheduler lock...")
    logger.info("Attempting to acquire scheduler lock...")
    if not acquire_scheduler_lock(redis_client):
        print("⚠️  Another scheduler instance is already running. Exiting.")
        print("   (This is normal when running multiple Render instances)")
        logger.info("⚠️  Another scheduler instance is already running. Exiting.")
        logger.info("   (This is normal when running multiple Render instances)")
        return

    print("✅ Scheduler lock acquired - starting scheduler")
    logger.info("✅ Scheduler lock acquired - starting scheduler")

    scheduler = BlockingScheduler()

    # Schedule entity deduplication every 15 minutes
    scheduler.add_job(
        func=lambda: deduplicate_entities_task.send(),
        trigger=IntervalTrigger(minutes=15),
        id='entity_deduplication',
        name='Entity Deduplication (every 15 min)',
        replace_existing=True,
        max_instances=1  # Prevent overlapping executions
    )

    print("=" * 80)
    print("Dramatiq Periodic Scheduler Started (with distributed lock)")
    print("=" * 80)
    print("📅 Scheduled Jobs:")
    print("   - Entity Deduplication: Every 15 minutes")
    print("=" * 80)

    logger.info("=" * 80)
    logger.info("Dramatiq Periodic Scheduler Started (with distributed lock)")
    logger.info("=" * 80)
    logger.info("📅 Scheduled Jobs:")
    logger.info("   - Entity Deduplication: Every 15 minutes")
    logger.info("=" * 80)

    try:
        # Renew lock every 30 seconds in background
        def renew_lock():
            redis_client.expire(SCHEDULER_LOCK_KEY, SCHEDULER_LOCK_TIMEOUT)

        print("📝 Adding lock renewal job...")
        scheduler.add_job(
            func=renew_lock,
            trigger=IntervalTrigger(seconds=30),
            id='lock_renewal',
            name='Lock Renewal',
            replace_existing=True
        )

        print("🎬 Starting scheduler (this will block)...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        print("⚠️  Scheduler stopped - releasing lock")
        logger.info("Scheduler stopped - releasing lock")
        redis_client.delete(SCHEDULER_LOCK_KEY)
    except Exception as e:
        print(f"❌ Scheduler error: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        logger.error(f"Scheduler error: {e}", exc_info=True)
        redis_client.delete(SCHEDULER_LOCK_KEY)
        raise


if __name__ == "__main__":
    start_periodic_scheduler()
