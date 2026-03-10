"""
Azure Blob Storage Operations

Upload, download, delete, list, and SAS URL generation for blobs.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, BinaryIO

from azure.storage.blob import (
    BlobSasPermissions,
    generate_blob_sas,
    ContentSettings,
)
from azure.core.exceptions import ResourceNotFoundError, AzureError

from .client import get_blob_client, BlobStorageError

logger = logging.getLogger(__name__)


def _generate_blob_name(original_filename: str, prefix: Optional[str] = None) -> str:
    """Generate a unique blob name preserving the original file extension."""
    ext = ""
    if "." in original_filename:
        ext = "." + original_filename.rsplit(".", 1)[-1].lower()
    unique_id = uuid.uuid4().hex
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    parts = [prefix, timestamp, f"{unique_id}{ext}"]
    return "/".join(p for p in parts if p)


def upload_blob(
    container_name: str,
    data: BinaryIO,
    original_filename: str,
    content_type: Optional[str] = None,
    prefix: Optional[str] = None,
    blob_name: Optional[str] = None,
    max_size_mb: int = 50,
) -> dict:
    """
    Upload a file to Azure Blob Storage.
    
    Args:
        container_name: Target container
        data: File-like object to upload
        original_filename: Original filename (used for extension)
        content_type: MIME type of the file
        prefix: Optional path prefix (e.g., "candidate_123")
        blob_name: Override auto-generated name
        max_size_mb: Maximum allowed file size in MB
        
    Returns:
        dict with keys: blob_name, container, url, size_bytes, content_type
        
    Raises:
        BlobStorageError: On upload failure or size violation
    """
    client = get_blob_client()
    
    if blob_name is None:
        blob_name = _generate_blob_name(original_filename, prefix=prefix)
    
    try:
        # Read data and enforce size limit
        file_bytes = data.read()
        size_bytes = len(file_bytes)
        max_bytes = max_size_mb * 1024 * 1024
        
        if size_bytes > max_bytes:
            raise BlobStorageError(
                f"File size {size_bytes} bytes exceeds limit of {max_size_mb} MB",
                status_code=413,
            )
        
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        
        content_settings = ContentSettings(content_type=content_type) if content_type else None
        
        blob_client.upload_blob(
            file_bytes,
            overwrite=True,
            content_settings=content_settings,
        )
        
        logger.info(
            f"Uploaded blob: {container_name}/{blob_name} ({size_bytes} bytes)"
        )
        
        return {
            "blob_name": blob_name,
            "container": container_name,
            "url": blob_client.url,
            "size_bytes": size_bytes,
            "content_type": content_type,
        }
        
    except BlobStorageError:
        raise
    except AzureError as e:
        raise BlobStorageError(f"Upload failed: {e}")


def download_blob(container_name: str, blob_name: str) -> bytes:
    """
    Download a blob's content.
    
    Returns:
        Raw bytes of the blob
        
    Raises:
        BlobStorageError: If blob not found or download fails
    """
    client = get_blob_client()
    
    try:
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        return blob_client.download_blob().readall()
    except ResourceNotFoundError:
        raise BlobStorageError(
            f"Blob not found: {container_name}/{blob_name}",
            status_code=404,
        )
    except AzureError as e:
        raise BlobStorageError(f"Download failed: {e}")


def delete_blob(container_name: str, blob_name: str) -> None:
    """
    Delete a blob from a container.
    
    Raises:
        BlobStorageError: If delete fails
    """
    client = get_blob_client()
    
    try:
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        blob_client.delete_blob()
        logger.info(f"Deleted blob: {container_name}/{blob_name}")
    except ResourceNotFoundError:
        logger.debug(f"Blob already deleted: {container_name}/{blob_name}")
    except AzureError as e:
        raise BlobStorageError(f"Delete failed: {e}")


def generate_sas_url(
    container_name: str,
    blob_name: str,
    expiry_hours: int = 1,
    permission: str = "r",
) -> str:
    """
    Generate a time-limited SAS URL for direct blob access.
    
    Args:
        container_name: Container name
        blob_name: Blob name
        expiry_hours: Hours until the SAS token expires
        permission: SAS permissions (r=read, w=write, d=delete)
        
    Returns:
        Full URL with SAS token
        
    Raises:
        BlobStorageError: If SAS generation fails
    """
    from app.config import settings
    
    storage_config = settings.azure_storage
    if storage_config is None:
        raise BlobStorageError("Azure Storage not configured")
    
    try:
        sas_token = generate_blob_sas(
            account_name=storage_config.azure_storage_account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=storage_config.azure_storage_account_key,
            permission=BlobSasPermissions(read="r" in permission, write="w" in permission, delete="d" in permission),
            expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
        )
        
        return f"{storage_config.account_url}/{container_name}/{blob_name}?{sas_token}"
        
    except AzureError as e:
        raise BlobStorageError(f"SAS URL generation failed: {e}")


def list_blobs(container_name: str, prefix: Optional[str] = None) -> list[dict]:
    """
    List blobs in a container with optional prefix filter.
    
    Returns:
        List of dicts with keys: name, size, content_type, last_modified
    """
    client = get_blob_client()
    
    try:
        container_client = client.get_container_client(container_name)
        blobs = container_client.list_blobs(name_starts_with=prefix)
        
        return [
            {
                "name": blob.name,
                "size": blob.size,
                "content_type": blob.content_settings.content_type if blob.content_settings else None,
                "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
            }
            for blob in blobs
        ]
        
    except AzureError as e:
        raise BlobStorageError(f"List blobs failed: {e}")


def blob_exists(container_name: str, blob_name: str) -> bool:
    """Check if a blob exists in the given container."""
    client = get_blob_client()
    
    try:
        blob_client = client.get_blob_client(container=container_name, blob=blob_name)
        blob_client.get_blob_properties()
        return True
    except ResourceNotFoundError:
        return False
    except AzureError as e:
        raise BlobStorageError(f"Blob existence check failed: {e}")
