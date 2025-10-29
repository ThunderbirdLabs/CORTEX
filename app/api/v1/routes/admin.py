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
