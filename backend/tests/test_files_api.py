"""Tests for /api/v1/files endpoints -- upload, list, get, delete, download."""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import Tenant, User


@pytest.fixture(autouse=True)
async def seed_user(db_session: AsyncSession, test_tenant_id: uuid.UUID, test_user_id: uuid.UUID) -> None:
    """Seed a Tenant + User so FileRecord FK constraints pass."""
    tenant = Tenant(id=test_tenant_id, name="Test Org", slug="test-org", plan="FREE", settings={})
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        id=test_user_id,
        tenant_id=test_tenant_id,
        email="test@daena.local",
        role="FOUNDER",
        display_name="Test User",
        settings={},
    )
    db_session.add(user)
    await db_session.flush()


@pytest.mark.asyncio
async def test_upload_file(client: AsyncClient, auth_headers: dict) -> None:
    """Upload a text file and verify response."""
    content = b"hello daena"
    resp = await client.post(
        "/api/v1/files/upload",
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["filename"] == "test.txt"
    assert body["data"]["size_bytes"] == len(content)
    assert body["data"]["sha256"]


@pytest.mark.asyncio
async def test_list_files(client: AsyncClient, auth_headers: dict) -> None:
    """Upload a file then list files."""
    await client.post(
        "/api/v1/files/upload",
        files={"file": ("list_test.txt", io.BytesIO(b"list test"), "text/plain")},
        headers=auth_headers,
    )

    resp = await client.get("/api/v1/files/", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert isinstance(body["data"], list)
    if body["data"]:
        rec = body["data"][0]
        assert "id" in rec
        assert "original_filename" in rec
        assert "size_bytes" in rec
        assert "sha256" in rec


@pytest.mark.asyncio
async def test_list_files_search(client: AsyncClient, auth_headers: dict) -> None:
    """Search files by filename."""
    await client.post(
        "/api/v1/files/upload",
        files={"file": ("unique_search_target.md", io.BytesIO(b"# search"), "text/plain")},
        headers=auth_headers,
    )

    resp = await client.get("/api/v1/files/", params={"search": "unique_search"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    names = [f["original_filename"] for f in body["data"]]
    assert any("unique_search_target" in n for n in names)


@pytest.mark.asyncio
async def test_list_files_sort(client: AsyncClient, auth_headers: dict) -> None:
    """Sort files by size ascending."""
    resp = await client.get("/api/v1/files/", params={"sort": "size_bytes", "dir": "asc"}, headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_file_meta(client: AsyncClient, auth_headers: dict) -> None:
    """Upload then retrieve file metadata by ID."""
    content = b"meta test"
    upload_resp = await client.post(
        "/api/v1/files/upload",
        files={"file": ("meta_test.txt", io.BytesIO(content), "text/plain")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["data"]["file_id"]

    resp = await client.get(f"/api/v1/files/{file_id}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["filename"] == "meta_test.txt"
    assert body["data"]["size_bytes"] == len(content)


@pytest.mark.asyncio
async def test_delete_file(client: AsyncClient, auth_headers: dict) -> None:
    """Upload then delete a file."""
    upload_resp = await client.post(
        "/api/v1/files/upload",
        files={"file": ("delete_me.txt", io.BytesIO(b"bye"), "text/plain")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["data"]["file_id"]

    resp = await client.delete(f"/api/v1/files/{file_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["deleted"] is True

    # Verify gone
    resp2 = await client.get(f"/api/v1/files/{file_id}", headers=auth_headers)
    assert resp2.status_code == 404


@pytest.mark.asyncio
async def test_download_file(client: AsyncClient, auth_headers: dict) -> None:
    """Upload then download a file and verify content."""
    content = b"download test content"
    upload_resp = await client.post(
        "/api/v1/files/upload",
        files={"file": ("download_test.txt", io.BytesIO(content), "text/plain")},
        headers=auth_headers,
    )
    file_id = upload_resp.json()["data"]["file_id"]

    resp = await client.get(f"/api/v1/files/{file_id}/download", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.content == content


@pytest.mark.asyncio
async def test_delete_nonexistent(client: AsyncClient, auth_headers: dict) -> None:
    """Deleting a nonexistent file returns 404."""
    resp = await client.delete(
        "/api/v1/files/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404
