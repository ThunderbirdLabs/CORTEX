"""
Identity Resolution Service
Maps multiple platform-specific user IDs to canonical person identities
"""
from app.services.identity.resolver import (
    resolve_identity,
    resolve_identity_by_name,
    get_canonical_identity
)

from app.services.identity.matcher import (
    calculate_name_similarity,
    extract_name_from_email,
    normalize_email,
    same_email_domain,
    calculate_combined_match_score,
    extract_name_variants
)

__all__ = [
    "resolve_identity",
    "resolve_identity_by_name",
    "get_canonical_identity",
    "calculate_name_similarity",
    "extract_name_from_email",
    "normalize_email",
    "same_email_domain",
    "calculate_combined_match_score",
    "extract_name_variants"
]
