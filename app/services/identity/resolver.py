"""
Identity Resolution Service
Core logic for mapping platform-specific user IDs to canonical identities
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from supabase import Client
from app.services.identity.matcher import (
    normalize_email,
    extract_name_from_email,
    calculate_name_similarity,
    calculate_combined_match_score,
    same_email_domain,
    is_corporate_email
)

logger = logging.getLogger(__name__)

# Confidence thresholds for matching
CONFIDENCE_EXACT = 1.0
CONFIDENCE_AUTO_MERGE = 0.9
CONFIDENCE_REVIEW_QUEUE = 0.75


async def resolve_identity(
    supabase: Client,
    tenant_id: str,
    platform: str,
    email: Optional[str] = None,
    platform_user_id: Optional[str] = None,
    display_name: Optional[str] = None,
    raw_platform_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Resolve a platform-specific identity to a canonical identity.

    This is the MAIN ENTRY POINT for identity resolution. Called by all sync providers.

    Algorithm:
    1. Check if platform_user_id already exists → return existing canonical_id
    2. If email provided:
       a. Check if email exists in email_aliases → return canonical_id
       b. Fuzzy match by email domain + name similarity
    3. If no email:
       a. Fuzzy match by name only (for QuickBooks customers)
    4. If no match found → create new canonical identity

    Args:
        supabase: Supabase client
        tenant_id: Tenant identifier
        platform: Platform name ('gmail', 'outlook', 'quickbooks', 'slack', 'drive')
        email: User's email address (optional)
        platform_user_id: Platform-specific user ID
        display_name: How the name appears on that platform
        raw_platform_data: Original platform user object (stored for debugging)

    Returns:
        {
            "canonical_identity_id": UUID,
            "canonical_name": str,
            "canonical_email": str,
            "is_new": bool,
            "confidence": float,
            "match_reason": str
        }

    Example:
        # Gmail sync finds h.woodburn@company.com
        result = await resolve_identity(
            supabase=supabase_client,
            tenant_id="user-123",
            platform="gmail",
            email="h.woodburn@company.com",
            platform_user_id="h.woodburn@company.com",
            display_name="H. Woodburn"
        )
        # Returns existing canonical_id if Hayden Woodburn already exists
        # document.metadata['canonical_identity_id'] = result['canonical_identity_id']
    """

    # Step 1: Check if this platform identity already exists
    if platform_user_id:
        existing = await _get_existing_platform_identity(
            supabase, tenant_id, platform, platform_user_id
        )
        if existing:
            logger.info(
                f"Found existing platform identity: {platform}:{platform_user_id} → "
                f"{existing['canonical_identity_id']}"
            )
            return {
                "canonical_identity_id": existing["canonical_identity_id"],
                "canonical_name": existing["canonical_name"],
                "canonical_email": existing["canonical_email"],
                "is_new": False,
                "confidence": 1.0,
                "match_reason": "Exact platform identity match"
            }

    # Step 2: Try to match by email
    if email:
        normalized_email = normalize_email(email)

        # 2a. Exact email match
        email_match = await _get_canonical_by_email(supabase, tenant_id, normalized_email)
        if email_match:
            # Link this platform identity to existing canonical
            await _link_platform_identity(
                supabase,
                tenant_id=tenant_id,
                canonical_id=email_match["id"],
                platform=platform,
                platform_user_id=platform_user_id or email,
                platform_email=email,
                display_name=display_name,
                confidence=CONFIDENCE_EXACT,
                raw_platform_data=raw_platform_data
            )

            logger.info(
                f"Exact email match: {email} → {email_match['canonical_name']}"
            )
            return {
                "canonical_identity_id": email_match["id"],
                "canonical_name": email_match["canonical_name"],
                "canonical_email": email_match["canonical_email"],
                "is_new": False,
                "confidence": CONFIDENCE_EXACT,
                "match_reason": f"Exact email match: {email}"
            }

        # 2b. Fuzzy match by email domain + name similarity
        if display_name:
            fuzzy_match = await _fuzzy_match_by_email_and_name(
                supabase, tenant_id, email, display_name
            )

            if fuzzy_match and fuzzy_match["confidence"] >= CONFIDENCE_AUTO_MERGE:
                # High confidence match - auto-merge
                await _link_platform_identity(
                    supabase,
                    tenant_id=tenant_id,
                    canonical_id=fuzzy_match["canonical_id"],
                    platform=platform,
                    platform_user_id=platform_user_id or email,
                    platform_email=email,
                    display_name=display_name,
                    confidence=fuzzy_match["confidence"],
                    raw_platform_data=raw_platform_data
                )

                # Add email alias
                await _add_email_alias(
                    supabase,
                    tenant_id=tenant_id,
                    canonical_id=fuzzy_match["canonical_id"],
                    email=email,
                    source_platform=platform
                )

                logger.info(
                    f"High confidence fuzzy match: {email} + {display_name} → "
                    f"{fuzzy_match['canonical_name']} (confidence: {fuzzy_match['confidence']:.2f})"
                )
                return {
                    "canonical_identity_id": fuzzy_match["canonical_id"],
                    "canonical_name": fuzzy_match["canonical_name"],
                    "canonical_email": fuzzy_match["canonical_email"],
                    "is_new": False,
                    "confidence": fuzzy_match["confidence"],
                    "match_reason": fuzzy_match["reason"]
                }

            elif fuzzy_match and fuzzy_match["confidence"] >= CONFIDENCE_REVIEW_QUEUE:
                # Medium confidence - add to review queue
                await _create_merge_suggestion(
                    supabase,
                    tenant_id=tenant_id,
                    identity_a_id=fuzzy_match["canonical_id"],
                    identity_b_email=email,
                    identity_b_name=display_name,
                    similarity_score=fuzzy_match["confidence"],
                    matching_reason=fuzzy_match["reason"],
                    evidence=fuzzy_match.get("evidence", {})
                )
                logger.info(
                    f"Medium confidence match added to review queue: {email} + {display_name} "
                    f"→ {fuzzy_match['canonical_name']} (confidence: {fuzzy_match['confidence']:.2f})"
                )

    # Step 3: No match found - create new canonical identity
    canonical_name = display_name or extract_name_from_email(email) if email else "Unknown"
    canonical_email = email if email else None

    new_canonical = await _create_canonical_identity(
        supabase,
        tenant_id=tenant_id,
        canonical_name=canonical_name,
        canonical_email=canonical_email
    )

    # Link platform identity
    await _link_platform_identity(
        supabase,
        tenant_id=tenant_id,
        canonical_id=new_canonical["id"],
        platform=platform,
        platform_user_id=platform_user_id or email or canonical_name,
        platform_email=email,
        display_name=display_name,
        confidence=CONFIDENCE_EXACT,
        raw_platform_data=raw_platform_data
    )

    # Add email alias if provided
    if email:
        await _add_email_alias(
            supabase,
            tenant_id=tenant_id,
            canonical_id=new_canonical["id"],
            email=email,
            source_platform=platform,
            is_primary=True
        )

    logger.info(f"Created new canonical identity: {canonical_name} ({new_canonical['id']})")
    return {
        "canonical_identity_id": new_canonical["id"],
        "canonical_name": canonical_name,
        "canonical_email": canonical_email,
        "is_new": True,
        "confidence": CONFIDENCE_EXACT,
        "match_reason": "New identity created"
    }


async def resolve_identity_by_name(
    supabase: Client,
    tenant_id: str,
    name: str,
    platform: str,
    platform_user_id: str
) -> Dict[str, Any]:
    """
    Resolve identity by name only (no email).

    Use case: QuickBooks customers who only have a name, no email.

    Args:
        supabase: Supabase client
        tenant_id: Tenant identifier
        name: Person's name
        platform: Platform name
        platform_user_id: Platform-specific ID

    Returns:
        Same format as resolve_identity()
    """
    # Check if platform identity already exists
    existing = await _get_existing_platform_identity(
        supabase, tenant_id, platform, platform_user_id
    )
    if existing:
        return {
            "canonical_identity_id": existing["canonical_identity_id"],
            "canonical_name": existing["canonical_name"],
            "canonical_email": existing["canonical_email"],
            "is_new": False,
            "confidence": 1.0,
            "match_reason": "Exact platform identity match"
        }

    # Fuzzy match by name only
    fuzzy_match = await _fuzzy_match_by_name(supabase, tenant_id, name)

    if fuzzy_match and fuzzy_match["confidence"] >= CONFIDENCE_REVIEW_QUEUE:
        # Add to review queue (require human verification for name-only matches)
        await _create_merge_suggestion(
            supabase,
            tenant_id=tenant_id,
            identity_a_id=fuzzy_match["canonical_id"],
            identity_b_email=None,
            identity_b_name=name,
            similarity_score=fuzzy_match["confidence"],
            matching_reason=f"Name-only match: {fuzzy_match['reason']}",
            evidence=fuzzy_match.get("evidence", {})
        )
        logger.info(
            f"Name-only match added to review queue: {name} → "
            f"{fuzzy_match['canonical_name']} (confidence: {fuzzy_match['confidence']:.2f})"
        )

    # Create new canonical identity
    new_canonical = await _create_canonical_identity(
        supabase,
        tenant_id=tenant_id,
        canonical_name=name,
        canonical_email=None
    )

    await _link_platform_identity(
        supabase,
        tenant_id=tenant_id,
        canonical_id=new_canonical["id"],
        platform=platform,
        platform_user_id=platform_user_id,
        platform_email=None,
        display_name=name,
        confidence=CONFIDENCE_EXACT
    )

    logger.info(f"Created new canonical identity (name-only): {name} ({new_canonical['id']})")
    return {
        "canonical_identity_id": new_canonical["id"],
        "canonical_name": name,
        "canonical_email": None,
        "is_new": True,
        "confidence": CONFIDENCE_EXACT,
        "match_reason": "New identity created (name-only)"
    }


async def get_canonical_identity(
    supabase: Client,
    tenant_id: str,
    canonical_id: UUID
) -> Optional[Dict[str, Any]]:
    """
    Get full canonical identity details including all platform IDs and email aliases.

    Args:
        supabase: Supabase client
        tenant_id: Tenant identifier
        canonical_id: Canonical identity UUID

    Returns:
        {
            "id": UUID,
            "canonical_name": str,
            "canonical_email": str,
            "platform_identities": [{platform, platform_user_id, display_name}, ...],
            "email_aliases": [str, ...]
        }
    """
    # Get canonical record
    canonical_result = supabase.table("canonical_identities").select("*").eq(
        "tenant_id", tenant_id
    ).eq("id", str(canonical_id)).limit(1).execute()

    if not canonical_result.data:
        return None

    canonical = canonical_result.data[0]

    # Get all platform identities
    platform_result = supabase.table("platform_identities").select("*").eq(
        "tenant_id", tenant_id
    ).eq("canonical_identity_id", str(canonical_id)).execute()

    # Get all email aliases
    email_result = supabase.table("email_aliases").select("*").eq(
        "tenant_id", tenant_id
    ).eq("canonical_identity_id", str(canonical_id)).execute()

    return {
        "id": canonical["id"],
        "canonical_name": canonical["canonical_name"],
        "canonical_email": canonical["canonical_email"],
        "is_team_member": canonical.get("is_team_member", False),
        "platform_identities": platform_result.data,
        "email_aliases": [ea["email_address"] for ea in email_result.data]
    }


# ============================================================================
# PRIVATE HELPER FUNCTIONS
# ============================================================================

async def _get_existing_platform_identity(
    supabase: Client,
    tenant_id: str,
    platform: str,
    platform_user_id: str
) -> Optional[Dict[str, Any]]:
    """Check if platform identity already exists."""
    result = supabase.table("platform_identities").select(
        "canonical_identity_id, canonical_identities(canonical_name, canonical_email)"
    ).eq("tenant_id", tenant_id).eq("platform", platform).eq(
        "platform_user_id", platform_user_id
    ).limit(1).execute()

    if result.data and len(result.data) > 0:
        row = result.data[0]
        canonical = row.get("canonical_identities", {})
        return {
            "canonical_identity_id": row["canonical_identity_id"],
            "canonical_name": canonical.get("canonical_name"),
            "canonical_email": canonical.get("canonical_email")
        }
    return None


async def _get_canonical_by_email(
    supabase: Client,
    tenant_id: str,
    email: str
) -> Optional[Dict[str, Any]]:
    """Look up canonical identity by email address."""
    result = supabase.table("email_aliases").select(
        "canonical_identity_id, canonical_identities(id, canonical_name, canonical_email)"
    ).eq("tenant_id", tenant_id).eq("email_address", email.lower()).limit(1).execute()

    if result.data and len(result.data) > 0:
        row = result.data[0]
        canonical = row.get("canonical_identities", {})
        return {
            "id": canonical.get("id"),
            "canonical_name": canonical.get("canonical_name"),
            "canonical_email": canonical.get("canonical_email")
        }
    return None


async def _fuzzy_match_by_email_and_name(
    supabase: Client,
    tenant_id: str,
    email: str,
    name: str
) -> Optional[Dict[str, Any]]:
    """
    Fuzzy match by email domain + name similarity.

    Returns best match above CONFIDENCE_REVIEW_QUEUE threshold.
    """
    # Get all canonical identities with emails from same domain
    domain = email.split('@')[1].lower() if '@' in email else None
    if not domain:
        return None

    # Get all email aliases from same domain
    email_result = supabase.table("email_aliases").select(
        "email_address, canonical_identity_id, canonical_identities(canonical_name, canonical_email)"
    ).eq("tenant_id", tenant_id).ilike("email_address", f"%@{domain}").execute()

    best_match = None
    best_score = 0.0

    for row in email_result.data:
        canonical = row.get("canonical_identities", {})
        canonical_name = canonical.get("canonical_name", "")
        canonical_email = canonical.get("canonical_email", "")

        # Calculate combined match score
        score = calculate_combined_match_score(
            name1=name,
            name2=canonical_name,
            email1=email,
            email2=row["email_address"]
        )

        if score > best_score and score >= CONFIDENCE_REVIEW_QUEUE:
            best_score = score
            best_match = {
                "canonical_id": row["canonical_identity_id"],
                "canonical_name": canonical_name,
                "canonical_email": canonical_email,
                "confidence": score,
                "reason": f"Same domain ({domain}) + name similarity {score:.2f}",
                "evidence": {
                    "name_similarity": calculate_name_similarity(name, canonical_name),
                    "email_domain": domain,
                    "matched_email": row["email_address"]
                }
            }

    return best_match


async def _fuzzy_match_by_name(
    supabase: Client,
    tenant_id: str,
    name: str
) -> Optional[Dict[str, Any]]:
    """Fuzzy match by name only (no email available)."""
    # Get all canonical identities for this tenant
    result = supabase.table("canonical_identities").select("*").eq(
        "tenant_id", tenant_id
    ).execute()

    best_match = None
    best_score = 0.0

    for canonical in result.data:
        canonical_name = canonical["canonical_name"]
        score = calculate_name_similarity(name, canonical_name)

        if score > best_score and score >= CONFIDENCE_REVIEW_QUEUE:
            best_score = score
            best_match = {
                "canonical_id": canonical["id"],
                "canonical_name": canonical_name,
                "canonical_email": canonical.get("canonical_email"),
                "confidence": score,
                "reason": f"Name similarity {score:.2f}",
                "evidence": {
                    "name_similarity": score
                }
            }

    return best_match


async def _create_canonical_identity(
    supabase: Client,
    tenant_id: str,
    canonical_name: str,
    canonical_email: Optional[str]
) -> Dict[str, Any]:
    """Create a new canonical identity record."""
    result = supabase.table("canonical_identities").insert({
        "tenant_id": tenant_id,
        "canonical_name": canonical_name,
        "canonical_email": canonical_email
    }).execute()

    return result.data[0]


async def _link_platform_identity(
    supabase: Client,
    tenant_id: str,
    canonical_id: str,
    platform: str,
    platform_user_id: str,
    platform_email: Optional[str],
    display_name: Optional[str],
    confidence: float,
    raw_platform_data: Optional[Dict[str, Any]] = None
) -> None:
    """Link a platform identity to a canonical identity."""
    supabase.table("platform_identities").upsert({
        "tenant_id": tenant_id,
        "canonical_identity_id": canonical_id,
        "platform": platform,
        "platform_user_id": platform_user_id,
        "platform_email": platform_email,
        "display_name": display_name,
        "confidence": confidence,
        "raw_platform_data": raw_platform_data,
        "last_seen_at": datetime.utcnow().isoformat()
    }, on_conflict="tenant_id,platform,platform_user_id").execute()


async def _add_email_alias(
    supabase: Client,
    tenant_id: str,
    canonical_id: str,
    email: str,
    source_platform: str,
    is_primary: bool = False
) -> None:
    """Add an email alias to a canonical identity."""
    # Check if email already exists
    existing = supabase.table("email_aliases").select("*").eq(
        "tenant_id", tenant_id
    ).eq("email_address", email.lower()).limit(1).execute()

    if existing.data:
        # Update usage count and last_seen_at
        supabase.table("email_aliases").update({
            "last_seen_at": datetime.utcnow().isoformat(),
            "usage_count": existing.data[0]["usage_count"] + 1
        }).eq("id", existing.data[0]["id"]).execute()
    else:
        # Insert new alias
        supabase.table("email_aliases").insert({
            "tenant_id": tenant_id,
            "canonical_identity_id": canonical_id,
            "email_address": email.lower(),
            "is_primary": is_primary,
            "source_platform": source_platform
        }).execute()


async def _create_merge_suggestion(
    supabase: Client,
    tenant_id: str,
    identity_a_id: str,
    identity_b_email: Optional[str],
    identity_b_name: str,
    similarity_score: float,
    matching_reason: str,
    evidence: Dict[str, Any]
) -> None:
    """Create a merge suggestion for admin review."""
    # For now, just log it (could create a temporary identity for identity_b)
    logger.info(
        f"Merge suggestion: {identity_b_name} ({identity_b_email}) → "
        f"{identity_a_id} (score: {similarity_score:.2f}, reason: {matching_reason})"
    )

    # TODO: Implement merge suggestions table insertion
    # This would require creating a temporary canonical identity for identity_b
    # or storing the suggestion with just the raw email/name data
