"""File upload, listing, retrieval, and deletion endpoints.

Stores uploaded files in a local directory (dev) or cloud storage (production).
Returns a file_id that can be attached to chat messages.
All operations are multi-tenant isolated via tenant_id.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.files import FileRecord

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
    purpose: str = Query("general", pattern="^(general|chat_attachment|project_file)$"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Upload a file and return its file_id for chat attachment."""
    if not _type_allowed(file.content_type):
        raise HTTPException(400, f"File type not allowed: {file.content_type}")

    data = await file.read()
    if len(data) > _MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large (max {_MAX_FILE_SIZE // (1024 * 1024)}MB)")

    file_id = uuid.uuid4()
    sha256 = hashlib.sha256(data).hexdigest()
    ext = Path(file.filename or "file").suffix or ".bin"
    stored_name = f"{file_id}{ext}"
    stored_path = _UPLOAD_DIR / stored_name
    stored_path.write_bytes(data)

    record = FileRecord(
        id=file_id,
        tenant_id=user.tenant_id,
        user_id=user.id,
        filename=stored_name,
        original_filename=file.filename or "file",
        content_type=file.content_type,
        size_bytes=len(data),
        sha256=sha256,
        storage_path=str(stored_name),
        purpose=purpose,
    )
    db.add(record)
    await db.flush()

    return {
        "success": True,
        "data": {
            "file_id": str(file_id),
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(data),
            "sha256": sha256,
            "purpose": purpose,
        },
    }


@router.get("")
async def list_files(
    search: str | None = Query(None, description="Search by original filename"),
    sort: str = Query("created_at", pattern="^(created_at|size_bytes|original_filename)$"),
    dir: str = Query("desc", alias="dir", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    purpose: str | None = Query(None, pattern="^(general|chat_attachment|project_file)$"),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List files for the current user's tenant with pagination and search."""
    base_query = select(FileRecord).where(FileRecord.tenant_id == user.tenant_id)

    if search:
        base_query = base_query.where(
            FileRecord.original_filename.ilike(f"%{search}%")
        )
    if purpose:
        base_query = base_query.where(FileRecord.purpose == purpose)

    # Count total
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Sort
    sort_col = getattr(FileRecord, sort)
    if dir == "desc":
        base_query = base_query.order_by(sort_col.desc())
    else:
        base_query = base_query.order_by(sort_col.asc())

    # Paginate
    offset = (page - 1) * per_page
    base_query = base_query.offset(offset).limit(per_page)

    result = await db.execute(base_query)
    records = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": str(r.id),
                "filename": r.filename,
                "original_filename": r.original_filename,
                "content_type": r.content_type,
                "size_bytes": r.size_bytes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "purpose": r.purpose,
                "sha256": r.sha256,
            }
            for r in records
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": (total + per_page - 1) // per_page if per_page else 1,
        },
    }


@router.get("/{file_id}")
async def get_file_meta(
    file_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get metadata for an uploaded file."""
    result = await db.execute(
        select(FileRecord).where(
            FileRecord.id == file_id,
            FileRecord.tenant_id == user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "File not found")

    return {
        "success": True,
        "data": {
            "file_id": str(record.id),
            "filename": record.original_filename,
            "stored_filename": record.filename,
            "content_type": record.content_type,
            "size_bytes": record.size_bytes,
            "sha256": record.sha256,
            "purpose": record.purpose,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
        },
    }


@router.delete("/{file_id}")
async def delete_file(
    file_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Delete a file from filesystem and database."""
    result = await db.execute(
        select(FileRecord).where(
            FileRecord.id == file_id,
            FileRecord.tenant_id == user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "File not found")

    # Remove from filesystem
    stored_path = _UPLOAD_DIR / record.storage_path
    if stored_path.exists():
        stored_path.unlink()

    # Remove from database
    await db.delete(record)
    await db.flush()

    return {
        "success": True,
        "data": {"file_id": str(file_id), "deleted": True},
    }


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """Download a file by its ID."""
    result = await db.execute(
        select(FileRecord).where(
            FileRecord.id == file_id,
            FileRecord.tenant_id == user.tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "File not found")

    stored_path = _UPLOAD_DIR / record.storage_path
    if not stored_path.exists():
        raise HTTPException(404, "File not found on disk")

    return FileResponse(
        path=str(stored_path),
        filename=record.original_filename,
        media_type=record.content_type or "application/octet-stream",
    )
