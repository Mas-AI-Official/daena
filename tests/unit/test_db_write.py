"""Test database write access"""
import sqlite3
from pathlib import Path

db_path = Path("D:/Ideas/Daena_old_upgrade_20251213/daena.db")

print(f"Testing database: {db_path}")
print(f"Exists: {db_path.exists()}")
print(f"Writable: {db_path.exists() and not db_path.stat().st_file_attributes & 1}")

try:
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Try to write
    cursor.execute("CREATE TABLE IF NOT EXISTS test_write (id INTEGER PRIMARY KEY, value TEXT)")
    cursor.execute("INSERT INTO test_write (value) VALUES ('test')")
    conn.commit()
    
    # Try to read
    cursor.execute("SELECT * FROM test_write LIMIT 1")
    result = cursor.fetchone()
    
    # Cleanup
    cursor.execute("DROP TABLE test_write")
    conn.commit()
    conn.close()
    
    print("✅ Database is writable!")
    print(f"Test result: {result}")
except Exception as e:
    print(f"❌ Database write failed: {e}")
