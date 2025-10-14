"""
Knowledge Graph Schemas
Custom node and relationship types for multi-app knowledge graph
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field


# ============================================================================
# NODE TYPES
# ============================================================================

class Person(BaseModel):
    """Individual contact across all platforms"""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None


class Company(BaseModel):
    """Business, client, vendor, or partner organization"""
    name: str
    industry: Optional[str] = None
    size: Optional[str] = None
    website: Optional[str] = None
    location: Optional[str] = None
    revenue: Optional[str] = None


class Team(BaseModel):
    """Department, group, or project team"""
    name: str
    department: Optional[str] = None
    purpose: Optional[str] = None
    size: Optional[int] = None


class EmailMessage(BaseModel):
    """Email message"""
    subject: Optional[str] = None
    content: str
    platform: str  # gmail, outlook
    timestamp: Optional[datetime] = None
    thread_id: Optional[str] = None


class Document(BaseModel):
    """File, PDF, spreadsheet, presentation"""
    title: str
    doc_type: str  # pdf, docx, xlsx, pptx, etc.
    content_summary: Optional[str] = None
    file_path: Optional[str] = None
    platform: str  # google_drive, sharepoint, local, etc.
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None


class Meeting(BaseModel):
    """Calendar event, video call"""
    title: str
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    platform: str  # zoom, teams, google_meet, etc.
    meeting_url: Optional[str] = None


class Deal(BaseModel):
    """Sales opportunity, pipeline item"""
    name: str
    stage: str  # prospecting, qualified, proposal, negotiation, closed
    value: Optional[float] = None
    probability: Optional[int] = None  # 0-100
    close_date: Optional[datetime] = None
    source: str = "hubspot"  # hubspot, salesforce, etc.


class Topic(BaseModel):
    """Theme, subject, keyword, tag"""
    name: str
    category: Optional[str] = None
    description: Optional[str] = None


# ============================================================================
# RELATIONSHIP TYPES
# ============================================================================

class WorksFor(BaseModel):
    """Person works for Company"""
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    employment_type: Optional[str] = None  # full-time, contract, etc.


class SentTo(BaseModel):
    """Message/Email sent from Person to Person/Company"""
    sent_at: datetime
    cc: Optional[List[str]] = None
    bcc: Optional[List[str]] = None


class MentionedIn(BaseModel):
    """Person/Company mentioned in Message/Document"""
    context: Optional[str] = None
    sentiment: Optional[str] = None  # positive, neutral, negative


class RelatedTo(BaseModel):
    """General relationship between entities"""
    relationship_type: str
    strength: Optional[float] = None  # 0.0 to 1.0
    context: Optional[str] = None


class Authored(BaseModel):
    """Person authored Document/Message"""
    created_at: Optional[datetime] = None
    role: Optional[str] = None  # author, contributor, editor


class ParticipatedIn(BaseModel):
    """Person participated in Meeting/Thread"""
    role: Optional[str] = None  # organizer, attendee, optional
    duration: Optional[int] = None  # minutes


class Owns(BaseModel):
    """Person owns Deal/Project"""
    assigned_at: Optional[datetime] = None
    ownership_percentage: Optional[int] = None


class Discussed(BaseModel):
    """Message/Meeting discussed Topic"""
    relevance_score: Optional[float] = None
    sentiment: Optional[str] = None
    key_points: Optional[List[str]] = None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_all_node_types():
    """Returns all custom node types"""
    return {
        "Person": Person,
        "Company": Company,
        "Team": Team,
        "EmailMessage": EmailMessage,
        "Document": Document,
        "Meeting": Meeting,
        "Deal": Deal,
        "Topic": Topic,
    }


def get_all_relationship_types():
    """Returns all custom relationship types"""
    return {
        "WORKS_FOR": WorksFor,
        "SENT_TO": SentTo,
        "MENTIONED_IN": MentionedIn,
        "RELATED_TO": RelatedTo,
        "AUTHORED": Authored,
        "PARTICIPATED_IN": ParticipatedIn,
        "OWNS": Owns,
        "DISCUSSED": Discussed,
    }
