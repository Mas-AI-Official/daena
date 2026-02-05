
import sqlite3
import os

DB_PATH = "daena.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print("No DB found, creating fresh via app startup...")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print("Migrating Database Schema...")
    
    # 1. Update brain_models table
    # Check existing columns
    c.execute("PRAGMA table_info(brain_models)")
    cols = [row[1] for row in c.fetchall()]
    
    updates = [
        ("model_id", "TEXT UNIQUE"),
        ("endpoint_base", "TEXT"),
        ("deployment_name", "TEXT"),
        ("api_version", "TEXT"),
        ("cost_per_1k_input", "FLOAT DEFAULT 0"),
        ("cost_per_1k_output", "FLOAT DEFAULT 0"),
        ("monthly_budget_usd", "FLOAT"),
        ("daily_budget_usd", "FLOAT"),
        ("requires_approval_above_usd", "FLOAT"),
        ("enabled", "BOOLEAN DEFAULT 1"), 
        ("routing_weight", "INTEGER DEFAULT 10"),
        ("max_tokens_default", "INTEGER DEFAULT 4096"),
        ("capabilities", "JSON")
    ]
    
    for col, type_def in updates:
        if col not in cols:
            print(f"Adding column {col} to brain_models...")
            try:
                c.execute(f"ALTER TABLE brain_models ADD COLUMN {col} {type_def}")
            except Exception as e:
                print(f"Error adding {col}: {e}")

    # 2. Add model_name if missing (BrainModel had model_path, provider, but maybe not model_name explicitly in previous vers?)
    # Previous: model_type, model_path, provider. New: model_name specific for Azure Inference.
    if "model_name" not in cols:
         try:
            c.execute("ALTER TABLE brain_models ADD COLUMN model_name TEXT")
         except: pass

    # 3. Create new tables if not exist (UsageLedger, FounderPolicy)
    # SQLAlchemy create_all does this usually, but we can double check.
    # We'll rely on SQLAlchemy for new tables, just column patching here.
    
    conn.commit()
    conn.close()
    print("Migration Check Complete.")

if __name__ == "__main__":
    migrate()
