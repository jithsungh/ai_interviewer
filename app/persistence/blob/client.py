"""
Azure Blob Storage Client Initialization

Handles BlobServiceClient creation, container provisioning,
and graceful error handling.
"""

import logging
from typing import Optional

from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError

from app.config.settings import AzureStorageSettings
from app.shared.errors import ApplicationError

logger = logging.getLogger(__name__)

# Global client instance (initialized once)
_client: Optional[BlobServiceClient] = None


class BlobStorageError(ApplicationError):
    """Azure Blob Storage initialization or operation failed"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=503, error_code="BLOB_STORAGE_UNAVAILABLE", **kwargs)


def _ensure_containers(client: BlobServiceClient, config: AzureStorageSettings) -> None:
    """Create containers if they don't exist."""
    container_names = [
        config.azure_container_resumes,
        config.azure_container_recordings,
        config.azure_container_images,
        config.azure_container_logos,
        config.azure_container_job_descriptions,
    ]
    for name in container_names:
        try:
            container_client = client.get_container_client(name)
            if not container_client.exists():
                client.create_container(name)
                logger.info(f"Created blob container: {name}")
            else:
                logger.debug(f"Blob container already exists: {name}")
        except AzureError as e:
            logger.warning(f"Could not ensure container '{name}': {e}")


def init_blob_client(config: AzureStorageSettings) -> BlobServiceClient:
    """
    Initialize BlobServiceClient and ensure containers exist.
    
    Args:
        config: AzureStorageSettings instance
        
    Returns:
        BlobServiceClient instance
        
    Raises:
        BlobStorageError: If connection fails
    """
    global _client
    
    logger.info("Initializing Azure Blob Storage client...")
    
    try:
        if config.azure_storage_connection_string:
            _client = BlobServiceClient.from_connection_string(
                config.azure_storage_connection_string
            )
        else:
            _client = BlobServiceClient(
                account_url=config.account_url,
                credential=config.azure_storage_account_key,
            )
        
        # Ensure all required containers exist
        _ensure_containers(_client, config)
        
        logger.info("Azure Blob Storage client initialized successfully")
        return _client
        
    except AzureError as e:
        raise BlobStorageError(f"Failed to initialize Azure Blob Storage: {e}")


def get_blob_client() -> BlobServiceClient:
    """
    Get the initialized BlobServiceClient.
    
    Returns:
        BlobServiceClient instance
        
    Raises:
        BlobStorageError: If client not initialized
    """
    if _client is None:
        raise BlobStorageError("Azure Blob Storage client not initialized. Call init_blob_client() first.")
    return _client


def cleanup_blob() -> None:
    """Gracefully close the BlobServiceClient."""
    global _client
    if _client is not None:
        try:
            _client.close()
            logger.info("Azure Blob Storage client closed")
        except Exception as e:
            logger.warning(f"Error closing Blob Storage client: {e}")
        finally:
            _client = None
