"""
Azure Blob Storage Persistence Layer

Pure infrastructure module for Azure Blob Storage connectivity.
Provides client initialization, upload/download operations, and SAS URL generation.

Public API:
- init_blob_client(): Initialize Azure Blob Storage client
- get_blob_client(): Get initialized client (dependency injection)
- cleanup_blob(): Graceful shutdown cleanup
- check_blob_health(): Health check for monitoring

Operations:
- upload_blob(): Upload a file to a container
- download_blob(): Download a file from a container
- delete_blob(): Delete a file from a container
- generate_sas_url(): Generate a time-limited SAS URL for a blob
- list_blobs(): List blobs in a container
- blob_exists(): Check if a blob exists
"""

from .client import (
    init_blob_client,
    get_blob_client,
    cleanup_blob,
    BlobStorageError,
)

from .operations import (
    upload_blob,
    download_blob,
    delete_blob,
    generate_sas_url,
    list_blobs,
    blob_exists,
)

from .health import check_blob_health

__all__ = [
    # Client lifecycle
    "init_blob_client",
    "get_blob_client",
    "cleanup_blob",
    "BlobStorageError",
    
    # Operations
    "upload_blob",
    "download_blob",
    "delete_blob",
    "generate_sas_url",
    "list_blobs",
    "blob_exists",
    
    # Health
    "check_blob_health",
]
