"""
CORTEX Master Control Plane - Backend API
Manages all company deployments from a central dashboard
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime, timedelta
import bcrypt
import secrets
import os
from supabase import create_client, Client

# ============================================================================
# Configuration
# ============================================================================

MASTER_SUPABASE_URL = os.getenv("MASTER_SUPABASE_URL")
MASTER_SUPABASE_SERVICE_KEY = os.getenv("MASTER_SUPABASE_SERVICE_KEY")

if not MASTER_SUPABASE_URL or not MASTER_SUPABASE_SERVICE_KEY:
    raise ValueError("Missing MASTER_SUPABASE_URL or MASTER_SUPABASE_SERVICE_KEY")

supabase: Client = create_client(MASTER_SUPABASE_URL, MASTER_SUPABASE_SERVICE_KEY)

# ============================================================================
# FastAPI App
# ============================================================================

app = FastAPI(
    title="CORTEX Master Control Plane API",
    description="Manage all CORTEX company deployments",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Vercel domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Models
# ============================================================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    session_token: str
    admin_id: str
    email: str
    name: str
    role: str
    expires_at: str

class CompanyCreate(BaseModel):
    slug: str
    name: str
    company_location: Optional[str] = None
    company_description: Optional[str] = None
    industries_served: Optional[List[str]] = []
    key_capabilities: Optional[List[str]] = []
    primary_contact_email: Optional[str] = None
    primary_contact_name: Optional[str] = None
    plan: str = "enterprise"

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    company_location: Optional[str] = None
    company_description: Optional[str] = None
    industries_served: Optional[List[str]] = None
    key_capabilities: Optional[List[str]] = None
    primary_contact_email: Optional[str] = None
    primary_contact_name: Optional[str] = None
    backend_url: Optional[str] = None
    frontend_url: Optional[str] = None

class SchemaCreate(BaseModel):
    company_id: str
    override_type: str  # "entity" or "relation"
    entity_type: Optional[str] = None
    relation_type: Optional[str] = None
    description: Optional[str] = None

class DeploymentCreate(BaseModel):
    company_id: str
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    neo4j_uri: str
    neo4j_user: str = "neo4j"
    neo4j_password: str
    qdrant_url: str
    qdrant_api_key: Optional[str] = None
    qdrant_collection_name: str
    redis_url: str
    openai_api_key: Optional[str] = None
    nango_secret_key: Optional[str] = None
    admin_pin_hash: str

class TeamMemberCreate(BaseModel):
    company_id: str
    name: str
    title: str
    role_description: Optional[str] = None
    reports_to: Optional[str] = None
    email: Optional[str] = None

class PromptUpdate(BaseModel):
    prompt_template: str
    prompt_name: Optional[str] = None
    prompt_description: Optional[str] = None

# ============================================================================
# Authentication
# ============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify bcrypt password."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )

def create_session_token() -> str:
    """Generate secure session token."""
    return secrets.token_urlsafe(32)

async def get_current_admin(authorization: Optional[str] = Header(None)):
    """Dependency to verify session token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    # Check session in database
    result = supabase.table("master_admin_sessions")\
        .select("*, master_admins(*)")\
        .eq("session_token", authorization)\
        .eq("is_active", True)\
        .single()\
        .execute()

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    session = result.data

    # Check expiration
    expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Session expired")

    return session["master_admins"]

# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Master admin login."""

    # Get admin by email
    result = supabase.table("master_admins")\
        .select("*")\
        .eq("email", request.email)\
        .eq("is_active", True)\
        .single()\
        .execute()

    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    admin = result.data

    # Verify password
    if not verify_password(request.password, admin["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Create session token
    session_token = create_session_token()
    expires_at = datetime.utcnow() + timedelta(hours=8)

    # Store session
    supabase.table("master_admin_sessions").insert({
        "admin_id": admin["id"],
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "is_active": True,
    }).execute()

    # Update last login
    supabase.table("master_admins").update({
        "last_login_at": datetime.utcnow().isoformat(),
    }).eq("id", admin["id"]).execute()

    return LoginResponse(
        session_token=session_token,
        admin_id=admin["id"],
        email=admin["email"],
        name=admin["name"],
        role=admin["role"],
        expires_at=expires_at.isoformat()
    )

@app.post("/auth/logout")
async def logout(admin = Depends(get_current_admin), authorization: str = Header(None)):
    """Logout and invalidate session."""

    supabase.table("master_admin_sessions")\
        .update({"is_active": False})\
        .eq("session_token", authorization)\
        .execute()

    return {"message": "Logged out successfully"}

# ============================================================================
# Company Endpoints
# ============================================================================

@app.get("/companies")
async def list_companies(admin = Depends(get_current_admin)):
    """List all companies."""

    result = supabase.table("companies")\
        .select("*")\
        .order("created_at", desc=True)\
        .execute()

    return result.data

@app.get("/companies/{company_id}")
async def get_company(company_id: str, admin = Depends(get_current_admin)):
    """Get company details."""

    result = supabase.table("companies")\
        .select("*")\
        .eq("id", company_id)\
        .single()\
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")

    return result.data

@app.post("/companies")
async def create_company(company: CompanyCreate, admin = Depends(get_current_admin)):
    """Create new company."""

    result = supabase.table("companies").insert({
        **company.model_dump(),
        "status": "provisioning",
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    # Log audit event
    supabase.table("audit_log_global").insert({
        "admin_id": admin["id"],
        "company_id": result.data[0]["id"],
        "action": "company_created",
        "details": {"company_slug": company.slug},
    }).execute()

    return result.data[0]

@app.patch("/companies/{company_id}")
async def update_company(
    company_id: str,
    updates: CompanyUpdate,
    admin = Depends(get_current_admin)
):
    """Update company details."""

    # Filter out None values
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()

    result = supabase.table("companies")\
        .update(update_data)\
        .eq("id", company_id)\
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")

    # Log audit event
    supabase.table("audit_log_global").insert({
        "admin_id": admin["id"],
        "company_id": company_id,
        "action": "company_updated",
        "details": update_data,
    }).execute()

    return result.data[0]

@app.delete("/companies/{company_id}")
async def delete_company(company_id: str, admin = Depends(get_current_admin)):
    """Soft delete company."""

    # Check permission
    if not admin.get("can_delete_companies"):
        raise HTTPException(status_code=403, detail="Permission denied")

    result = supabase.table("companies")\
        .update({"status": "deleted"})\
        .eq("id", company_id)\
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Company not found")

    # Log audit event
    supabase.table("audit_log_global").insert({
        "admin_id": admin["id"],
        "company_id": company_id,
        "action": "company_deleted",
    }).execute()

    return {"message": "Company deleted"}

# ============================================================================
# Schema Endpoints
# ============================================================================

@app.get("/schemas/{company_id}")
async def list_schemas(company_id: str, admin = Depends(get_current_admin)):
    """List schemas for a company."""

    result = supabase.table("company_schemas")\
        .select("*")\
        .eq("company_id", company_id)\
        .eq("is_active", True)\
        .order("created_at", desc=True)\
        .execute()

    return result.data

@app.post("/schemas")
async def create_schema(schema: SchemaCreate, admin = Depends(get_current_admin)):
    """Add custom schema for a company."""

    # Check permission
    if not admin.get("can_edit_schemas"):
        raise HTTPException(status_code=403, detail="Permission denied")

    result = supabase.table("company_schemas").insert({
        **schema.model_dump(),
        "created_by": admin["email"],
        "is_active": True,
    }).execute()

    # Log audit event
    supabase.table("audit_log_global").insert({
        "admin_id": admin["id"],
        "company_id": schema.company_id,
        "action": "schema_created",
        "details": {
            "override_type": schema.override_type,
            "entity_type": schema.entity_type,
            "relation_type": schema.relation_type,
        },
    }).execute()

    return result.data[0]

@app.delete("/schemas/{schema_id}")
async def delete_schema(schema_id: int, admin = Depends(get_current_admin)):
    """Deactivate a custom schema."""

    # Check permission
    if not admin.get("can_edit_schemas"):
        raise HTTPException(status_code=403, detail="Permission denied")

    result = supabase.table("company_schemas")\
        .update({"is_active": False})\
        .eq("id", schema_id)\
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Schema not found")

    return {"message": "Schema deleted"}

# ============================================================================
# Deployment Endpoints
# ============================================================================

@app.get("/deployments/{company_id}")
async def get_deployment(company_id: str, admin = Depends(get_current_admin)):
    """Get deployment configuration for a company."""

    # Check permission
    if not admin.get("can_view_deployments"):
        raise HTTPException(status_code=403, detail="Permission denied")

    result = supabase.table("company_deployments")\
        .select("*")\
        .eq("company_id", company_id)\
        .single()\
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Deployment not found")

    return result.data

@app.post("/deployments")
async def create_deployment(deployment: DeploymentCreate, admin = Depends(get_current_admin)):
    """Store deployment configuration."""

    # Check permission
    if not admin.get("can_edit_deployments"):
        raise HTTPException(status_code=403, detail="Permission denied")

    result = supabase.table("company_deployments").insert({
        **deployment.model_dump(),
    }).execute()

    # Log audit event
    supabase.table("audit_log_global").insert({
        "admin_id": admin["id"],
        "company_id": deployment.company_id,
        "action": "deployment_created",
    }).execute()

    return result.data[0]

# ============================================================================
# Team Member Endpoints
# ============================================================================

@app.get("/team-members/{company_id}")
async def list_team_members(company_id: str, admin = Depends(get_current_admin)):
    """List team members for a company."""

    result = supabase.table("company_team_members")\
        .select("*")\
        .eq("company_id", company_id)\
        .eq("is_active", True)\
        .order("created_at", desc=True)\
        .execute()

    return result.data

@app.post("/team-members")
async def create_team_member(member: TeamMemberCreate, admin = Depends(get_current_admin)):
    """Add team member."""

    result = supabase.table("company_team_members").insert({
        **member.model_dump(),
        "is_active": True,
    }).execute()

    return result.data[0]

# ============================================================================
# Prompt Management Endpoints
# ============================================================================

@app.get("/prompts/{company_id}")
async def list_prompts(company_id: str, admin = Depends(get_current_admin)):
    """List all prompts for a company."""

    result = supabase.table("company_prompts")\
        .select("*")\
        .eq("company_id", company_id)\
        .eq("is_active", True)\
        .order("prompt_key")\
        .execute()

    return result.data

@app.patch("/prompts/{company_id}/{prompt_key}")
async def update_prompt(
    company_id: str,
    prompt_key: str,
    updates: PromptUpdate,
    admin = Depends(get_current_admin)
):
    """Update a prompt for a company."""

    # Get current version
    current = supabase.table("company_prompts")\
        .select("version")\
        .eq("company_id", company_id)\
        .eq("prompt_key", prompt_key)\
        .eq("is_active", True)\
        .single()\
        .execute()

    if not current.data:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Filter out None values and increment version
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow().isoformat()
    update_data["version"] = (current.data.get("version") or 1) + 1

    result = supabase.table("company_prompts")\
        .update(update_data)\
        .eq("company_id", company_id)\
        .eq("prompt_key", prompt_key)\
        .eq("is_active", True)\
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Prompt not found")

    # Log audit event
    supabase.table("audit_log_global").insert({
        "admin_id": admin["id"],
        "company_id": company_id,
        "action": "prompt_updated",
        "details": {
            "prompt_key": prompt_key,
            "version": update_data["version"]
        },
    }).execute()

    return result.data[0]

# ============================================================================
# Dashboard Stats
# ============================================================================

@app.get("/stats")
async def get_stats(admin = Depends(get_current_admin)):
    """Get dashboard statistics."""

    # Count companies by status
    companies = supabase.table("companies").select("status").execute()

    stats = {
        "total_companies": len(companies.data),
        "active_companies": len([c for c in companies.data if c["status"] == "active"]),
        "trial_companies": len([c for c in companies.data if c["status"] == "trial"]),
        "provisioning": len([c for c in companies.data if c["status"] == "provisioning"]),
    }

    return stats

# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""

    try:
        # Test master Supabase connection
        supabase.table("companies").select("id").limit(1).execute()
        return {
            "status": "healthy",
            "master_supabase": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/")
async def root():
    """API root."""
    return {
        "name": "CORTEX Master Control Plane API",
        "version": "1.0.0",
        "status": "operational"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
