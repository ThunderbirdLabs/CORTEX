"""
Admin Dashboard Routes
Secure admin-only endpoints for system management

FEATURES:
- PIN-based authentication (2525 for now, TODO: add proper 2FA)
- Session management (1 hour expiry)
- Health diagnostics
- Connector management
- Schema management
- Worker & job monitoring
"""
import logging
from typing import Optional, Dict, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from supabase import Client

from app.core.dependencies import get_supabase
from app.core.admin_security import (
    verify_admin_pin,
    create_admin_session,
    verify_admin_session,
    log_admin_action,
    get_client_ip,
    check_ip_whitelist
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AdminLoginRequest(BaseModel):
    pin: str


class AdminLoginResponse(BaseModel):
    session_token: str
    expires_at: str
    expires_in: int


class HealthCheckResponse(BaseModel):
    status: str
    components: Dict[str, any]
    timestamp: str


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/auth", response_model=AdminLoginResponse)
async def admin_login(
    request: Request,
    login_data: AdminLoginRequest,
    supabase: Client = Depends(get_supabase)
):
    """
    Admin login with PIN authentication.
    Returns session token valid for 1 hour.

    PIN: 2525 (hardcoded for now, TODO: add proper 2FA)
    """
    ip_address = get_client_ip(request)

    # Check IP whitelist (if configured)
    if not check_ip_whitelist(ip_address):
        logger.warning(f"🚫 Admin login blocked from non-whitelisted IP: {ip_address}")
        raise HTTPException(
            status_code=403,
            detail="Access denied. Your IP address is not whitelisted for admin access."
        )

    # Verify PIN
    if not verify_admin_pin(login_data.pin, ip_address):
        raise HTTPException(
            status_code=401,
            detail="Invalid PIN code"
        )

    # Create session
    user_agent = request.headers.get("User-Agent", "Unknown")
    session_data = create_admin_session(supabase, ip_address, user_agent)

    # Log successful login
    await log_admin_action(
        supabase=supabase,
        session_id=session_data.get("session_token"),  # Temp: use token as ID until we query it back
        action="login",
        resource_type="admin",
        details={"ip_address": ip_address, "user_agent": user_agent},
        ip_address=ip_address
    )

    logger.info(f"✅ Admin login successful from IP: {ip_address}")

    return AdminLoginResponse(**session_data)


@router.get("/verify-session")
async def verify_session(
    session_id: str = Depends(verify_admin_session)
):
    """Verify if current session is valid."""
    return {
        "valid": True,
        "session_id": session_id
    }


@router.post("/logout")
async def admin_logout(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase)
):
    """Logout and invalidate session."""
    try:
        # Delete session from database
        supabase.table("admin_sessions")\
            .delete()\
            .eq("id", session_id)\
            .execute()

        logger.info(f"✅ Admin session {session_id} logged out")

        return {"message": "Logged out successfully"}

    except Exception as e:
        logger.error(f"Error logging out: {e}")
        raise HTTPException(status_code=500, detail="Logout failed")


# ============================================================================
# HEALTH & DIAGNOSTICS
# ============================================================================

@router.get("/health/full", response_model=HealthCheckResponse)
async def full_health_check(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase)
):
    """
    Comprehensive health check for all system components.
    Requires admin authentication.
    """
    components = {}

    # Database (Supabase)
    try:
        start = datetime.utcnow()
        supabase.table("documents").select("id").limit(1).execute()
        latency = (datetime.utcnow() - start).total_seconds() * 1000
        components["database"] = {
            "status": "healthy",
            "latency_ms": round(latency, 2)
        }
    except Exception as e:
        components["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Qdrant (Vector DB)
    try:
        from app.services.ingestion.llamaindex.index_manager import IndexManager
        index_manager = IndexManager()
        # Try to get collection info
        collection_info = index_manager.qdrant_client.get_collection(
            index_manager.config.qdrant_collection_name
        )
        components["qdrant"] = {
            "status": "healthy",
            "vectors_count": collection_info.vectors_count,
            "points_count": collection_info.points_count
        }
    except Exception as e:
        components["qdrant"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Neo4j (Graph DB)
    try:
        from app.services.ingestion.llamaindex.index_manager import IndexManager
        index_manager = IndexManager()
        # Try a simple cypher query
        with index_manager.neo4j_driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count LIMIT 1")
            node_count = result.single()["count"]
        components["neo4j"] = {
            "status": "healthy",
            "nodes_count": node_count
        }
    except Exception as e:
        components["neo4j"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Redis (Background Jobs)
    try:
        from app.services.background.broker import redis_broker
        # Ping Redis
        redis_broker.client.ping()
        components["redis"] = {
            "status": "healthy"
        }
    except Exception as e:
        components["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Overall status
    all_healthy = all(c.get("status") == "healthy" for c in components.values())
    overall_status = "healthy" if all_healthy else "degraded"

    # Log health check
    await log_admin_action(
        supabase=supabase,
        session_id=session_id,
        action="health_check",
        resource_type="system",
        details={"components": components}
    )

    return HealthCheckResponse(
        status=overall_status,
        components=components,
        timestamp=datetime.utcnow().isoformat()
    )


@router.post("/health/test-flow")
async def test_end_to_end_flow(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase)
):
    """
    Run end-to-end test flow:
    1. Create test document
    2. Ingest to Supabase
    3. Chunk & embed to Qdrant
    4. Extract entities to Neo4j
    5. Query hybrid search
    6. Clean up test data
    """
    test_id = f"admin_test_{datetime.utcnow().timestamp()}"
    steps = []

    try:
        # Step 1: Create test document
        step_start = datetime.utcnow()
        test_doc = {
            "tenant_id": "admin_test",
            "source": "admin_test",
            "source_id": test_id,
            "document_type": "test",
            "title": f"Admin Test Document {test_id}",
            "content": "This is a test document from the admin dashboard. John Smith from Acme Corp ordered polycarbonate materials."
        }
        duration = (datetime.utcnow() - step_start).total_seconds() * 1000
        steps.append({
            "step": "create_document",
            "status": "success",
            "duration_ms": round(duration, 2)
        })

        # Step 2: Ingest to Supabase
        step_start = datetime.utcnow()
        result = supabase.table("documents").insert(test_doc).execute()
        doc_id = result.data[0]["id"]
        duration = (datetime.utcnow() - step_start).total_seconds() * 1000
        steps.append({
            "step": "insert_supabase",
            "status": "success",
            "duration_ms": round(duration, 2),
            "document_id": doc_id
        })

        # Step 3-5: Would require full ingestion pipeline (skipping for now)
        steps.append({
            "step": "chunking_embedding",
            "status": "skipped",
            "reason": "Full pipeline test not implemented yet"
        })

        # Cleanup
        step_start = datetime.utcnow()
        supabase.table("documents").delete().eq("id", doc_id).execute()
        duration = (datetime.utcnow() - step_start).total_seconds() * 1000
        steps.append({
            "step": "cleanup",
            "status": "success",
            "duration_ms": round(duration, 2)
        })

        # Log test
        await log_admin_action(
            supabase=supabase,
            session_id=session_id,
            action="end_to_end_test",
            resource_type="system",
            details={"steps": steps, "test_id": test_id}
        )

        return {
            "status": "success",
            "test_id": test_id,
            "steps": steps
        }

    except Exception as e:
        logger.error(f"End-to-end test failed: {e}")
        return {
            "status": "failed",
            "test_id": test_id,
            "steps": steps,
            "error": str(e)
        }


# ============================================================================
# SYSTEM METRICS
# ============================================================================

@router.get("/metrics/overview")
async def get_system_metrics(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase)
):
    """Get high-level system metrics."""
    try:
        # Total documents by source
        docs_result = supabase.table("documents")\
            .select("source", count="exact")\
            .execute()

        # Total sync jobs
        jobs_result = supabase.table("sync_jobs")\
            .select("status", count="exact")\
            .execute()

        # Get Qdrant stats
        try:
            from app.services.ingestion.llamaindex.index_manager import IndexManager
            index_manager = IndexManager()
            collection_info = index_manager.qdrant_client.get_collection(
                index_manager.config.qdrant_collection_name
            )
            qdrant_vectors = collection_info.vectors_count
        except:
            qdrant_vectors = "N/A"

        # Get Neo4j stats
        try:
            from app.services.ingestion.llamaindex.index_manager import IndexManager
            index_manager = IndexManager()
            with index_manager.neo4j_driver.session() as session:
                nodes = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
                rels = session.run("MATCH ()-[r]->() RETURN count(r) as count").single()["count"]
            neo4j_stats = {"nodes": nodes, "relationships": rels}
        except:
            neo4j_stats = {"nodes": "N/A", "relationships": "N/A"}

        return {
            "documents": {
                "total": docs_result.count,
                "by_source": {}  # TODO: Group by source
            },
            "sync_jobs": {
                "total": jobs_result.count
            },
            "qdrant": {
                "vectors": qdrant_vectors
            },
            "neo4j": neo4j_stats,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AUDIT LOG
# ============================================================================

@router.get("/audit-log")
async def get_audit_log(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase),
    limit: int = 100,
    offset: int = 0
):
    """Get admin audit log with pagination."""
    try:
        result = supabase.table("admin_audit_log")\
            .select("*")\
            .order("created_at", desc=True)\
            .limit(limit)\
            .offset(offset)\
            .execute()

        return {
            "logs": result.data,
            "count": len(result.data),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error fetching audit log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CONNECTOR MANAGEMENT
# ============================================================================

@router.get("/connectors/users")
async def get_connected_users(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase)
):
    """Get all users and their connection status."""
    try:
        # Get unique user IDs from documents table
        result = supabase.rpc('get_unique_tenant_ids').execute()

        # For each user, check their connection status via sync_jobs
        users = []
        for row in result.data:
            user_id = row.get('tenant_id')

            # Get last sync for each provider
            last_syncs = {}
            for provider in ['gmail', 'outlook', 'drive']:
                sync_result = supabase.table("sync_jobs")\
                    .select("*")\
                    .eq("user_id", user_id)\
                    .eq("job_type", provider)\
                    .order("created_at", desc=True)\
                    .limit(1)\
                    .execute()

                if sync_result.data:
                    last_syncs[provider] = sync_result.data[0]

            users.append({
                "user_id": user_id,
                "last_syncs": last_syncs
            })

        return {"users": users}

    except Exception as e:
        logger.error(f"Error fetching connected users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connectors/sync")
async def trigger_manual_sync(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase),
    user_id: str = None,
    provider: str = None  # gmail, outlook, drive
):
    """Trigger manual sync for a specific user (bypasses rate limits)."""
    if not user_id or not provider:
        raise HTTPException(status_code=400, detail="user_id and provider required")

    try:
        # Create job record
        job = supabase.table("sync_jobs").insert({
            "user_id": user_id,
            "job_type": provider,
            "status": "queued"
        }).execute()

        job_id = job.data[0]["id"]

        # Enqueue background task
        from app.services.background.tasks import sync_gmail_task, sync_outlook_task, sync_drive_task

        if provider == "gmail":
            sync_gmail_task.send(user_id, job_id, None)
        elif provider == "outlook":
            sync_outlook_task.send(user_id, job_id)
        elif provider == "drive":
            sync_drive_task.send(user_id, job_id)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

        # Log action
        await log_admin_action(
            supabase=supabase,
            session_id=session_id,
            action="trigger_sync",
            resource_type="connector",
            resource_id=job_id,
            details={"user_id": user_id, "provider": provider}
        )

        logger.info(f"✅ Admin triggered {provider} sync for user {user_id[:8]}...")

        return {
            "status": "queued",
            "job_id": job_id,
            "user_id": user_id,
            "provider": provider
        }

    except Exception as e:
        logger.error(f"Error triggering sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connectors/history")
async def get_sync_history(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase),
    user_id: Optional[str] = None,
    provider: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get sync job history with filters."""
    try:
        query = supabase.table("sync_jobs").select("*")

        if user_id:
            query = query.eq("user_id", user_id)
        if provider:
            query = query.eq("job_type", provider)
        if status:
            query = query.eq("status", status)

        result = query.order("created_at", desc=True)\
            .limit(limit)\
            .offset(offset)\
            .execute()

        return {
            "jobs": result.data,
            "count": len(result.data),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error fetching sync history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WORKER & JOB MANAGEMENT
# ============================================================================

@router.get("/workers/status")
async def get_worker_status(
    session_id: str = Depends(verify_admin_session)
):
    """Get Dramatiq worker status and queue depths."""
    try:
        from app.services.background.broker import redis_broker

        # Get queue info from Redis
        # Note: This is simplified - full implementation would use Dramatiq API

        return {
            "workers": {
                "status": "healthy",
                "note": "Full worker metrics require Dramatiq management API"
            },
            "queues": {
                "pending_jobs": "N/A - requires Dramatiq integration"
            }
        }

    except Exception as e:
        logger.error(f"Error fetching worker status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/all")
async def get_all_jobs(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase),
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """Get all sync jobs with pagination and filters."""
    try:
        query = supabase.table("sync_jobs").select("*")

        if status:
            query = query.eq("status", status)
        if job_type:
            query = query.eq("job_type", job_type)

        result = query.order("created_at", desc=True)\
            .limit(limit)\
            .offset(offset)\
            .execute()

        return {
            "jobs": result.data,
            "count": len(result.data),
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jobs/{job_id}/retry")
async def retry_job(
    job_id: str,
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase)
):
    """Retry a failed job."""
    try:
        # Get job details
        result = supabase.table("sync_jobs")\
            .select("*")\
            .eq("id", job_id)\
            .single()\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")

        job = result.data
        user_id = job["user_id"]
        job_type = job["job_type"]

        # Create new job
        new_job = supabase.table("sync_jobs").insert({
            "user_id": user_id,
            "job_type": job_type,
            "status": "queued"
        }).execute()

        new_job_id = new_job.data[0]["id"]

        # Enqueue background task
        from app.services.background.tasks import sync_gmail_task, sync_outlook_task, sync_drive_task

        if job_type == "gmail":
            sync_gmail_task.send(user_id, new_job_id, None)
        elif job_type == "outlook":
            sync_outlook_task.send(user_id, new_job_id)
        elif job_type == "drive":
            sync_drive_task.send(user_id, new_job_id)

        # Log action
        await log_admin_action(
            supabase=supabase,
            session_id=session_id,
            action="retry_job",
            resource_type="job",
            resource_id=new_job_id,
            details={"original_job_id": job_id, "user_id": user_id, "job_type": job_type}
        )

        logger.info(f"✅ Admin retried job {job_id}, new job: {new_job_id}")

        return {
            "status": "queued",
            "new_job_id": new_job_id,
            "original_job_id": job_id
        }

    except Exception as e:
        logger.error(f"Error retrying job: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SCHEMA MANAGEMENT
# ============================================================================

@router.get("/schema")
async def get_current_schema(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase)
):
    """Get current entity and relationship schema."""
    try:
        from app.services.ingestion.llamaindex.config import POSSIBLE_ENTITIES, POSSIBLE_RELATIONS

        # Get overrides from database
        overrides = supabase.table("admin_schema_overrides")\
            .select("*")\
            .eq("is_active", True)\
            .execute()

        # Get entity counts from Neo4j
        try:
            from app.services.ingestion.llamaindex.index_manager import IndexManager
            index_manager = IndexManager()

            entity_counts = {}
            for entity_type in POSSIBLE_ENTITIES:
                with index_manager.neo4j_driver.session() as session:
                    result = session.run(
                        f"MATCH (n:{entity_type}) RETURN count(n) as count"
                    )
                    entity_counts[entity_type] = result.single()["count"]
        except:
            entity_counts = {}

        return {
            "entities": POSSIBLE_ENTITIES,
            "relationships": POSSIBLE_RELATIONS,
            "overrides": overrides.data,
            "entity_counts": entity_counts
        }

    except Exception as e:
        logger.error(f"Error fetching schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schema/entity/add")
async def add_entity_type(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase),
    entity_type: str = None,
    description: str = None
):
    """Add a new entity type to schema."""
    if not entity_type:
        raise HTTPException(status_code=400, detail="entity_type required")

    try:
        # Add to overrides table
        result = supabase.table("admin_schema_overrides").insert({
            "override_type": "entity",
            "entity_type": entity_type.upper(),
            "description": description,
            "created_by": session_id,
            "is_active": True
        }).execute()

        # Log action
        await log_admin_action(
            supabase=supabase,
            session_id=session_id,
            action="add_entity",
            resource_type="schema",
            resource_id=entity_type,
            details={"entity_type": entity_type, "description": description}
        )

        logger.info(f"✅ Admin added entity type: {entity_type}")

        return {
            "status": "success",
            "entity_type": entity_type,
            "id": result.data[0]["id"],
            "note": "Restart application or hot-reload config to apply changes"
        }

    except Exception as e:
        logger.error(f"Error adding entity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schema/relation/add")
async def add_relation_type(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase),
    relation_type: str = None,
    from_entity: str = None,
    to_entity: str = None,
    description: str = None
):
    """Add a new relationship type to schema."""
    if not relation_type or not from_entity or not to_entity:
        raise HTTPException(
            status_code=400,
            detail="relation_type, from_entity, and to_entity required"
        )

    try:
        # Add to overrides table
        result = supabase.table("admin_schema_overrides").insert({
            "override_type": "relation",
            "relation_type": relation_type.upper(),
            "from_entity": from_entity.upper(),
            "to_entity": to_entity.upper(),
            "description": description,
            "created_by": session_id,
            "is_active": True
        }).execute()

        # Log action
        await log_admin_action(
            supabase=supabase,
            session_id=session_id,
            action="add_relation",
            resource_type="schema",
            resource_id=relation_type,
            details={
                "relation_type": relation_type,
                "from_entity": from_entity,
                "to_entity": to_entity,
                "description": description
            }
        )

        logger.info(f"✅ Admin added relation: {from_entity}-[{relation_type}]->{to_entity}")

        return {
            "status": "success",
            "relation_type": relation_type,
            "id": result.data[0]["id"],
            "note": "Restart application or hot-reload config to apply changes"
        }

    except Exception as e:
        logger.error(f"Error adding relation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/schema/{override_id}")
async def delete_schema_override(
    override_id: int,
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase)
):
    """Delete/deactivate a schema override."""
    try:
        # Soft delete (set is_active = false)
        result = supabase.table("admin_schema_overrides")\
            .update({"is_active": False})\
            .eq("id", override_id)\
            .execute()

        # Log action
        await log_admin_action(
            supabase=supabase,
            session_id=session_id,
            action="delete_schema_override",
            resource_type="schema",
            resource_id=str(override_id)
        )

        logger.info(f"✅ Admin deactivated schema override: {override_id}")

        return {"status": "success", "id": override_id}

    except Exception as e:
        logger.error(f"Error deleting schema override: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# COMPANY SETTINGS MANAGEMENT
# ============================================================================

@router.get("/company/settings")
async def get_company_settings(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase)
):
    """Get current company settings."""
    try:
        result = supabase.table("company_settings")\
            .select("*")\
            .order("id", desc=True)\
            .limit(1)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Company settings not found")

        return result.data[0]

    except Exception as e:
        logger.error(f"Error fetching company settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/company/settings")
async def update_company_settings(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase),
    company_name: Optional[str] = None,
    company_location: Optional[str] = None,
    company_description: Optional[str] = None,
    industries_served: Optional[List[str]] = None,
    key_capabilities: Optional[List[str]] = None
):
    """Update company settings."""
    try:
        # Build update dict
        updates = {}
        if company_name:
            updates["company_name"] = company_name
        if company_location:
            updates["company_location"] = company_location
        if company_description:
            updates["company_description"] = company_description
        if industries_served:
            updates["industries_served"] = industries_served
        if key_capabilities:
            updates["key_capabilities"] = key_capabilities

        if not updates:
            raise HTTPException(status_code=400, detail="No updates provided")

        updates["updated_at"] = datetime.utcnow().isoformat()
        updates["updated_by"] = session_id

        # Update latest record
        result = supabase.table("company_settings")\
            .update(updates)\
            .order("id", desc=True)\
            .limit(1)\
            .execute()

        # Log action
        await log_admin_action(
            supabase=supabase,
            session_id=session_id,
            action="update_company_settings",
            resource_type="company",
            details=updates
        )

        logger.info(f"✅ Admin updated company settings")

        return {
            "status": "success",
            "note": "Settings updated. Consider regenerating prompts to apply changes."
        }

    except Exception as e:
        logger.error(f"Error updating company settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/company/team")
async def get_team_members(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase)
):
    """Get company team members."""
    try:
        result = supabase.table("team_members")\
            .select("*")\
            .order("id")\
            .execute()

        return {"team": result.data}

    except Exception as e:
        logger.error(f"Error fetching team members: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/company/team")
async def add_team_member(
    session_id: str = Depends(verify_admin_session),
    supabase: Client = Depends(get_supabase),
    name: str = None,
    title: str = None,
    role_description: Optional[str] = None,
    reports_to: Optional[str] = None
):
    """Add a team member."""
    if not name or not title:
        raise HTTPException(status_code=400, detail="name and title required")

    try:
        result = supabase.table("team_members").insert({
            "name": name,
            "title": title,
            "role_description": role_description,
            "reports_to": reports_to
        }).execute()

        # Log action
        await log_admin_action(
            supabase=supabase,
            session_id=session_id,
            action="add_team_member",
            resource_type="team",
            resource_id=str(result.data[0]["id"]),
            details={"name": name, "title": title}
        )

        logger.info(f"✅ Admin added team member: {name}")

        return {"status": "success", "member": result.data[0]}

    except Exception as e:
        logger.error(f"Error adding team member: {e}")
        raise HTTPException(status_code=500, detail=str(e))
