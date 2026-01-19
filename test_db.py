import sqlite3
import os

db_path = 'daena.db'
print(f"Testing database: {os.path.abspath(db_path)}")

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Test read
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
    result = cur.fetchone()
    print(f"✅ DB READ OK - Found table: {result}")
    
    # Test write
    cur.execute("CREATE TABLE IF NOT EXISTS _test_write_permission (id INTEGER)")
    cur.execute("DROP TABLE _test_write_permission")
    conn.commit()
    print("✅ DB WRITE OK")
    
    conn.close()
    print("\n✅ DATABASE IS FULLY WRITABLE!")
except Exception as e:
    print(f"❌ ERROR: {e}")
    print("\nDatabase is READ-ONLY or locked!")
