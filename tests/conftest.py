import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import os
import sys

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend.main import app
try:
    from backend.config.settings import get_settings
except ImportError:  # pragma: no cover - fallback for legacy structure
    def get_settings():
        class _Stub:
            api_key = None
            secret_key = None
            test_api_key = None
        return _Stub()
from backend.database import Base, get_db

try:
    from backend.routes.consultation import consultations_store, messages_store  # type: ignore[attr-defined]
except (ImportError, AttributeError):  # pragma: no cover - legacy compatibility
    consultations_store = {}
    messages_store = {}

settings = get_settings()

# Create test database engine
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def clear_in_memory_stores():
    """Fixture to clear in-memory stores before each test."""
    consultations_store.clear()
    messages_store.clear()
    yield

@pytest.fixture(scope="function")
def client(db_session, clear_in_memory_stores):
    def override_get_db():
        try:
            yield db_session
        finally:
            db_session.close()
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def test_user():
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword123"
    }

@pytest.fixture(scope="function")
def test_agent():
    return {
        "name": "TestAgent",
        "type": "voice",
        "capabilities": ["speech", "consultation"]
    } 