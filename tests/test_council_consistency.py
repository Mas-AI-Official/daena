"""
Council Consistency Test
Validates 8 departments × 6 agents structure after seeding.
"""

import pytest
import asyncio
import requests
from backend.config.council_config import COUNCIL_CONFIG
from backend.database import SessionLocal, Department, Agent


@pytest.fixture
def api_base_url():
    """Get API base URL from environment or use default."""
    import os
    return os.getenv("DAENA_API_URL", "http://localhost:8000")


@pytest.fixture
def api_key():
    """Get API key from environment or use default."""
    import os
    return os.getenv("DAENA_API_KEY", "daena_secure_key_2025")


@pytest.fixture(scope="session")
def seeded_database():
    """Ensure database is seeded before tests run."""
    import asyncio
    import sys
    import os
    
    # Add scripts directory to path
    scripts_dir = os.path.join(os.path.dirname(__file__), "..", "backend", "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    
    # Run seed script
    try:
        from seed_6x8_council import main as seed_main
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, schedule it
            asyncio.create_task(seed_main())
        else:
            loop.run_until_complete(seed_main())
    except Exception as e:
        pytest.skip(f"Failed to seed database: {e}")
    
    yield
    
    # Cleanup if needed


def test_council_health_endpoint(api_base_url, api_key, seeded_database):
    """Test that /api/v1/health/council returns valid 8×6 structure."""
    url = f"{api_base_url}/api/v1/health/council"
    headers = {"X-API-Key": api_key}
    
    response = requests.get(url, headers=headers, timeout=10)
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    
    # Validate response structure
    assert "status" in data
    assert "departments" in data
    assert "agents" in data
    assert "roles_per_department" in data
    assert "validation" in data
    assert "expected" in data
    
    # Validate counts
    assert data["departments"] == COUNCIL_CONFIG.TOTAL_DEPARTMENTS, \
        f"Expected {COUNCIL_CONFIG.TOTAL_DEPARTMENTS} departments, got {data['departments']}"
    
    assert data["agents"] == COUNCIL_CONFIG.TOTAL_AGENTS, \
        f"Expected {COUNCIL_CONFIG.TOTAL_AGENTS} agents, got {data['agents']}"
    
    assert data["roles_per_department"] == COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT, \
        f"Expected {COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT} roles per department, got {data['roles_per_department']}"
    
    # Validate structure
    assert data["validation"]["structure_valid"] is True, \
        f"Structure invalid: {data['validation']}"
    
    assert data["status"] == "healthy", \
        f"Expected healthy status, got {data['status']}"


def test_council_structure_from_database(seeded_database):
    """Test that database has correct 8×6 structure."""
    db = SessionLocal()
    try:
        # Count departments
        dept_count = db.query(Department).filter(Department.status == "active").count()
        assert dept_count == COUNCIL_CONFIG.TOTAL_DEPARTMENTS, \
            f"Expected {COUNCIL_CONFIG.TOTAL_DEPARTMENTS} departments, found {dept_count}"
        
        # Count agents
        agent_count = db.query(Agent).filter(Agent.is_active == True).count()
        assert agent_count == COUNCIL_CONFIG.TOTAL_AGENTS, \
            f"Expected {COUNCIL_CONFIG.TOTAL_AGENTS} agents, found {agent_count}"
        
        # Verify agents per department
        for dept in db.query(Department).filter(Department.status == "active").all():
            agents = db.query(Agent).filter(
                Agent.department_id == dept.id,
                Agent.is_active == True
            ).count()
            assert agents == COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT, \
                f"Department {dept.slug} has {agents} agents, expected {COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT}"
        
    finally:
        db.close()


def test_council_config_constants():
    """Test that COUNCIL_CONFIG constants match expected values."""
    assert COUNCIL_CONFIG.TOTAL_DEPARTMENTS == 8
    assert COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT == 6
    assert COUNCIL_CONFIG.TOTAL_AGENTS == 48
    assert len(COUNCIL_CONFIG.DEPARTMENT_SLUGS) == 8
    assert len(COUNCIL_CONFIG.AGENT_ROLES) == 6


@pytest.mark.asyncio
async def test_council_health_metrics_snapshot(api_base_url, api_key, seeded_database):
    """Snapshot metrics from health endpoint for 10 seconds."""
    url = f"{api_base_url}/api/v1/health/council"
    headers = {"X-API-Key": api_key}
    
    snapshots = []
    start_time = asyncio.get_event_loop().time()
    
    # Collect snapshots for 10 seconds
    while (asyncio.get_event_loop().time() - start_time) < 10:
        try:
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                snapshots.append({
                    "timestamp": data.get("timestamp"),
                    "departments": data.get("departments"),
                    "agents": data.get("agents"),
                    "status": data.get("status")
                })
            await asyncio.sleep(1)  # Check every second
        except Exception as e:
            print(f"Error collecting snapshot: {e}")
            await asyncio.sleep(1)
    
    # Validate all snapshots are consistent
    assert len(snapshots) > 0, "No snapshots collected"
    
    for snapshot in snapshots:
        assert snapshot["departments"] == 8, f"Snapshot shows {snapshot['departments']} departments"
        assert snapshot["agents"] == 48, f"Snapshot shows {snapshot['agents']} agents"
        assert snapshot["status"] == "healthy", f"Snapshot shows status {snapshot['status']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

