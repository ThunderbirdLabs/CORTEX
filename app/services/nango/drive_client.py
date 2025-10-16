"""
Nango Google Drive Client
Uses Nango actions to download files
"""
import logging
import httpx
import base64
from typing import Dict, Any

from app.core.config import settings

logger = logging.getLogger(__name__)


async def nango_fetch_file(
    http_client: httpx.AsyncClient,
    provider_key: str,
    connection_id: str,
    file_id: str
) -> bytes:
    """
    Download a file from Google Drive using Nango's fetch-document action.

    Args:
        http_client: HTTP client
        provider_key: Nango provider key
        connection_id: Nango connection ID
        file_id: Google Drive file ID

    Returns:
        File bytes
    """
    url = "https://api.nango.dev/fetch-document"

    response = await http_client.get(
        url,
        params={"id": file_id},
        headers={
            "Authorization": f"Bearer {settings.nango_secret}",
            "Connection-Id": connection_id,
            "Provider-Config-Key": provider_key
        }
    )

    response.raise_for_status()

    # Response is base64-encoded file content
    base64_content = response.text.strip('"')  # Remove quotes from JSON string
    file_bytes = base64.b64decode(base64_content)

    return file_bytes
