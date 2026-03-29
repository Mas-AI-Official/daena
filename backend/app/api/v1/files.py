"""File upload and retrieval endpoints.

Stores uploaded files in a local directory (dev) or cloud storage (production).
Returns a file_id that can be attached to chat messages.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.deps import CurrentUser, get_current_user

router = APIRouter()

# Dev storage directory (production would use GCS / S3)
_UPLOAD_DIR = Path("uploads")
_UPLOAD_DIR.mkdir(exist_ok=True)

# 20 MB limit
_MAX_FILE_SIZE = 20 * 1024 * 1024

# Allowed MIME prefixes (permissive for developer workflows)
_ALLOWED_TYPES = {
    "text/",                          # .txt, .md, .csv, .html, .css, .js, etc.
    "application/pdf",
    "application/json",
    "application/octet-stream",       # generic binary (.md, .txt, .csv sometimes)
    "application/x-yaml",             # .yaml, .yml
    "application/xml",
    "image/",                         # all image types
    "audio/",                         # voice recordings
    "video/",                         # screen recordings
    "application/vnd.openxmlformats", # .docx, .xlsx, .pptx
    "application/zip",
    "application/x-tar",
    "application/gzip",
    "application/x-python-code",      # .py
    "application/javascript",         # .js
    "application/typescript",         # .ts
    "application/x-ipynb+json",       # Jupyter notebooks
}


def _type_allowed(content_type: str | None) -> bool:
    if not content_type:
        return True  # permissive fallback
    return any(content_type.startswith(prefix) for prefix in _ALLOWED_TYPES)


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Upload a file and return its file_id for chat attachment."""
    if not _type_allowed(file.content_type):
        raise HTTPException(400, f"File type not allowed: {file.content_type}")

    data = await file.read()
    if len(data) > _MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large (max {_MAX_FILE_SIZE // (1024*1024)}MB)")

    file_id = str(uuid.uuid4())
    sha256 = hashlib.sha256(data).hexdigest()
    ext = Path(file.filename or "file").suffix or ".bin"
    stored_name = f"{file_id}{ext}"
    stored_path = _UPLOAD_DIR / stored_name
    stored_path.write_bytes(data)

    return {
        "success": True,
        "data": {
            "file_id": file_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(data),
            "sha256": sha256,
        },
    }


@router.get("/{file_id}")
async def get_file_meta(
    file_id: str,
    user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get metadata for an uploaded file."""
    matches = list(_UPLOAD_DIR.glob(f"{file_id}.*"))
    if not matches:
        raise HTTPException(404, "File not found")
    p = matches[0]
    return {
        "success": True,
        "data": {
            "file_id": file_id,
            "filename": p.name,
            "size_bytes": p.stat().st_size,
        },
    }
