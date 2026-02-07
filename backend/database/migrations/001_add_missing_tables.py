"""
Migration: Add missing tables for super-sync implementation
"""
import sqlite3
import os

def migrate():
    db_path = os.getenv('DATABASE_URL', 'sqlite:///daena.db').replace('sqlite:///', '')

    # Handle both relative and absolute paths
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.getcwd(), db_path)

    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path) or '.', exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print(f"[Migration] Connected to database: {db_path}")

    # Precedents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS precedents (
            id TEXT PRIMARY KEY,
            problem_summary TEXT NOT NULL,
            domain TEXT NOT NULL,
            quintessence_consulted TEXT,  -- JSON array
            expert_conclusions TEXT,  -- JSON
            baseline_consensus TEXT,
            final_decision TEXT,
            rationale TEXT,
            confidence REAL,
            tags TEXT,  -- JSON array
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            applied_to_domains TEXT,  -- JSON array
            success_rate REAL DEFAULT 0.5,
            feedback_count INTEGER DEFAULT 0,
            cross_domain_potential REAL,
            pattern_type TEXT,
            abstract_principle TEXT
        )
    """)
    print("[Migration] Created precedents table")

    # Patterns table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patterns (
            id TEXT PRIMARY KEY,
            pattern_type TEXT NOT NULL,
            principle TEXT,
            indicators TEXT,  -- JSON array
            applicability TEXT,  -- JSON array
            confidence REAL,
            precedent_ids TEXT,  -- JSON array
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            usage_count INTEGER DEFAULT 0
        )
    """)
    print("[Migration] Created patterns table")

    # Projects table (if not exists)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            tenant_id INTEGER,
            department_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            total_tasks INTEGER DEFAULT 0,
            completed_tasks INTEGER DEFAULT 0,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            FOREIGN KEY (department_id) REFERENCES departments(id)
        )
    """)
    print("[Migration] Created/verified projects table")

    # Tasks table (for projects)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT UNIQUE NOT NULL,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'todo',
            assignee_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            order_index INTEGER DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
    """)
    print("[Migration] Created tasks table")

    # Comments table (for projects)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id TEXT UNIQUE NOT NULL,
            project_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            parent_id TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        )
    """)
    print("[Migration] Created comments table")

    # Tool connections table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tool_connections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            connection_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            tool_id TEXT NOT NULL,
            credentials_encrypted TEXT NOT NULL,
            connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    """)
    print("[Migration] Created tool_connections table")

    # Chat sessions table (for history)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            title TEXT,
            preview TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_message_at TIMESTAMP
        )
    """)
    print("[Migration] Created chat_sessions table")

    # Messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id TEXT UNIQUE NOT NULL,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,  -- user, assistant, system
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actions TEXT,  -- JSON array of executed actions
            FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
        )
    """)
    print("[Migration] Created messages table")

    # Models table (for brain/model management)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            size_gb REAL,
            provider TEXT DEFAULT 'ollama',
            enabled BOOLEAN DEFAULT 0,
            status TEXT DEFAULT 'available',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP
        )
    """)
    print("[Migration] Created models table")

    # API keys table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL,  -- openai, anthropic, google
            key_encrypted TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_used TIMESTAMP
        )
    """)
    print("[Migration] Created api_keys table")

    # Update existing tables (add columns if not exists)
    try:
        cursor.execute("ALTER TABLE skills ADD COLUMN operators TEXT DEFAULT '[\"founder\", \"daena\"]'")
        print("[Migration] Added operators column to skills")
    except sqlite3.OperationalError:
        print("[Migration] operators column already exists in skills")

    try:
        cursor.execute("ALTER TABLE skills ADD COLUMN enabled BOOLEAN DEFAULT 1")
        print("[Migration] Added enabled column to skills")
    except sqlite3.OperationalError:
        print("[Migration] enabled column already exists in skills")

    # Ensure indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_projects_tenant ON projects(tenant_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_project ON comments(project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_models_enabled ON models(enabled)")
    print("[Migration] Created indexes")

    conn.commit()
    conn.close()

    print("✅ Migration completed successfully")

if __name__ == "__main__":
    migrate()
