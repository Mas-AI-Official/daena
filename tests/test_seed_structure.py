"""
Test that the seed script creates the correct 8 departments / 6 agents structure.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import sys

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from database import engine, Base, Department, Agent
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_session():
    """Create a test database session."""
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    yield session
    session.rollback()
    Base.metadata.drop_all(engine)
    session.close()


def test_seed_creates_8_departments(db_session):
    """Test that seeding creates exactly 8 departments."""
    from backend.scripts.seed_6x8_council import seed_departments
    
    asyncio.run(seed_departments(db_session))
    
    departments = db_session.query(Department).all()
    assert len(departments) == 8, f"Expected 8 departments, got {len(departments)}"
    
    # Verify all expected departments exist
    expected_slugs = {
        "engineering", "product", "sales", "marketing",
        "finance", "hr", "legal", "customer"
    }
    actual_slugs = {dept.slug for dept in departments}
    assert actual_slugs == expected_slugs, f"Department slugs mismatch: {actual_slugs} vs {expected_slugs}"


def test_seed_creates_6_agents_per_department(db_session):
    """Test that each department has exactly 6 agents."""
    from backend.scripts.seed_6x8_council import seed_departments, seed_agents
    
    asyncio.run(seed_departments(db_session))
    asyncio.run(seed_agents(db_session))
    
    departments = db_session.query(Department).all()
    for dept in departments:
        agents = db_session.query(Agent).filter(Agent.department == dept.slug).all()
        assert len(agents) == 6, f"Department {dept.slug} has {len(agents)} agents, expected 6"
        
        # Verify agent roles
        expected_roles = {
            "advisor_a", "advisor_b", "scout_internal", "scout_external",
            "synth", "executor"
        }
        actual_roles = {agent.role for agent in agents}
        assert actual_roles == expected_roles, f"Department {dept.slug} roles mismatch: {actual_roles} vs {expected_roles}"


def test_seed_total_agents_count(db_session):
    """Test that total agent count is 48 (8 departments × 6 agents)."""
    from backend.scripts.seed_6x8_council import seed_departments, seed_agents
    
    asyncio.run(seed_departments(db_session))
    asyncio.run(seed_agents(db_session))
    
    total_agents = db_session.query(Agent).count()
    assert total_agents == 48, f"Expected 48 total agents, got {total_agents}"


def test_seed_sunflower_indices(db_session):
    """Test that departments have correct sunflower indices (1-8)."""
    from backend.scripts.seed_6x8_council import seed_departments
    
    asyncio.run(seed_departments(db_session))
    
    departments = db_session.query(Department).order_by(Department.sunflower_index).all()
    assert len(departments) == 8
    
    for i, dept in enumerate(departments, start=1):
        assert dept.sunflower_index == i, f"Department {dept.slug} has index {dept.sunflower_index}, expected {i}"


def test_seed_idempotent(db_session):
    """Test that running seed multiple times doesn't create duplicates."""
    from backend.scripts.seed_6x8_council import seed_departments, seed_agents
    
    # Run seed twice
    asyncio.run(seed_departments(db_session))
    asyncio.run(seed_agents(db_session))
    
    first_count_depts = db_session.query(Department).count()
    first_count_agents = db_session.query(Agent).count()
    
    asyncio.run(seed_departments(db_session))
    asyncio.run(seed_agents(db_session))
    
    second_count_depts = db_session.query(Department).count()
    second_count_agents = db_session.query(Agent).count()
    
    assert first_count_depts == second_count_depts == 8
    assert first_count_agents == second_count_agents == 48

