#!/usr/bin/env python3
import sqlite3

def check_database():
    conn = sqlite3.connect('daena.db')
    cursor = conn.cursor()
    
    print("🔍 Checking database state...")
    
    # Check agent roles
    cursor.execute('SELECT role, COUNT(*) FROM agents GROUP BY role')
    print("\n📊 Agent roles:")
    for role, count in cursor.fetchall():
        print(f"  {role}: {count}")
    
    # Check agents per department (excluding council)
    cursor.execute('SELECT department, COUNT(*) FROM agents WHERE role != "council" GROUP BY department')
    print("\n📊 Agents per department:")
    total_agents = 0
    for dept, count in cursor.fetchall():
        print(f"  {dept}: {count}")
        total_agents += count
    
    print(f"\n📊 Total non-council agents: {total_agents}")
    
    # Check departments
    cursor.execute('SELECT name, slug FROM departments')
    print("\n📊 Departments:")
    for name, slug in cursor.fetchall():
        print(f"  {name} ({slug})")
    
    conn.close()

if __name__ == "__main__":
    check_database() 