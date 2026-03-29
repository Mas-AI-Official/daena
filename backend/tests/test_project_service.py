"""Tests for ProjectService and Project API (Sprint 4, Phase 6).

Covers Project dataclass, ProjectService CRUD, filtering,
task/file association, and API endpoint request models.
"""

from __future__ import annotations

import pytest

from app.services.project_service import Project, ProjectService  # noqa: I001

# ── Project dataclass tests ──


class TestProject:
    def test_default_fields(self):
        project = Project()
        assert project.id  # auto-generated UUID
        assert project.created_at  # auto-generated timestamp
        assert project.updated_at
        assert project.name == ""
        assert project.owner_id == ""
        assert project.task_ids == []
        assert project.file_paths == []
        assert project.department_ids == []
        assert project.settings == {}

    def test_custom_fields(self):
        project = Project(
            name="Test Project",
            description="A test",
            owner_id="user-1",
            working_directory="/tmp/test",
        )
        assert project.name == "Test Project"
        assert project.description == "A test"
        assert project.owner_id == "user-1"
        assert project.working_directory == "/tmp/test"

    def test_to_dict(self):
        project = Project(
            name="Test",
            owner_id="user-1",
            task_ids=["t1", "t2"],
            file_paths=["f1"],
            department_ids=["d1", "d2", "d3"],
        )
        d = project.to_dict()
        assert d["name"] == "Test"
        assert d["owner_id"] == "user-1"
        assert d["task_count"] == 2
        assert d["file_count"] == 1
        assert d["department_count"] == 3
        assert "task_ids" not in d  # to_dict uses counts, not IDs
        assert "file_paths" not in d
        assert "department_ids" not in d

    def test_to_dict_includes_settings(self):
        project = Project(settings={"governance": "strict"})
        d = project.to_dict()
        assert d["settings"] == {"governance": "strict"}

    def test_to_dict_includes_working_directory(self):
        project = Project(working_directory="/home/user/project")
        d = project.to_dict()
        assert d["working_directory"] == "/home/user/project"


# ── ProjectService tests ──


class TestProjectService:
    @pytest.fixture
    def service(self):
        return ProjectService()

    def test_create_project(self, service):
        project = service.create(
            name="Daena V2",
            owner_id="user-1",
            description="V2 automation",
        )
        assert project.name == "Daena V2"
        assert project.owner_id == "user-1"
        assert project.description == "V2 automation"
        assert project.memory_scope == "project:daena-v2"
        assert service.project_count == 1

    def test_create_with_settings(self, service):
        project = service.create(
            name="Test",
            owner_id="user-1",
            settings={"cost_ceiling": 5.0},
        )
        assert project.settings == {"cost_ceiling": 5.0}

    def test_create_with_working_directory(self, service):
        project = service.create(
            name="Test",
            owner_id="user-1",
            working_directory="/tmp/daena",
        )
        assert project.working_directory == "/tmp/daena"

    def test_get_existing(self, service):
        project = service.create(name="Test", owner_id="user-1")
        found = service.get(project.id)
        assert found is not None
        assert found.id == project.id

    def test_get_nonexistent(self, service):
        assert service.get("no-such-id") is None

    def test_list_for_user(self, service):
        service.create(name="P1", owner_id="user-1")
        service.create(name="P2", owner_id="user-1")
        service.create(name="P3", owner_id="user-2")

        user1_projects = service.list_for_user("user-1")
        assert len(user1_projects) == 2

        user2_projects = service.list_for_user("user-2")
        assert len(user2_projects) == 1

    def test_list_for_user_respects_limit(self, service):
        for i in range(10):
            service.create(name=f"P{i}", owner_id="user-1")

        projects = service.list_for_user("user-1", limit=5)
        assert len(projects) == 5

    def test_list_for_user_sorted_by_updated(self, service):
        p1 = service.create(name="First", owner_id="user-1")
        service.create(name="Second", owner_id="user-1")
        # Update p1 so it becomes most recent
        service.update(p1.id, name="First Updated")

        projects = service.list_for_user("user-1")
        assert projects[0].id == p1.id  # most recently updated

    def test_update_fields(self, service):
        project = service.create(name="Original", owner_id="user-1")
        original_updated = project.updated_at

        updated = service.update(
            project.id,
            name="Updated Name",
            description="New desc",
        )
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.description == "New desc"
        assert updated.updated_at >= original_updated

    def test_update_immutable_fields(self, service):
        """id, owner_id, and created_at should not be changeable."""
        project = service.create(
            name="Test",
            owner_id="user-1",
        )
        original_id = project.id
        original_owner = project.owner_id
        original_created = project.created_at

        service.update(
            project.id,
            id="hacked-id",
            owner_id="hacked-owner",
            created_at="2020-01-01",
        )
        assert project.id == original_id
        assert project.owner_id == original_owner
        assert project.created_at == original_created

    def test_update_nonexistent(self, service):
        result = service.update("no-such-id", name="test")
        assert result is None

    def test_delete_existing(self, service):
        project = service.create(name="Delete Me", owner_id="user-1")
        assert service.delete(project.id) is True
        assert service.project_count == 0

    def test_delete_nonexistent(self, service):
        assert service.delete("no-such-id") is False

    def test_add_task(self, service):
        project = service.create(name="Test", owner_id="user-1")
        assert service.add_task(project.id, "task-1") is True
        assert "task-1" in project.task_ids

    def test_add_task_duplicate(self, service):
        project = service.create(name="Test", owner_id="user-1")
        service.add_task(project.id, "task-1")
        assert service.add_task(project.id, "task-1") is False

    def test_add_task_nonexistent_project(self, service):
        assert service.add_task("no-such-id", "task-1") is False

    def test_add_file(self, service):
        project = service.create(name="Test", owner_id="user-1")
        assert service.add_file(project.id, "/tmp/file.txt") is True
        assert "/tmp/file.txt" in project.file_paths

    def test_add_file_duplicate(self, service):
        project = service.create(name="Test", owner_id="user-1")
        service.add_file(project.id, "/tmp/file.txt")
        assert service.add_file(project.id, "/tmp/file.txt") is False

    def test_add_file_nonexistent_project(self, service):
        assert service.add_file("no-such-id", "/tmp/file.txt") is False

    def test_project_count(self, service):
        assert service.project_count == 0
        service.create(name="P1", owner_id="user-1")
        assert service.project_count == 1
        service.create(name="P2", owner_id="user-1")
        assert service.project_count == 2

    def test_memory_scope_slugification(self, service):
        """Spaces replaced with dashes, lowercased."""
        project = service.create(
            name="My Big Project",
            owner_id="user-1",
        )
        assert project.memory_scope == "project:my-big-project"

    def test_multiple_operations(self, service):
        """Integration: create, add tasks/files, update, verify."""
        project = service.create(
            name="Full Test",
            owner_id="user-1",
            description="Integration test",
        )

        service.add_task(project.id, "task-1")
        service.add_task(project.id, "task-2")
        service.add_file(project.id, "main.py")

        service.update(project.id, description="Updated desc")

        d = project.to_dict()
        assert d["task_count"] == 2
        assert d["file_count"] == 1
        assert d["description"] == "Updated desc"
