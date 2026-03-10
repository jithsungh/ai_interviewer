"""
Azure Blob Storage Health Check
"""

import logging
from azure.core.exceptions import AzureError
from .client import get_blob_client, BlobStorageError

logger = logging.getLogger(__name__)


def check_blob_health() -> bool:
    """
    Check Azure Blob Storage connectivity by listing containers.
    
    Returns:
        True if healthy, False otherwise
    """
    try:
        client = get_blob_client()
        # A lightweight call to verify connectivity
        list(client.list_containers(results_per_page=1))
        return True
    except (BlobStorageError, AzureError) as e:
        logger.warning(f"Blob Storage health check failed: {e}")
        return False
