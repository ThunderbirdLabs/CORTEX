"""
Daily Reports - Data Models

Pydantic models for type safety and validation.
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import date, datetime


class ReportType:
    """Report type constants."""
    CLIENT_RELATIONSHIPS = "client_relationships"
    OPERATIONS = "operations"


class SourceDocument(BaseModel):
    """Source document reference in a report."""
    document_id: str
    title: str
    created_at: str
    document_type: str
    excerpt: str = Field(..., description="Relevant excerpt from document")
    score: Optional[float] = None


class ReportSection(BaseModel):
    """A section within a daily report."""
    title: str = Field(..., description="Section heading")
    content: str = Field(..., description="Section content (markdown)")
    sources: List[SourceDocument] = Field(default_factory=list)
    evolution_note: Optional[str] = Field(
        default=None,
        description="Note about how this evolved from previous day (e.g., 'Update: ACME issue resolved')"
    )
    order: int = Field(..., description="Display order")


class DailyReport(BaseModel):
    """Complete daily report."""
    report_type: Literal["client_relationships", "operations"]
    report_date: date
    tenant_id: str

    executive_summary: str = Field(..., description="One paragraph overview")
    sections: List[ReportSection] = Field(..., description="Structured report sections")

    # Metadata
    generated_at: datetime
    generation_duration_ms: int
    total_sources: int
    sub_questions_asked: List[str] = Field(default_factory=list, description="All questions asked during generation")

    # For storage
    def to_db_dict(self) -> Dict[str, Any]:
        """Convert to database-ready dict."""
        return {
            "report_type": self.report_type,
            "report_date": self.report_date.isoformat(),
            "tenant_id": self.tenant_id,
            "full_report": self.model_dump(mode='json'),
            "generated_at": self.generated_at.isoformat(),
            "generation_duration_ms": self.generation_duration_ms,
            "total_sources": self.total_sources
        }


class ReportMemory(BaseModel):
    """Memory from previous day's report (for context injection)."""
    summary: str = Field(..., description="2-3 paragraph summary of previous day")
    key_items: Dict[str, Any] = Field(
        ...,
        description="Structured extraction of important items to follow up on",
        examples=[{
            "client_issues": [
                {"company": "ACME Corp", "issue": "late PO-123", "urgency": "high", "mentioned_on": "2025-11-11"}
            ],
            "pending_approvals": ["7020-9036", "7020-9037"],
            "scheduled_shipments": [
                {"company": "TTI Inc", "expected_date": "2025-11-13", "tracking": "885403557633"}
            ]
        }]
    )
    report_date: date = Field(..., description="Date this memory is from")
    report_type: str


class QueryAnswer(BaseModel):
    """Answer from a single RAG query."""
    question: str
    answer: str
    sources: List[SourceDocument]
    metadata: Dict[str, Any]


class ReportGenerationRequest(BaseModel):
    """Request to generate a daily report."""
    report_type: Literal["client_relationships", "operations"]
    target_date: Optional[date] = None  # Defaults to yesterday
    force_regenerate: bool = Field(default=False, description="Regenerate even if report exists")
