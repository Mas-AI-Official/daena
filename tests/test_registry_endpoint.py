"""
Tests for the registry summary endpoint (/api/v1/registry/summary)
Validates 8×6 structure alignment.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.database import Base, engine, SessionLocal, Department, Agent
from backend.config.council_config import COUNCIL_CONFIG
from backend.main import app


@pytest.fixture(scope="function")
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(scope="function")
def seeded_database(db_session: Session):
    """Seed database with 8 departments × 6 agents = 48 agents."""
    # Create 8 departments
    departments = []
    for i, slug in enumerate(COUNCIL_CONFIG.DEPARTMENT_SLUGS, 1):
        dept = Department(
            slug=slug,
            name=COUNCIL_CONFIG.DEPARTMENT_NAMES[slug],
            description=f"Test {slug} department",
            color="#0066cc",
            sunflower_index=i,
            cell_id=f"D{i}",
            status="active"
        )
        db_session.add(dept)
        departments.append(dept)
    
    db_session.commit()
    
    # Create 6 agents per department
    total_agents = 0
    for dept in departments:
        for role in COUNCIL_CONFIG.AGENT_ROLES:
            agent = Agent(
                name=f"{role}_{dept.slug}",
                department=dept.slug,
                department_id=dept.id,
                role=role,
                status="active",
                is_active=True,
                sunflower_index=dept.sunflower_index * 10 + COUNCIL_CONFIG.AGENT_ROLES.index(role) + 1,
                cell_id=f"A{dept.sunflower_index}{COUNCIL_CONFIG.AGENT_ROLES.index(role) + 1}"
            )
            db_session.add(agent)
            total_agents += 1
    
    db_session.commit()
    
    return {
        "departments": departments,
        "total_agents": total_agents
    }


def test_registry_summary_structure(client: TestClient, seeded_database, db_session: Session):
    """Test that registry summary returns correct 8×6 structure."""
    response = client.get(
        "/api/v1/registry/summary",
        headers={"X-API-Key": "daena_secure_key_2025"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Validate structure
    assert data["success"] is True
    assert data["departments"] == 8
    assert data["agents"] == 48
    assert data["roles_per_department"] == 6
    
    # Validate expected counts
    assert data["expected"]["departments"] == 8
    assert data["expected"]["agents"] == 48
    assert data["expected"]["roles_per_department"] == 6
    
    # Validate structure validation
    assert data["validation"]["departments_valid"] is True
    assert data["validation"]["agents_valid"] is True
    assert data["validation"]["roles_valid"] is True
    assert data["validation"]["structure_valid"] is True


def test_registry_summary_department_details(client: TestClient, seeded_database, db_session: Session):
    """Test that department details are correct."""
    response = client.get(
        "/api/v1/registry/summary",
        headers={"X-API-Key": "daena_secure_key_2025"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Validate department details
    assert len(data["department_details"]) == 8
    
    for dept_detail in data["department_details"]:
        assert dept_detail["agent_count"] == 6
        assert len(dept_detail["roles"]) == 6
        
        # Each role should have exactly 1 agent
        for role, count in dept_detail["roles"].items():
            assert count == 1, f"Expected 1 agent for role {role} in {dept_detail['slug']}, got {count}"


def test_registry_summary_agents_by_role(client: TestClient, seeded_database, db_session: Session):
    """Test that agents_by_role counts are correct (8 agents per role)."""
    response = client.get(
        "/api/v1/registry/summary",
        headers={"X-API-Key": "daena_secure_key_2025"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Each role should have exactly 8 agents (one per department)
    for role, count in data["agents_by_role"].items():
        assert count == 8, f"Expected 8 agents for role {role}, got {count}"


def test_registry_summary_departments_by_role(client: TestClient, seeded_database, db_session: Session):
    """Test that departments_by_role counts are correct (6 agents per department)."""
    response = client.get(
        "/api/v1/registry/summary",
        headers={"X-API-Key": "daena_secure_key_2025"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Each department should have exactly 6 agents
    for dept_slug, count in data["departments_by_role"].items():
        assert count == 6, f"Expected 6 agents for department {dept_slug}, got {count}"


def test_registry_summary_missing_agents(client: TestClient, db_session: Session):
    """Test that registry summary handles missing agents correctly."""
    # Create only 4 departments with 3 agents each
    for i, slug in enumerate(list(COUNCIL_CONFIG.DEPARTMENT_SLUGS)[:4], 1):
        dept = Department(
            slug=slug,
            name=COUNCIL_CONFIG.DEPARTMENT_NAMES[slug],
            description=f"Test {slug} department",
            color="#0066cc",
            sunflower_index=i,
            cell_id=f"D{i}",
            status="active"
        )
        db_session.add(dept)
        db_session.flush()
        
        # Create only 3 agents
        for role in list(COUNCIL_CONFIG.AGENT_ROLES)[:3]:
            agent = Agent(
                name=f"{role}_{slug}",
                department=slug,
                department_id=dept.id,
                role=role,
                status="active",
                is_active=True,
                sunflower_index=i * 10 + COUNCIL_CONFIG.AGENT_ROLES.index(role) + 1,
                cell_id=f"A{i}{COUNCIL_CONFIG.AGENT_ROLES.index(role) + 1}"
            )
            db_session.add(agent)
    
    db_session.commit()
    
    response = client.get(
        "/api/v1/registry/summary",
        headers={"X-API-Key": "daena_secure_key_2025"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Should detect invalid structure
    assert data["departments"] == 4
    assert data["agents"] == 12
    assert data["validation"]["structure_valid"] is False
    assert data["validation"]["departments_valid"] is False
    assert data["validation"]["agents_valid"] is False


def test_registry_summary_requires_auth(client: TestClient):
    """Test that registry summary requires authentication."""
    response = client.get("/api/v1/registry/summary")
    
    assert response.status_code == 401  # Unauthorized


def test_registry_summary_invalid_auth(client: TestClient):
    """Test that registry summary rejects invalid API key."""
    response = client.get(
        "/api/v1/registry/summary",
        headers={"X-API-Key": "invalid_key"}
    )
    
    assert response.status_code == 401  # Unauthorized

