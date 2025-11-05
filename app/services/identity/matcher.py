"""
Identity Matching Utilities
Similarity algorithms for fuzzy name/email matching
"""
import re
from typing import Optional
from difflib import SequenceMatcher


def normalize_email(email: str) -> str:
    """
    Normalize email address for comparison.

    Args:
        email: Raw email address

    Returns:
        Lowercase, trimmed email
    """
    if not email:
        return ""
    return email.strip().lower()


def extract_name_from_email(email: str) -> str:
    """
    Extract display name from email address.

    Examples:
        john.doe@company.com → John Doe
        sarah.chen123@gmail.com → Sarah Chen
        h.woodburn@company.com → H Woodburn

    Args:
        email: Email address

    Returns:
        Extracted name (title case)
    """
    if not email or '@' not in email:
        return ""

    # Get local part (before @)
    local_part = email.split('@')[0]

    # Remove common suffixes (numbers, underscores)
    local_part = re.sub(r'[\d_]+$', '', local_part)

    # Split on dots, dashes, underscores
    parts = re.split(r'[.\-_]', local_part)

    # Title case each part
    name_parts = [part.capitalize() for part in parts if part]

    return " ".join(name_parts)


def calculate_name_similarity(name1: str, name2: str) -> float:
    """
    Calculate similarity score between two names using multiple algorithms.

    Combines:
    - SequenceMatcher (overall string similarity)
    - Token-based matching (handles reordering)
    - Initials matching (H. Woodburn vs Hayden Woodburn)

    Args:
        name1: First name
        name2: Second name

    Returns:
        Similarity score 0.0-1.0 (1.0 = identical)
    """
    if not name1 or not name2:
        return 0.0

    # Normalize
    name1_norm = name1.strip().lower()
    name2_norm = name2.strip().lower()

    # Exact match
    if name1_norm == name2_norm:
        return 1.0

    # Calculate base similarity (overall string)
    base_similarity = SequenceMatcher(None, name1_norm, name2_norm).ratio()

    # Token-based matching (handles "John Doe" vs "Doe, John")
    tokens1 = set(name1_norm.split())
    tokens2 = set(name2_norm.split())

    if tokens1 and tokens2:
        token_intersection = tokens1 & tokens2
        token_union = tokens1 | tokens2
        token_similarity = len(token_intersection) / len(token_union)
    else:
        token_similarity = 0.0

    # Initials matching ("H. Woodburn" vs "Hayden Woodburn")
    initials_match = check_initials_match(name1, name2)
    initials_boost = 0.2 if initials_match else 0.0

    # Combine scores (weighted average)
    combined_score = (
        base_similarity * 0.5 +
        token_similarity * 0.4 +
        initials_boost * 0.1
    )

    return min(combined_score, 1.0)


def check_initials_match(name1: str, name2: str) -> bool:
    """
    Check if one name matches initials of another.

    Examples:
        "H. Woodburn" matches "Hayden Woodburn" → True
        "J. Doe" matches "John Smith" → False

    Args:
        name1: First name
        name2: Second name

    Returns:
        True if initials match
    """
    def extract_initials(name: str) -> str:
        """Extract initials from name."""
        parts = name.strip().split()
        return "".join([p[0].upper() for p in parts if p])

    def has_initials(name: str) -> bool:
        """Check if name contains period (likely initials)."""
        return '.' in name

    # Check if either name has initials
    if not (has_initials(name1) or has_initials(name2)):
        return False

    initials1 = extract_initials(name1)
    initials2 = extract_initials(name2)

    # Check if initials match
    return initials1 == initials2


def same_email_domain(email1: str, email2: str) -> bool:
    """
    Check if two emails share the same domain.

    Args:
        email1: First email
        email2: Second email

    Returns:
        True if same domain
    """
    if not email1 or not email2 or '@' not in email1 or '@' not in email2:
        return False

    domain1 = email1.split('@')[1].lower()
    domain2 = email2.split('@')[1].lower()

    return domain1 == domain2


def calculate_levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein (edit) distance between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Edit distance (number of edits needed to transform s1 to s2)
    """
    if len(s1) < len(s2):
        return calculate_levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertion, deletion, substitution
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def extract_company_domain(email: str) -> Optional[str]:
    """
    Extract company domain from email (excluding common providers).

    Examples:
        john@company.com → company.com
        john@gmail.com → None (personal email)
        sarah@acme.co.uk → acme.co.uk

    Args:
        email: Email address

    Returns:
        Company domain or None if personal email provider
    """
    if not email or '@' not in email:
        return None

    domain = email.split('@')[1].lower()

    # Common personal email providers
    personal_providers = {
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'icloud.com', 'me.com', 'aol.com', 'protonmail.com',
        'mail.com', 'zoho.com'
    }

    if domain in personal_providers:
        return None

    return domain


def is_corporate_email(email: str) -> bool:
    """
    Check if email is corporate (not personal provider).

    Args:
        email: Email address

    Returns:
        True if corporate email
    """
    return extract_company_domain(email) is not None


def calculate_combined_match_score(
    name1: str,
    name2: str,
    email1: Optional[str] = None,
    email2: Optional[str] = None
) -> float:
    """
    Calculate combined matching score using name and email.

    Scoring:
    - Name similarity (0.5 weight)
    - Same email domain (0.3 boost if corporate emails)
    - Email local part similarity (0.2 weight)

    Args:
        name1: First person's name
        name2: Second person's name
        email1: First person's email (optional)
        email2: Second person's email (optional)

    Returns:
        Combined match score 0.0-1.0
    """
    # Base name similarity
    name_score = calculate_name_similarity(name1, name2)

    # Email boost
    email_boost = 0.0

    if email1 and email2:
        # Same domain boost (corporate emails only)
        if same_email_domain(email1, email2):
            if is_corporate_email(email1):
                email_boost += 0.3  # Strong signal for same company

        # Email local part similarity
        local1 = email1.split('@')[0] if '@' in email1 else email1
        local2 = email2.split('@')[0] if '@' in email2 else email2
        local_similarity = SequenceMatcher(None, local1.lower(), local2.lower()).ratio()
        email_boost += local_similarity * 0.2

    # Combine scores
    combined_score = name_score * 0.5 + email_boost

    return min(combined_score, 1.0)


def extract_name_variants(name: str) -> list[str]:
    """
    Generate name variants for fuzzy matching.

    Examples:
        "John Doe" → ["John Doe", "J. Doe", "John D.", "J. D."]
        "Sarah Chen" → ["Sarah Chen", "S. Chen", "Sarah C.", "S. C."]

    Args:
        name: Full name

    Returns:
        List of name variants
    """
    if not name:
        return []

    parts = name.strip().split()
    if len(parts) < 2:
        return [name]

    variants = [name]  # Original name

    # First name + last initial ("John D.")
    if len(parts) >= 2:
        variants.append(f"{parts[0]} {parts[-1][0]}.")

    # First initial + last name ("J. Doe")
    variants.append(f"{parts[0][0]}. {parts[-1]}")

    # All initials ("J. D.")
    initials = " ".join([p[0] + "." for p in parts])
    variants.append(initials)

    return list(set(variants))  # Remove duplicates
