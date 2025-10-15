"""
Knowledge Graph Schema
Defines typed entity and relationship models for Neo4j enrichment
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============================================================================
# ENUMS FOR CONSTRAINED VALUES
# ============================================================================

class SeniorityLevel(str, Enum):
    """Employee seniority levels"""
    JUNIOR = "Junior"
    MID = "Mid-Level"
    SENIOR = "Senior"
    LEAD = "Lead"
    MANAGER = "Manager"
    DIRECTOR = "Director"
    VP = "VP"
    C_LEVEL = "C-Level"
    FOUNDER = "Founder"


class CompanySize(str, Enum):
    """Company size categories"""
    STARTUP = "Startup"
    SMB = "Small Business"
    MID_MARKET = "Mid-Market"
    ENTERPRISE = "Enterprise"


class DealStage(str, Enum):
    """Sales deal stages"""
    PROSPECTING = "Prospecting"
    QUALIFICATION = "Qualification"
    PROPOSAL = "Proposal"
    NEGOTIATION = "Negotiation"
    CLOSED_WON = "Closed Won"
    CLOSED_LOST = "Closed Lost"


class ProjectStatus(str, Enum):
    """Project status"""
    PLANNING = "Planning"
    ACTIVE = "Active"
    ON_HOLD = "On Hold"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


# ============================================================================
# ENTITY TYPE MODELS
# ============================================================================

class Person(BaseModel):
    """Person entity - employee, contact, or external individual"""
    name: str = Field(description="Full name of the person")
    email: Optional[str] = Field(None, description="Email address")
    role: Optional[str] = Field(None, description="Job title or role")
    phone: Optional[str] = Field(None, description="Phone number")
    department: Optional[str] = Field(None, description="Department (Sales, Engineering, etc.)")
    seniority_level: Optional[SeniorityLevel] = Field(None, description="Seniority level")
    linkedin: Optional[str] = Field(None, description="LinkedIn profile URL")
    location: Optional[str] = Field(None, description="Geographic location")


class Company(BaseModel):
    """Company entity - customer, partner, competitor"""
    name: str = Field(description="Company name")
    industry: Optional[str] = Field(None, description="Industry (Healthcare, SaaS, Finance, etc.)")
    size: Optional[CompanySize] = Field(None, description="Company size")
    location: Optional[str] = Field(None, description="Headquarters location")
    website: Optional[str] = Field(None, description="Company website URL")
    revenue_range: Optional[str] = Field(None, description="Annual revenue range")
    description: Optional[str] = Field(None, description="Brief company description")


class Deal(BaseModel):
    """Deal/Opportunity entity - sales opportunity"""
    name: str = Field(description="Deal name")
    value: Optional[float] = Field(None, description="Deal value in dollars")
    stage: Optional[DealStage] = Field(None, description="Current deal stage")
    close_date: Optional[datetime] = Field(None, description="Expected or actual close date")
    probability: Optional[float] = Field(None, description="Win probability (0-100)")
    deal_type: Optional[str] = Field(None, description="New Business, Upsell, Renewal, etc.")
    description: Optional[str] = Field(None, description="Deal description")


class Project(BaseModel):
    """Project entity - internal project or initiative"""
    name: str = Field(description="Project name")
    status: Optional[ProjectStatus] = Field(None, description="Project status")
    start_date: Optional[datetime] = Field(None, description="Project start date")
    end_date: Optional[datetime] = Field(None, description="Project end date")
    budget: Optional[float] = Field(None, description="Project budget")
    description: Optional[str] = Field(None, description="Project description")


class Document(BaseModel):
    """Document entity - file, proposal, contract"""
    name: str = Field(description="Document name/title")
    document_type: Optional[str] = Field(None, description="Contract, Proposal, Report, etc.")
    created_date: Optional[datetime] = Field(None, description="Creation date")
    file_url: Optional[str] = Field(None, description="URL to document")
    description: Optional[str] = Field(None, description="Document summary")


class Message(BaseModel):
    """Message entity - Slack/Teams message"""
    name: str = Field(description="Message identifier or preview")
    channel: Optional[str] = Field(None, description="Channel or conversation name")
    timestamp: Optional[datetime] = Field(None, description="Message timestamp")
    platform: Optional[str] = Field(None, description="Slack, Teams, etc.")


class Meeting(BaseModel):
    """Meeting entity - calendar meeting"""
    name: str = Field(description="Meeting title")
    meeting_date: Optional[datetime] = Field(None, description="Meeting date/time")
    duration_minutes: Optional[int] = Field(None, description="Meeting duration")
    meeting_type: Optional[str] = Field(None, description="Sales Call, Standup, Review, etc.")
    location: Optional[str] = Field(None, description="Physical or virtual location")


class Product(BaseModel):
    """Product/Service entity"""
    name: str = Field(description="Product name")
    category: Optional[str] = Field(None, description="Product category")
    price: Optional[float] = Field(None, description="Product price")
    description: Optional[str] = Field(None, description="Product description")


class Location(BaseModel):
    """Location entity - office, city, region"""
    name: str = Field(description="Location name")
    location_type: Optional[str] = Field(None, description="Office, City, Region, Country")
    address: Optional[str] = Field(None, description="Physical address")


class Task(BaseModel):
    """Task entity - action item or TODO"""
    name: str = Field(description="Task description")
    status: Optional[str] = Field(None, description="Todo, In Progress, Done")
    due_date: Optional[datetime] = Field(None, description="Due date")
    priority: Optional[str] = Field(None, description="High, Medium, Low")


# ============================================================================
# ENTITY TYPES REGISTRY
# ============================================================================

ENTITY_TYPES = {
    "Person": Person,
    "Company": Company,
    "Deal": Deal,
    "Project": Project,
    "Document": Document,
    "Message": Message,
    "Meeting": Meeting,
    "Product": Product,
    "Location": Location,
    "Task": Task
}


# ============================================================================
# RELATIONSHIP TYPE MODELS
# ============================================================================

class WorksFor(BaseModel):
    """Person works for Company"""
    start_date: Optional[datetime] = Field(None, description="Employment start date")
    position: Optional[str] = Field(None, description="Position title")
    is_current: Optional[bool] = Field(True, description="Current employment")


class WorksOn(BaseModel):
    """Person works on Deal/Project"""
    start_date: Optional[datetime] = Field(None, description="When person started working on this")
    role_in_project: Optional[str] = Field(None, description="Role or responsibility")
    is_active: Optional[bool] = Field(True, description="Currently working on it")


class Manages(BaseModel):
    """Person manages Person"""
    start_date: Optional[datetime] = Field(None, description="When management relationship started")


class WithCustomer(BaseModel):
    """Deal with Company (customer)"""
    relationship_start: Optional[datetime] = Field(None, description="When relationship started")
    relationship_type: Optional[str] = Field(None, description="Customer, Prospect, etc.")


class OwnsDeal(BaseModel):
    """Person owns Deal"""
    assigned_date: Optional[datetime] = Field(None, description="When deal was assigned")


class AttendedMeeting(BaseModel):
    """Person attended Meeting"""
    role: Optional[str] = Field(None, description="Organizer, Participant, etc.")


class CreatedDocument(BaseModel):
    """Person created Document"""
    created_date: Optional[datetime] = Field(None, description="Creation date")


class References(BaseModel):
    """Document/Email references Deal/Project/Company"""
    mention_count: Optional[int] = Field(None, description="Number of mentions")


class LocatedIn(BaseModel):
    """Person/Company located in Location"""
    since: Optional[datetime] = Field(None, description="Since when")


class CollaboratesWith(BaseModel):
    """Person collaborates with Person"""
    context: Optional[str] = Field(None, description="Collaboration context")


# ============================================================================
# RELATIONSHIP TYPES REGISTRY
# ============================================================================

RELATIONSHIP_TYPES = {
    # Work relationships
    "WORKS_FOR": WorksFor,
    "WORKS_ON": WorksOn,
    "MANAGES": Manages,
    "REPORTS_TO": Manages,  # Same schema as Manages
    "COLLABORATES_WITH": CollaboratesWith,

    # Business relationships
    "WITH_CUSTOMER": WithCustomer,
    "PARTNER_WITH": BaseModel,
    "COMPETES_WITH": BaseModel,

    # Deal/Opportunity relationships
    "OWNS_DEAL": OwnsDeal,
    "ASSOCIATED_WITH": BaseModel,
    "USES_PRODUCT": BaseModel,

    # Communication/Event
    "ATTENDED_MEETING": AttendedMeeting,
    "SENT_EMAIL": BaseModel,
    "RECEIVED_EMAIL": BaseModel,
    "MENTIONED_IN": BaseModel,

    # Document relationships
    "CREATED_DOCUMENT": CreatedDocument,
    "REFERENCES": References,

    # Location
    "LOCATED_IN": LocatedIn
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_entity_schema(entity_type: str) -> Optional[type[BaseModel]]:
    """Get Pydantic schema for entity type"""
    return ENTITY_TYPES.get(entity_type)


def get_relationship_schema(rel_type: str) -> Optional[type[BaseModel]]:
    """Get Pydantic schema for relationship type"""
    return RELATIONSHIP_TYPES.get(rel_type)


def get_all_entity_types() -> List[str]:
    """Get list of all defined entity types"""
    return list(ENTITY_TYPES.keys())


def get_all_relationship_types() -> List[str]:
    """Get list of all defined relationship types"""
    return list(RELATIONSHIP_TYPES.keys())
