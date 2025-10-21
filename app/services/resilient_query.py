"""
Resilient Query Service
Wraps query operations with circuit breakers for production resilience
"""
import logging
from typing import Dict, Any
from app.core.circuit_breakers import with_openai_retry, with_neo4j_retry, with_qdrant_retry

logger = logging.getLogger(__name__)


class ResilientQueryWrapper:
    """
    Wrapper for query engine that adds circuit breakers and retry logic.
    
    This prevents cascading failures when external services have issues.
    """
    
    def __init__(self, query_engine):
        self.query_engine = query_engine
        logger.info("✅ Resilient query wrapper initialized with circuit breakers")
    
    @with_openai_retry
    async def query_with_retry(self, query_text: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute query with automatic retry on transient failures.
        
        Retries on:
        - OpenAI rate limits (429)
        - OpenAI connection errors
        - OpenAI timeouts
        
        Args:
            query_text: The user's query
            filters: Optional metadata filters
        
        Returns:
            Query results with answer and sources
        """
        try:
            logger.debug(f"Executing query with circuit breaker: {query_text[:100]}...")
            
            # Execute the actual query (with automatic retry on failures)
            result = await self.query_engine.query(query_text, filters=filters)
            
            logger.info(f"✅ Query successful: {len(result.get('source_nodes', []))} sources")
            return result
            
        except Exception as e:
            logger.error(f"❌ Query failed after retries: {e}")
            # Re-raise to let caller handle
            raise
    
    def query_sync(self, query_text: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Synchronous query with retry logic.
        Useful for worker processes or sync contexts.
        """
        # LlamaIndex query engine is synchronous by default
        return self._query_sync_with_retry(query_text, filters)
    
    @with_openai_retry
    def _query_sync_with_retry(self, query_text: str, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Internal sync query with retry decorator"""
        try:
            result = self.query_engine.query(query_text, filters=filters)
            logger.info(f"✅ Sync query successful: {len(result.get('source_nodes', []))} sources")
            return result
        except Exception as e:
            logger.error(f"❌ Sync query failed after retries: {e}")
            raise


def wrap_query_engine_with_resilience(query_engine):
    """
    Factory function to wrap a query engine with resilience patterns.
    
    Usage:
        engine = HybridQueryEngine()
        resilient_engine = wrap_query_engine_with_resilience(engine)
        result = await resilient_engine.query_with_retry("What's the status?")
    """
    return ResilientQueryWrapper(query_engine)

