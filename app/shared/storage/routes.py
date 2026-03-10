"""
Storage API Routes

REST endpoints for file upload, download, and management via Azure Blob Storage.

  POST   /upload/{category}         — upload a file (resume, profile-photo, org-logo, job-description)
  GET    /download/{category}/{blob_name:path}  — download / get SAS URL for a file
  DELETE /delete/{category}/{blob_name:path}     — delete a file
  GET    /list/{category}           — list files in a category

URL prefix: /api/v1/storage (set in router_registry.py)
Auth: requires authenticated user (candidate or admin)

Categories map to Azure containers:
  resume          → candidate-resumes
  recording       → interview-recordings
  profile-photo   → candidate-images
  org-logo        → organization-logos
  job-description → job-descriptions
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from pydantic import BaseModel

from app.bootstrap.dependencies import get_identity
from app.shared.auth_context import IdentityContext
from app.config import settings
from app.persistence.blob.operations import (
    upload_blob,
    download_blob,
    delete_blob,
    generate_sas_url,
    list_blobs,
)
from app.persistence.blob.client import BlobStorageError

logger = logging.getLogger(__name__)

router = APIRouter()


# ────────────────────────────────────────────────────────────
# Response schemas
# ────────────────────────────────────────────────────────────


class FileUploadResponse(BaseModel):
    blob_name: str
    container: str
    url: str
    size_bytes: int
    content_type: Optional[str] = None


class FileListItem(BaseModel):
    name: str
    size: Optional[int] = None
    content_type: Optional[str] = None
    last_modified: Optional[str] = None


class FileListResponse(BaseModel):
    files: list[FileListItem]
    count: int


class SasUrlResponse(BaseModel):
    url: str
    expires_in_hours: int


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

# Allowed MIME types per category
_ALLOWED_TYPES: dict[str, set[str]] = {
    "resume": {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    },
    "recording": {
        "audio/mpeg",
        "audio/wav",
        "audio/webm",
        "audio/ogg",
        "video/webm",
        "video/mp4",
    },
    "profile-photo": {
        "image/jpeg",
        "image/png",
        "image/webp",
    },
    "org-logo": {
        "image/jpeg",
        "image/png",
        "image/svg+xml",
        "image/webp",
    },
    "job-description": {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    },
}

_CATEGORY_TO_CONTAINER: dict[str, str] = {}


def _get_category_container_map() -> dict[str, str]:
    """Lazily build category→container mapping from settings."""
    global _CATEGORY_TO_CONTAINER
    if _CATEGORY_TO_CONTAINER:
        return _CATEGORY_TO_CONTAINER
    
    cfg = settings.azure_storage
    if cfg is None:
        raise HTTPException(status_code=503, detail="Azure Blob Storage not configured")
    
    _CATEGORY_TO_CONTAINER = {
        "resume": cfg.azure_container_resumes,
        "recording": cfg.azure_container_recordings,
        "profile-photo": cfg.azure_container_images,
        "org-logo": cfg.azure_container_logos,
        "job-description": cfg.azure_container_job_descriptions,
    }
    return _CATEGORY_TO_CONTAINER


def _resolve_container(category: str) -> str:
    mapping = _get_category_container_map()
    container = mapping.get(category)
    if container is None:
        valid = ", ".join(mapping.keys())
        raise HTTPException(status_code=400, detail=f"Invalid category '{category}'. Valid: {valid}")
    return container


# ────────────────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────────────────


@router.post(
    "/upload/{category}",
    response_model=FileUploadResponse,
    summary="Upload a file",
)
async def upload_file(
    category: str,
    file: UploadFile = File(...),
    identity: IdentityContext = Depends(get_identity),
):
    """Upload a file to the specified category container."""
    container = _resolve_container(category)
    
    # Validate MIME type
    allowed = _ALLOWED_TYPES.get(category)
    if allowed and file.content_type not in allowed:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{file.content_type}' for category '{category}'",
        )
    
    # Build a prefix from user identity for namespacing
    prefix = f"user_{identity.user_id}"
    
    cfg = settings.azure_storage
    max_size = cfg.azure_max_upload_size_mb if cfg else 50
    
    try:
        result = upload_blob(
            container_name=container,
            data=file.file,
            original_filename=file.filename or "upload",
            content_type=file.content_type,
            prefix=prefix,
            max_size_mb=max_size,
        )
        return FileUploadResponse(**result)
    except BlobStorageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/download/{category}/{blob_name:path}",
    response_model=SasUrlResponse,
    summary="Get a download URL for a file",
)
async def get_download_url(
    category: str,
    blob_name: str,
    identity: IdentityContext = Depends(get_identity),
):
    """Generate a time-limited SAS URL for downloading a file."""
    container = _resolve_container(category)
    
    cfg = settings.azure_storage
    expiry_hours = cfg.azure_sas_token_expiry_hours if cfg else 1
    
    try:
        url = generate_sas_url(
            container_name=container,
            blob_name=blob_name,
            expiry_hours=expiry_hours,
        )
        return SasUrlResponse(url=url, expires_in_hours=expiry_hours)
    except BlobStorageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete(
    "/delete/{category}/{blob_name:path}",
    status_code=204,
    summary="Delete a file",
)
async def delete_file(
    category: str,
    blob_name: str,
    identity: IdentityContext = Depends(get_identity),
):
    """Delete a file from the specified category container."""
    container = _resolve_container(category)
    
    try:
        delete_blob(container_name=container, blob_name=blob_name)
    except BlobStorageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get(
    "/list/{category}",
    response_model=FileListResponse,
    summary="List files in a category",
)
async def list_files(
    category: str,
    prefix: Optional[str] = Query(None, description="Filter by blob name prefix"),
    identity: IdentityContext = Depends(get_identity),
):
    """List files in the specified category container."""
    container = _resolve_container(category)
    
    try:
        blobs = list_blobs(container_name=container, prefix=prefix)
        return FileListResponse(
            files=[FileListItem(**b) for b in blobs],
            count=len(blobs),
        )
    except BlobStorageError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
