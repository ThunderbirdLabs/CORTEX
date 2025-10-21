"""
Dramatiq Redis Broker Configuration
Handles background job queue for large sync operations
"""
import os
import logging
import dramatiq
from dramatiq.brokers.redis import RedisBroker
from dramatiq.middleware import TimeLimit, Retries

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    logger.warning("⚠️  REDIS_URL not set - background jobs will not work")
    # Create a stub broker for development
    redis_broker = RedisBroker()
else:
    redis_broker = RedisBroker(url=REDIS_URL)
    logger.info(f"✅ Redis broker initialized: {REDIS_URL[:20]}...")

# Configure retries and timeouts
redis_broker.add_middleware(TimeLimit(time_limit=3600000))  # 1 hour max per job
redis_broker.add_middleware(Retries(max_retries=3))

dramatiq.set_broker(redis_broker)
broker = redis_broker

