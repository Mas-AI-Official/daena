"""Create missing database tables"""
import sys
sys.path.insert(0, ".")

from backend.database import engine, Base

# Create all tables
Base.metadata.create_all(bind=engine)
print("Tables created successfully!")

# Verify new tables exist
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print(f"Tables in database: {len(tables)}")
if "learning_log" in tables:
    print("✓ learning_log table exists")
if "pending_approvals" in tables:
    print("✓ pending_approvals table exists")
