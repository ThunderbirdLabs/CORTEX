"""
Nango API client
Handles token retrieval and Gmail unified API calls
"""
import json
import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import HTTPException

from config.settings import NANGO_SECRET

logger = logging.getLogger(__name__)


# ============================================================================
# NANGO TOKEN RETRIEVAL
# ============================================================================

async def get_graph_token_via_nango(
    http_client: httpx.AsyncClient,
    provider_key: str,
    connection_id: str
) -> str:
    """
    Get Microsoft Graph access token via Nango.

    Args:
        http_client: Async HTTP client instance
        provider_key: Nango provider configuration key
        connection_id: Nango connection ID

    Returns:
        Access token string

    Raises:
        HTTPException: If token retrieval fails
    """
    url = f"https://api.nango.dev/connection/{provider_key}/{connection_id}"
    headers = {"Authorization": f"Bearer {NANGO_SECRET}"}

    try:
        response = await http_client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["credentials"]["access_token"]
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to get Nango token: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail="Failed to retrieve access token from Nango")
    except Exception as e:
        logger.error(f"Error getting Nango token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GMAIL UNIFIED API
# ============================================================================

async def nango_list_gmail_records(
    http_client: httpx.AsyncClient,
    provider_key: str,
    connection_id: str,
    cursor: Optional[str] = None,
    limit: int = 100,
    modified_after: Optional[str] = None
) -> Dict[str, Any]:
    """
    List Gmail records from Nango unified API.

    Args:
        http_client: Async HTTP client instance
        provider_key: Nango provider configuration key
        connection_id: Nango connection ID
        cursor: Optional cursor for pagination
        limit: Number of records per page
        modified_after: Optional ISO datetime to filter records

    Returns:
        Dictionary with 'records' list and optional 'next_cursor'

    Raises:
        HTTPException: If request fails
    """
    url = "https://api.nango.dev/v1/emails"
    params = {
        "limit": limit
    }

    if cursor:
        params["cursor"] = cursor
    if modified_after:
        params["modified_after"] = modified_after

    headers = {
        "Authorization": f"Bearer {NANGO_SECRET}",
        "Connection-Id": connection_id,
        "Provider-Config-Key": provider_key
    }

    try:
        response = await http_client.get(url, headers=headers, params=params)
        response.raise_for_status()

        # Log FULL raw response for debugging
        response_text = response.text
        logger.info(f"=" * 80)
        logger.info(f"NANGO RAW RESPONSE - FULL PAYLOAD")
        logger.info(f"=" * 80)
        logger.info(f"URL: {url}")
        logger.info(f"Params: {params}")
        logger.info(f"Response Length: {len(response_text)} bytes")
        logger.info(f"Full Response:\n{response_text}")
        logger.info(f"=" * 80)

        # Handle empty response
        if not response_text or response_text.strip() == "":
            logger.warning("Nango returned empty response - sync may not have run yet")
            return {"records": [], "next_cursor": None}

        try:
            data = response.json()

            # Log individual email record structure (first 3 records for inspection)
            records = data.get("records", [])
            if records:
                logger.info(f"FIRST 3 EMAIL RECORDS FROM NANGO:")
                for i, record in enumerate(records[:3], 1):
                    logger.info(f"--- Email Record #{i} ---")
                    logger.info(json.dumps(record, indent=2))
                    logger.info(f"--- End Record #{i} ---")

            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Nango response as JSON: {e}")
            logger.error(f"Response text: {response_text}")
            return {"records": [], "next_cursor": None}

    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to fetch Gmail records from Nango: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail="Failed to fetch Gmail records from Nango")
    except Exception as e:
        logger.error(f"Error fetching Gmail records: {e}")
        raise HTTPException(status_code=500, detail=str(e))
