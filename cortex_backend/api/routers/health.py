"""
Health Check Endpoints
"""
from fastapi import APIRouter
from backend.models.api_models import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/", response_model=HealthResponse)
async def root():
    """Root health check endpoint"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        vector_db="supabase_pgvector",
        knowledge_graph="neo4j_graphiti"
    )


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Detailed health check"""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        vector_db="supabase_pgvector",
        knowledge_graph="neo4j_graphiti"
    )
