"""
Database Inspector Tool for Daena AI VP

Gives Daena read-only access to inspect the database.
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def list_tables() -> Dict[str, Any]:
    """
    List all tables in the database.
    
    Returns:
        {success, tables, error}
    """
    try:
        from backend.database import engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        return {
            "success": True,
            "tables": tables,
            "count": len(tables)
        }
    except Exception as e:
        logger.error(f"list_tables error: {e}")
        return {"success": False, "error": str(e)}


def describe_table(table_name: str) -> Dict[str, Any]:
    """
    Get schema/columns of a table.
    
    Returns:
        {success, table, columns, error}
    """
    try:
        from backend.database import engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        
        if table_name not in inspector.get_table_names():
            return {"success": False, "error": f"Table not found: {table_name}"}
        
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                "type": str(col["type"]),
                "nullable": col.get("nullable", True),
                "primary_key": col.get("autoincrement", False)
            })
        
        # Get primary keys
        pk = inspector.get_pk_constraint(table_name)
        
        # Get foreign keys
        fks = inspector.get_foreign_keys(table_name)
        
        return {
            "success": True,
            "table": table_name,
            "columns": columns,
            "primary_key": pk.get("constrained_columns", []),
            "foreign_keys": [
                {
                    "column": fk["constrained_columns"],
                    "references": f"{fk['referred_table']}.{fk['referred_columns']}"
                }
                for fk in fks
            ]
        }
    except Exception as e:
        logger.error(f"describe_table error: {e}")
        return {"success": False, "error": str(e)}


def count_records(table_name: str) -> Dict[str, Any]:
    """
    Count records in a table.
    
    Returns:
        {success, table, count, error}
    """
    try:
        from backend.database import engine
        from sqlalchemy import text, inspect
        
        inspector = inspect(engine)
        if table_name not in inspector.get_table_names():
            return {"success": False, "error": f"Table not found: {table_name}"}
        
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar()
        
        return {
            "success": True,
            "table": table_name,
            "count": count
        }
    except Exception as e:
        logger.error(f"count_records error: {e}")
        return {"success": False, "error": str(e)}


def query_read_only(sql: str, limit: int = 100) -> Dict[str, Any]:
    """
    Execute a READ-ONLY SQL query.
    
    Security: Only SELECT statements allowed.
    
    Returns:
        {success, rows, columns, row_count, error}
    """
    try:
        # Security: only allow SELECT
        sql_clean = sql.strip().upper()
        if not sql_clean.startswith("SELECT"):
            return {"success": False, "error": "Only SELECT queries allowed"}
        
        # Block dangerous keywords
        dangerous = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE", "GRANT", "EXECUTE"]
        for d in dangerous:
            if d in sql_clean:
                return {"success": False, "error": f"Dangerous keyword detected: {d}"}
        
        # Add LIMIT if not present
        if "LIMIT" not in sql_clean:
            sql = f"{sql} LIMIT {limit}"
        
        from backend.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
        
        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": len(rows) >= limit
        }
    except Exception as e:
        logger.error(f"query_read_only error: {e}")
        return {"success": False, "error": str(e)}


def get_table_sample(table_name: str, limit: int = 5) -> Dict[str, Any]:
    """
    Get sample rows from a table.
    
    Returns:
        {success, table, sample, error}
    """
    try:
        from backend.database import engine
        from sqlalchemy import text, inspect
        
        inspector = inspect(engine)
        if table_name not in inspector.get_table_names():
            return {"success": False, "error": f"Table not found: {table_name}"}
        
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM {table_name} LIMIT {limit}"))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
        
        return {
            "success": True,
            "table": table_name,
            "columns": columns,
            "sample": rows
        }
    except Exception as e:
        logger.error(f"get_table_sample error: {e}")
        return {"success": False, "error": str(e)}


# Convenience function for Daena
async def daena_db(command: str) -> Dict[str, Any]:
    """
    Parse a natural language database command and execute.
    
    Examples:
        "show tables"
        "describe departments"
        "count agents"
        "select * from departments where name like '%engineering%'"
    """
    command = command.lower().strip()
    
    if command in ["show tables", "list tables", "tables"]:
        return list_tables()
    
    elif command.startswith("describe ") or command.startswith("schema "):
        table = command.split(" ", 1)[1].strip()
        return describe_table(table)
    
    elif command.startswith("count "):
        table = command[6:].strip()
        return count_records(table)
    
    elif command.startswith("sample "):
        parts = command.split()
        table = parts[1] if len(parts) > 1 else ""
        limit = int(parts[2]) if len(parts) > 2 else 5
        return get_table_sample(table, limit)
    
    elif command.startswith("select "):
        return query_read_only(command)
    
    else:
        return {
            "success": False,
            "error": "Unknown command. Try: show tables, describe <table>, count <table>, sample <table>, or SELECT query"
        }
