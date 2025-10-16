"""
Google Drive Sync Engine
Syncs entire Drive or specific folders using Nango
"""
import logging
from typing import Dict, Any, List, Optional
import httpx
from supabase import Client

from app.core.config import settings
from app.services.ingestion.llamaindex.hybrid_property_graph_pipeline import HybridPropertyGraphPipeline
from app.services.nango.database import get_connection
from app.services.connectors.google_drive import (
    normalize_drive_file,
    is_supported_file_type,
    get_export_mime_type
)
from app.services.nango.drive_client import nango_fetch_file
from app.services.universal.ingest import ingest_document_universal

logger = logging.getLogger(__name__)


async def nango_list_drive_files(
    http_client: httpx.AsyncClient,
    provider_key: str,
    connection_id: str,
    folder_ids: Optional[List[str]] = None,
    cursor: Optional[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    List Drive files using Nango /documents sync endpoint.

    Args:
        http_client: HTTP client
        provider_key: Nango provider key
        connection_id: Connection ID
        folder_ids: Optional list of folder IDs to filter by
        cursor: Pagination cursor
        limit: Results per page

    Returns:
        Dict with records and next_cursor
    """
    url = "https://api.nango.dev/sync/records"

    params = {
        "provider_config_key": provider_key,
        "connection_id": connection_id,
        "model": "Document",  # Nango model name for Drive files
        "limit": limit
    }

    if cursor:
        params["cursor"] = cursor

    # Add metadata filter for specific folders
    if folder_ids:
        params["metadata"] = {"folders": folder_ids}

    response = await http_client.get(
        url,
        params=params,
        headers={"Authorization": f"Bearer {settings.nango_secret}"}
    )

    response.raise_for_status()
    
    # Handle empty response (sync not run yet)
    if not response.text or response.text.strip() == "":
        logger.warning("Nango returned empty response - Documents sync may not have run yet")
        return {"records": [], "next_cursor": None}
    
    try:
        return response.json()
    except Exception as e:
        logger.error(f"Failed to parse Nango response: {e}")
        logger.error(f"Response text: {response.text}")
        return {"records": [], "next_cursor": None}


async def get_drive_access_token(
    http_client: httpx.AsyncClient,
    provider_key: str,
    connection_id: str
) -> str:
    """
    Get Drive access token from Nango.

    Args:
        http_client: HTTP client
        provider_key: Nango provider key
        connection_id: Connection ID

    Returns:
        Access token
    """
    url = f"https://api.nango.dev/connection/{connection_id}"

    response = await http_client.get(
        url,
        params={"provider_config_key": provider_key},
        headers={"Authorization": f"Bearer {settings.nango_secret}"}
    )

    response.raise_for_status()
    data = response.json()

    return data["credentials"]["access_token"]


async def run_drive_sync(
    http_client: httpx.AsyncClient,
    supabase: Client,
    cortex_pipeline: Optional[HybridPropertyGraphPipeline],
    tenant_id: str,
    provider_key: str,
    folder_ids: Optional[List[str]] = None,
    download_files: bool = True
) -> Dict[str, Any]:
    """
    Sync Google Drive files for a tenant.

    Flow:
    1. Fetch file metadata from Nango (/documents endpoint)
    2. For each supported file:
       a. Download file content
       b. Ingest via universal ingestion (Unstructured.io parses it)
    3. Pagination until all files synced

    Args:
        http_client: HTTP client
        supabase: Supabase client
        cortex_pipeline: PropertyGraph pipeline
        tenant_id: Tenant/user ID
        provider_key: Nango provider key
        folder_ids: Optional folder IDs to sync (None = entire Drive)
        download_files: Whether to download and parse files (vs just metadata)

    Returns:
        Sync statistics
    """
    logger.info(f"🚀 Starting Drive sync for tenant {tenant_id}")

    if folder_ids:
        logger.info(f"   Syncing specific folders: {folder_ids}")
    else:
        logger.info(f"   Syncing entire Drive")

    files_synced = 0
    files_skipped = 0
    errors = []

    try:
        # Get connection
        connection_id = await get_connection(tenant_id, provider_key)
        if not connection_id:
            error_msg = f"No Drive connection found for tenant {tenant_id}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error": error_msg,
                "files_synced": 0
            }

        # Nango handles OAuth tokens internally - no need to get access_token

        # Paginate through all files
        cursor = None
        has_more = True

        while has_more:
            try:
                # Fetch page of files
                result = await nango_list_drive_files(
                    http_client,
                    provider_key,
                    connection_id,
                    folder_ids=folder_ids,
                    cursor=cursor,
                    limit=100
                )

                files = result.get("records", [])
                next_cursor = result.get("next_cursor")

                logger.info(f"📄 Fetched {len(files)} files (cursor: {cursor[:20] if cursor else 'none'}...)")

                # Process each file
                for raw_file in files:
                    try:
                        # Normalize metadata
                        normalized = normalize_drive_file(raw_file, tenant_id)

                        # Skip trashed files
                        if normalized["is_trashed"]:
                            logger.debug(f"   ⏭️  Skipping trashed file: {normalized['file_name']}")
                            files_skipped += 1
                            continue

                        # Check if file type is supported
                        if not is_supported_file_type(normalized["mime_type"]):
                            logger.debug(f"   ⏭️  Skipping unsupported type: {normalized['file_name']} ({normalized['mime_type']})")
                            files_skipped += 1
                            continue

                        # Download and ingest file
                        if download_files:
                            file_bytes = None
                            document_type = "file"  # Default
                            original_mime = normalized["mime_type"]

                            # Download file using Nango fetch-document action
                            logger.info(f"   📥 Downloading: {normalized['file_name']}")

                            file_bytes = await nango_fetch_file(
                                http_client,
                                provider_key,
                                connection_id,
                                normalized["file_id"]
                            )

                            # Set specific document type for Google Workspace files
                            if normalized["mime_type"].startswith("application/vnd.google-apps"):
                                if original_mime == "application/vnd.google-apps.document":
                                    document_type = "googledoc"
                                    normalized["mime_type"] = "application/pdf"  # Nango exports to PDF
                                elif original_mime == "application/vnd.google-apps.spreadsheet":
                                    document_type = "googlesheet"
                                    normalized["mime_type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"  # Excel
                                elif original_mime == "application/vnd.google-apps.presentation":
                                    document_type = "googleslide"
                                    normalized["mime_type"] = "application/pdf"  # Exported to PDF
                                else:
                                    document_type = "file"

                            # Universal ingestion (Unstructured.io parses the file!)
                            result = await ingest_document_universal(
                                supabase=supabase,
                                cortex_pipeline=cortex_pipeline,
                                tenant_id=tenant_id,
                                source="googledrive",
                                source_id=normalized["file_id"],
                                document_type=document_type,  # googledoc, googlesheet, googleslide, or file
                                title=normalized["file_name"],
                                file_bytes=file_bytes,
                                filename=normalized["file_name"],
                                file_type=normalized["mime_type"],
                                raw_data=raw_file,  # Preserve full metadata
                                source_created_at=normalized["created_at"],
                                source_modified_at=normalized["modified_at"],
                                metadata={
                                    "owner_email": normalized["owner_email"],
                                    "owner_name": normalized["owner_name"],
                                    "web_view_link": normalized["web_view_link"],
                                    "parent_folders": normalized["parent_folders"],
                                    "original_mime_type": original_mime  # Preserve original type
                                }
                            )

                            if result["status"] == "success":
                                logger.info(f"   ✅ Ingested: {normalized['file_name']}")
                                files_synced += 1
                            else:
                                logger.error(f"   ❌ Ingestion failed: {result.get('error')}")
                                errors.append(f"{normalized['file_name']}: {result.get('error')}")
                        else:
                            # Metadata-only mode (no download)
                            files_synced += 1

                    except Exception as e:
                        error_msg = f"Error processing file: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                # Check pagination
                if next_cursor:
                    cursor = next_cursor
                else:
                    has_more = False

            except Exception as e:
                error_msg = f"Error fetching Drive page: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                has_more = False

        logger.info(f"✅ Drive sync complete: {files_synced} files synced, {files_skipped} skipped")

        return {
            "status": "success" if not errors else "partial_success",
            "tenant_id": tenant_id,
            "files_synced": files_synced,
            "files_skipped": files_skipped,
            "errors": errors
        }

    except Exception as e:
        error_msg = f"Fatal error during Drive sync: {e}"
        logger.error(error_msg)
        return {
            "status": "error",
            "error": error_msg,
            "files_synced": files_synced
        }
