"""
Pydantic models for API requests and responses
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================================================
# REQUEST MODELS
# ============================================================================

class DocumentIngest(BaseModel):
    """Request model for document ingestion"""
    content: str = Field(..., description="Full document text content")
    document_name: str = Field(..., description="Name/title of the document")
    source: str = Field(..., description="Source system (gmail, slack, hubspot, etc.)")
    document_type: str = Field(..., description="Document type (email, doc, deal, meeting, etc.)")
    reference_time: Optional[datetime] = Field(None, description="When the document was created")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class Message(BaseModel):
    """Chat message"""
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class SearchQuery(BaseModel):
    """Request model for hybrid search"""
    query: str = Field(..., description="Search query text")
    vector_limit: int = Field(5, description="Max vector search results", ge=1, le=20)
    graph_limit: int = Field(5, description="Max knowledge graph results", ge=1, le=20)
    source_filter: Optional[str] = Field(None, description="Filter by source (gmail, slack, etc.)")
    conversation_history: Optional[List[Message]] = Field(default=[], description="Previous messages for context")


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class DocumentIngestResponse(BaseModel):
    """Response model for document ingestion"""
    success: bool
    episode_id: str
    document_name: str
    source: str
    document_type: str
    num_chunks: int
    message: str


class VectorResult(BaseModel):
    """Vector search result"""
    id: str
    document_name: str
    source: str
    document_type: str
    content: str
    chunk_index: int
    episode_id: str
    similarity: float
    metadata: Optional[Dict[str, Any]]


class GraphResult(BaseModel):
    """Knowledge graph result"""
    type: str
    relation_name: str
    fact: str
    source_node_id: str
    target_node_id: str
    valid_at: Optional[str]
    episodes: List[str]


class SearchResponse(BaseModel):
    """Response model for hybrid search"""
    success: bool
    query: str
    answer: str  # AI-generated conversational answer
    vector_results: List[VectorResult]
    graph_results: List[GraphResult]
    num_episodes: int
    message: str


class EpisodeContextResponse(BaseModel):
    """Response model for episode context"""
    success: bool
    episode_id: str
    chunks: List[Dict[str, Any]]
    total_chunks: int


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    vector_db: str
    knowledge_graph: str
