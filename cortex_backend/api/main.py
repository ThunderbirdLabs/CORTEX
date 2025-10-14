"""
Cortex Hybrid RAG API
Main FastAPI application with modular routers
"""
import nest_asyncio
nest_asyncio.apply()  # Enable nested async for LlamaIndex

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routers import health, ingest, episodes, search_llamaindex
from backend.core.pipeline import HybridRAGPipeline
from backend.core.search import HybridSearch


# Initialize FastAPI application
app = FastAPI(
    title="Cortex Hybrid RAG API",
    description="AI-powered hybrid RAG platform combining vector search and knowledge graphs",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware - configure for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",      # Next.js default
        "http://localhost:3001",      # Simple chatbot
        "http://localhost:5173",      # Vite default
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(search_llamaindex.router)  # Optimized LlamaIndex + semantic reranking
app.include_router(episodes.router)


# Lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    print("🚀 Starting Cortex Hybrid RAG API")
    print("   - Vector DB: Qdrant Cloud")
    print("   - Knowledge Graph: Neo4j Aura + Graphiti")
    print("   - LLM: OpenAI gpt-4o-mini")
    print("   - LlamaIndex-powered search: /api/search-llamaindex")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    print("🛑 Shutting down Cortex API")
    # Close database connections if needed
    # Note: HybridRAGPipeline and HybridSearch have their own close() methods
    # but they're called per-request, not globally


# Development server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
