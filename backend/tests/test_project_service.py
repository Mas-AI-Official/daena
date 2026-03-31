"""Tests for ProjectService and Project model (DB-backed).

Covers Project model, ProjectService async CRUD, filtering,
and API endpoint request model validation.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.project import Project
from app.services.project_service import ProjectService


# ── Project model tests ──


class TestProjectModel:
    def test_default_fields(self):
        project = Project(
            name="Test",
            owner_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )
        assert project.name == "Test"
        # Server defaults apply on INSERT; Python-side may be None before flush
        assert project.description in ("", None)
        assert project.is_active in (True, None)
        assert project.settings in ({}, None)

    def test_to_dict(self):
        pid = uuid.uuid4()
        oid = uuid.uuid4()
        project = Project(
            id=pid,
            name="Test",
            owner_id=oid,
            tenant_id=uuid.uuid4(),
            description="A test project",
            memory_scope="project:test",
            is_active=True,
            settings={},
        )
        d = project.to_dict()
        assert d["name"] == "Test"
        assert d["owner_id"] == str(oid)
        assert d["description"] == "A test project"
        assert d["task_count"] == 0
        assert d["file_count"] == 0
        assert d["is_active"] is True
        assert d["settings"] == {}

    def test_to_dict_includes_settings(self):
        project = Project(
            name="Test",
            owner_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            settings={"governance": "strict"},
        )
        d = project.to_dict()
        assert d["settings"] == {"governance": "strict"}

    def test_to_dict_includes_working_directory(self):
        project = Project(
            name="Test",
            owner_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            working_directory="/home/user/project",
        )
        d = project.to_dict()
        assert d["working_directory"] == "/home/user/project"


# ── ProjectService async tests ──


class TestProjectService:
    @pytest.fixture
    async def tenant_id(self, db_session):
        from app.models.identity import Tenant
        tenant = Tenant(name="Test Tenant", slug=f"test-{uuid.uuid4().hex[:8]}", plan="FREE")
        db_session.add(tenant)
        await db_session.flush()
        return tenant.id

    @pytest.fixture
    def service(self, db_session):
        return ProjectService(db_session)

    @pytest.mark.asyncio
    async def test_create_project(self, service, tenant_id):
        owner_id = uuid.uuid4()
        project = await service.create(
            name="Daena V2",
            owner_id=owner_id,
            tenant_id=tenant_id,
            description="V2 automation",
        )
        assert project["name"] == "Daena V2"
        assert project["owner_id"] == str(owner_id)
        assert project["description"] == "V2 automation"
        assert project["memory_scope"] == "project:daena-v2"

    @pytest.mark.asyncio
    async def test_create_with_settings(self, service, tenant_id):
        project = await service.create(
            name="Test",
            owner_id=uuid.uuid4(),
            tenant_id=tenant_id,
            settings={"cost_ceiling": 5.0},
        )
        assert project["settings"] == {"cost_ceiling": 5.0}

    @pytest.mark.asyncio
    async def test_create_with_working_directory(self, service, tenant_id):
        project = await service.create(
            name="Test",
            owner_id=uuid.uuid4(),
            tenant_id=tenant_id,
            working_directory="/tmp/daena",
        )
        assert project["working_directory"] == "/tmp/daena"

    @pytest.mark.asyncio
    async def test_get_existing(self, service, tenant_id):
        owner_id = uuid.uuid4()
        project = await service.create(name="Test", owner_id=owner_id, tenant_id=tenant_id)
        found = await service.get(uuid.UUID(project["id"]), tenant_id=tenant_id)
        assert found is not None
        assert found["id"] == project["id"]

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, service, tenant_id):
        result = await service.get(uuid.uuid4(), tenant_id=tenant_id)
        assert result is None

    @pytest.mark.asyncio
    async def test_list_for_user(self, service, tenant_id):
        owner1 = uuid.uuid4()
        owner2 = uuid.uuid4()
        await service.create(name="P1", owner_id=owner1, tenant_id=tenant_id)
        await service.create(name="P2", owner_id=owner1, tenant_id=tenant_id)
        await service.create(name="P3", owner_id=owner2, tenant_id=tenant_id)

        user1_projects = await service.list_for_user(owner_id=owner1, tenant_id=tenant_id)
        assert len(user1_projects) == 2

        user2_projects = await service.list_for_user(owner_id=owner2, tenant_id=tenant_id)
        assert len(user2_projects) == 1

    @pytest.mark.asyncio
    async def test_list_for_user_respects_limit(self, service, tenant_id):
        owner_id = uuid.uuid4()
        for i in range(10):
            await service.create(name=f"P{i}", owner_id=owner_id, tenant_id=tenant_id)

        projects = await service.list_for_user(owner_id=owner_id, tenant_id=tenant_id, limit=5)
        assert len(projects) == 5

    @pytest.mark.asyncio
    async def test_update_fields(self, service, tenant_id):
        owner_id = uuid.uuid4()
        project = await service.create(name="Original", owner_id=owner_id, tenant_id=tenant_id)

        updated = await service.update(
            uuid.UUID(project["id"]),
            tenant_id=tenant_id,
            name="Updated Name",
            description="New desc",
        )
        assert updated is not None
        assert updated["name"] == "Updated Name"
        assert updated["description"] == "New desc"

    @pytest.mark.asyncio
    async def test_update_immutable_fields(self, service, tenant_id):
        """id, owner_id, tenant_id, and created_at should not be changeable."""
        owner_id = uuid.uuid4()
        project = await service.create(name="Test", owner_id=owner_id, tenant_id=tenant_id)
        original_id = project["id"]
        original_owner = project["owner_id"]

        await service.update(
            uuid.UUID(project["id"]),
            tenant_id=tenant_id,
            id="hacked-id",
            owner_id="hacked-owner",
        )
        retrieved = await service.get(uuid.UUID(original_id), tenant_id=tenant_id)
        assert retrieved["id"] == original_id
        assert retrieved["owner_id"] == original_owner

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, service, tenant_id):
        result = await service.update(uuid.uuid4(), tenant_id=tenant_id, name="test")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_existing(self, service, tenant_id):
        owner_id = uuid.uuid4()
        project = await service.create(name="Delete Me", owner_id=owner_id, tenant_id=tenant_id)
        result = await service.delete(uuid.UUID(project["id"]), tenant_id=tenant_id)
        assert result is True

        # Soft-deleted, so excluded from list
        projects = await service.list_for_user(owner_id=owner_id, tenant_id=tenant_id)
        assert len(projects) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, service, tenant_id):
        result = await service.delete(uuid.uuid4(), tenant_id=tenant_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_count(self, service, tenant_id):
        owner_id = uuid.uuid4()
        assert await service.count(tenant_id=tenant_id) == 0
        await service.create(name="P1", owner_id=owner_id, tenant_id=tenant_id)
        assert await service.count(tenant_id=tenant_id) == 1
        await service.create(name="P2", owner_id=owner_id, tenant_id=tenant_id)
        assert await service.count(tenant_id=tenant_id) == 2

    @pytest.mark.asyncio
    async def test_memory_scope_slugification(self, service, tenant_id):
        """Spaces replaced with dashes, lowercased."""
        project = await service.create(
            name="My Big Project",
            owner_id=uuid.uuid4(),
            tenant_id=tenant_id,
        )
        assert project["memory_scope"] == "project:my-big-project"


# ── Request model validation ──


class TestProjectRequestModels:
    def test_create_body_validates_name(self):
        from app.api.v1.projects import CreateProjectBody

        with pytest.raises(Exception):
            CreateProjectBody(name="")

        with pytest.raises(Exception):
            CreateProjectBody(name="a")

        body = CreateProjectBody(name="Valid Name")
        assert body.name == "Valid Name"

    def test_create_body_sanitizes_html(self):
        from app.api.v1.projects import CreateProjectBody

        body = CreateProjectBody(name="<b>Bold</b> Project")
        assert "<b>" not in body.name
        assert "Bold" in body.name

    def test_update_body_allows_none(self):
        from app.api.v1.projects import UpdateProjectBody

        body = UpdateProjectBody()
        assert body.name is None
        assert body.description is None
