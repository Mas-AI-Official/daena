from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import uuid
import asyncio
import os
from pydantic import BaseModel

# Chat storage
try:
    from backend.core.chat_storage import chat_storage
except ImportError:
    chat_storage = None

try:
    from backend.config.settings import get_settings
except ImportError:
    get_settings = None

router = APIRouter(prefix="/api/v1/daena", tags=["Daena AI VP"])

# Daena AI VP Models
class DaenaMessage(BaseModel):
    id: str
    type: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    context: Optional[Dict[str, Any]] = None

class DaenaSession(BaseModel):
    session_id: str
    user_id: Optional[str] = None
    started_at: datetime
    last_activity: datetime
    messages: List[DaenaMessage] = []
    context: Dict[str, Any] = {}
    category: str = "general"  # executive, departments, agents, general
    tags: List[str] = []  # Auto-tagged topics
    title: str = "New Chat"  # User-editable title

# Active sessions storage (DEPRECATED - use DB ChatSession instead)
# Kept for backward compatibility during migration
active_sessions: Dict[str, DaenaSession] = {}
active_connections: Dict[str, WebSocket] = {}


# Compatibility request model for legacy UIs that POST /api/v1/daena/chat
class SimpleChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


# Tool detection patterns for smart dispatch
# NOTE: Some patterns use regex-style matching (marked with 'r:' prefix)
TOOL_PATTERNS = {
    "code_scan": [r"scan\s+", "read file", "show file", "view file", "open file", "look at"],
    "code_search": ["find in code", "grep ", "where is", "locate in"],  # More specific for code
    "db_query": ["show tables", "list tables", "describe ", "count ", "select ", "database", " table"],
    "api_test": ["health check", "test endpoint", "test api", "check if", "is running"],
    "diagnostics": ["run diagnostics", "self check", "self-check", "full health", "system check", 
                    "check all backend", "audit system", "run a full", "check backend", "check frontend"],
    "analyze": ["analyze", "check for issues", "scan department", "scan all", "audit"],
    "mcp": ["discover server", "connect to", "mcp", "ask ollama", "ask antigravity", "list connections"],
    # Browser patterns - now with regex for typo tolerance
    "browser": [
        r"open\s+.{0,5}browser",   # "open the browser", "open browserr", "open my browser"
        r"go\s+to\s+",             # "go to google.com"
        r"navigate\s+to",          # "navigate to"
        "open http",               # "open http://..."
        "click ",                  # "click button"
        "fill ",                   # "fill form"
        "screenshot",              # "take screenshot"
        "browse to",               # "browse to site"
        "login to",                # "login to X"
    ],
    # Web search patterns - more flexible
    "web_search": [
        r"search\s+(for|the\s+web|online)\s*",  # "search for X", "search the web"
        r"google\s+",              # "google X"
        r"look\s+up\s+",           # "look up X"
        r"find\s+online\s*",       # "find online X"
        "web search",              # "web search"
        r"search\s+.+\s+on\s+(the\s+)?internet",  # "search X on the internet"
    ],
    "model_list": ["what models", "what brains", "list models", "list brains", "how many brain", "how many llm", "what llm", "see any other llm"],
    "workspace": ["list files", "show files", "workspace", "root folder", "my files", "my folders"],
    # New patterns for agent control and model management
    "agent_control": ["activate agent", "turn on agent", "start agent", "run agent", "enable agent",
                      "deactivate agent", "stop agent", "disable agent", "turn off agent",
                      "run the company", "process company", "start operations"],
    "model_download": ["download model", "download deepseek", "pull model", "pull deepseek", 
                       "get model", "install model", "update model", "new version of deepseek"],
    "action_execute": ["proceed", "do it", "yes do it", "execute", "start now", "go ahead", 
                       "run it", "make it happen"],
}

# Helper to match patterns (supports literal and regex)
import re
def matches_pattern(text: str, pattern: str) -> bool:
    """Match text against pattern. If pattern starts with 'r:' or contains regex chars, use regex."""
    text_lower = text.lower()
    # If it looks like a regex pattern (contains special chars)
    if any(c in pattern for c in [r'\s', r'\d', r'.', '*', '+', '?', '(', ')', '[', ']', '{', '}']):
        try:
            return bool(re.search(pattern, text_lower, re.IGNORECASE))
        except re.error:
            pass
    # Fallback to literal substring
    return pattern.lower() in text_lower


async def detect_and_execute_tool(message: str) -> Optional[Dict[str, Any]]:
    """
    Detect if the message requires a tool and execute it.
    Returns tool result or None if no tool needed.
    """
    msg_lower = message.lower().strip()
    
    # Check for code scan patterns
    for pattern in TOOL_PATTERNS["code_scan"]:
        if pattern in msg_lower:
            try:
                from backend.services.daena_tools.code_scanner import daena_scan
                # Extract the path after the pattern
                for p in TOOL_PATTERNS["code_scan"]:
                    if p in msg_lower:
                        idx = msg_lower.find(p)
                        path = message[idx + len(p):].strip().strip('"\'')
                        if path:
                            result = await daena_scan(f"scan {path}")
                            return {"tool": "code_scanner", "action": "scan", "result": result}
            except Exception as e:
                return {"tool": "code_scanner", "error": str(e)}
    
    # Check for code search patterns
    for pattern in TOOL_PATTERNS["code_search"]:
        if pattern in msg_lower:
            try:
                from backend.services.daena_tools.code_scanner import search_code
                # Extract search query
                for p in TOOL_PATTERNS["code_search"]:
                    if p in msg_lower:
                        idx = msg_lower.find(p)
                        query = message[idx + len(p):].strip().strip('"\'')
                        if query:
                            result = search_code(query)
                            return {"tool": "code_scanner", "action": "search", "result": result}
            except Exception as e:
                return {"tool": "code_scanner", "error": str(e)}
    
    # Check for DB patterns
    for pattern in TOOL_PATTERNS["db_query"]:
        if pattern in msg_lower:
            try:
                from backend.services.daena_tools.db_inspector import daena_db
                result = await daena_db(msg_lower)
                return {"tool": "db_inspector", "action": "query", "result": result}
            except Exception as e:
                return {"tool": "db_inspector", "error": str(e)}
    
    # Check for API test patterns
    for pattern in TOOL_PATTERNS["api_test"]:
        if pattern in msg_lower:
            try:
                from backend.services.daena_tools.api_tester import health_check
                result = await health_check()
                return {"tool": "api_tester", "action": "health_check", "result": result}
            except Exception as e:
                return {"tool": "api_tester", "error": str(e)}
    
    # Check for diagnostics patterns (comprehensive self-check)
    for pattern in TOOL_PATTERNS["diagnostics"]:
        if pattern in msg_lower:
            try:
                diagnostics = {"success": True, "checks": {}, "issues": [], "recommendations": []}
                
                # 1. Health check endpoints
                from backend.services.daena_tools.api_tester import health_check
                health = await health_check()
                diagnostics["checks"]["endpoints"] = health
                if health.get("summary", {}).get("failed", 0) > 0:
                    diagnostics["issues"].append(f"❌ {health['summary']['failed']} endpoint(s) failing")
                
                # 2. Database counts
                from backend.services.daena_tools.db_inspector import list_tables, count_records
                tables = list_tables()
                if tables.get("success"):
                    diagnostics["checks"]["database"] = {"tables": len(tables.get("tables", []))}
                    for table in ["departments", "agents", "chat_sessions", "councils"]:
                        if table in tables.get("tables", []):
                            count = count_records(table)
                            diagnostics["checks"]["database"][table] = count.get("count", 0)
                
                # 3. Brain/LLM status
                try:
                    import httpx
                    async with httpx.AsyncClient(timeout=3.0) as client:
                        brain_resp = await client.get("http://127.0.0.1:11434/api/tags")
                        if brain_resp.status_code == 200:
                            models = brain_resp.json().get("models", [])
                            diagnostics["checks"]["brain"] = {
                                "status": "online",
                                "models_available": len(models),
                                "model_names": [m.get("name") for m in models[:5]]
                            }
                        else:
                            diagnostics["issues"].append("⚠️ Ollama not responding properly")
                except Exception:
                    diagnostics["checks"]["brain"] = {"status": "offline"}
                    diagnostics["issues"].append("⚠️ Local brain (Ollama) is offline")
                
                # 4. Voice service status
                try:
                    from backend.services.voice_service import voice_service
                    voice_status = await voice_service.get_voice_status()
                    diagnostics["checks"]["voice"] = voice_status
                except Exception as e:
                    diagnostics["checks"]["voice"] = {"status": "error", "error": str(e)}
                    diagnostics["issues"].append(f"⚠️ Voice service: {str(e)[:50]}")
                
                # Summary
                diagnostics["summary"] = {
                    "total_issues": len(diagnostics["issues"]),
                    "health_score": health.get("summary", {}).get("health_score", "unknown"),
                    "endpoints_ok": health.get("summary", {}).get("passed", 0),
                    "endpoints_total": health.get("summary", {}).get("total", 0)
                }
                
                if len(diagnostics["issues"]) == 0:
                    diagnostics["recommendations"].append("✅ All systems operational!")
                else:
                    diagnostics["recommendations"].append("Review issues above and fix as needed")
                
                return {"tool": "diagnostics", "action": "full_system_check", "result": diagnostics}
            except Exception as e:
                return {"tool": "diagnostics", "error": str(e)}
    
    # Check for analyze patterns (comprehensive scan)
    for pattern in TOOL_PATTERNS["analyze"]:
        if pattern in msg_lower:
            try:
                # Run multiple tools and compile results
                results = {}
                
                # Get table counts
                from backend.services.daena_tools.db_inspector import list_tables, count_records
                tables_result = list_tables()
                if tables_result.get("success"):
                    results["tables"] = len(tables_result.get("tables", []))
                    # Count key tables
                    for table in ["departments", "agents", "chat_sessions"]:
                        if table in tables_result.get("tables", []):
                            count_result = count_records(table)
                            results[f"{table}_count"] = count_result.get("count", 0)
                
                # Health check
                from backend.services.daena_tools.api_tester import health_check
                health = await health_check()
                results["health"] = health.get("summary", {})
                
                # Structure analysis
                from backend.services.daena_tools.code_scanner import analyze_structure
                structure = analyze_structure(".")
                results["structure"] = {
                    "files": structure.get("total_files", 0),
                    "dirs": structure.get("total_dirs", 0)
                }
                
                return {"tool": "analyzer", "action": "comprehensive", "result": {"success": True, "analysis": results}}
            except Exception as e:
                return {"tool": "analyzer", "error": str(e)}
    
    # Check for MCP patterns
    for pattern in TOOL_PATTERNS["mcp"]:
        if pattern in msg_lower:
            try:
                from backend.services.daena_tools.mcp_client import daena_mcp
                result = await daena_mcp(message)
                return {"tool": "mcp_client", "action": "execute", "result": result}
            except Exception as e:
                return {"tool": "mcp_client", "error": str(e)}
    
    # Check for browser patterns (uses regex for typo tolerance)
    for pattern in TOOL_PATTERNS["browser"]:
        if matches_pattern(message, pattern):
            try:
                from backend.services.daena_tools.browser_automation import daena_browser
                result = await daena_browser(message)
                return {"tool": "browser", "action": "execute", "result": result}
            except Exception as e:
                return {"tool": "browser", "error": str(e)}
    
    # Check for web search patterns (uses regex for flexibility)
    for pattern in TOOL_PATTERNS["web_search"]:
        if matches_pattern(message, pattern):
            try:
                from backend.services.daena_tools.web_search import web_search
                # Extract search query - remove common prefixes
                query = message
                for prefix in ["search for ", "search the web for ", "google ", "look up ", "find online ", "web search "]:
                    if prefix in msg_lower:
                        idx = msg_lower.find(prefix)
                        query = message[idx + len(prefix):].strip().strip('"\'')
                        break
                result = await web_search(query)
                return {"tool": "web_search", "action": "search", "result": result}
            except Exception as e:
                return {"tool": "web_search", "error": str(e)}
    
    # Check for model list patterns
    for pattern in TOOL_PATTERNS["model_list"]:
        if pattern in msg_lower:
            try:
                import httpx as httpx_local
                async with httpx_local.AsyncClient(timeout=5.0) as client:
                    response = await client.get("http://127.0.0.1:8001/api/v1/brain/list-models")
                    if response.status_code == 200:
                        result = response.json()
                        return {"tool": "model_list", "action": "list", "result": result}
                    else:
                        return {"tool": "model_list", "error": f"Failed to fetch models: {response.status_code}"}
            except Exception as e:
                return {"tool": "model_list", "error": str(e)}
    
    # Check for workspace patterns
    for pattern in TOOL_PATTERNS["workspace"]:
        if pattern in msg_lower:
            try:
                import os
                from pathlib import Path
                workspace_root = Path(__file__).parent.parent.parent
                files = []
                dirs = []
                for item in workspace_root.iterdir():
                    if item.is_file():
                        files.append({"name": item.name, "size": item.stat().st_size})
                    elif item.is_dir() and not item.name.startswith('.') and item.name not in ['__pycache__', 'node_modules']:
                        dirs.append({"name": item.name, "type": "directory"})
                
                result = {
                    "success": True,
                    "workspace_path": str(workspace_root),
                    "directories": dirs[:20],
                    "files": files[:30]
                }
                return {"tool": "workspace", "action": "list", "result": result}
            except Exception as e:
                return {"tool": "workspace", "error": str(e)}
    
    # Check for agent control patterns
    for pattern in TOOL_PATTERNS["agent_control"]:
        if pattern in msg_lower:
            try:
                from backend.database import get_db, Agent
                db = next(get_db())
                try:
                    # Get all agents and their status
                    agents = db.query(Agent).filter(Agent.is_active == True).all()
                    agent_summary = []
                    for agent in agents[:10]:  # Limit to 10
                        agent_summary.append({
                            "name": agent.name,
                            "department": agent.department,
                            "status": agent.status or "ready"
                        })
                    
                    result = {
                        "success": True,
                        "action": "agent_status_report",
                        "total_agents": len(agents),
                        "agents": agent_summary,
                        "message": f"Found {len(agents)} active agents ready to assist. "
                                   "To activate specific agents, use the Agent Builder in the Founder Panel."
                    }
                    return {"tool": "agent_control", "action": "status", "result": result}
                finally:
                    db.close()
            except Exception as e:
                return {"tool": "agent_control", "error": str(e)}
    
    # Check for model download patterns
    for pattern in TOOL_PATTERNS["model_download"]:
        if pattern in msg_lower:
            try:
                import httpx as httpx_local
                # First list available models
                async with httpx_local.AsyncClient(timeout=5.0) as client:
                    tags_resp = await client.get("http://127.0.0.1:11434/api/tags")
                    if tags_resp.status_code == 200:
                        existing = [m.get("name") for m in tags_resp.json().get("models", [])]
                    else:
                        existing = []
                
                # Check what model user wants
                if "deepseek" in msg_lower:
                    model_name = "deepseek-r1:8b"  # Default deepseek
                    if "32b" in msg_lower or "biggest" in msg_lower or "highest" in msg_lower:
                        model_name = "deepseek-r1:32b"
                    elif "14b" in msg_lower:
                        model_name = "deepseek-r1:14b"
                else:
                    model_name = "deepseek-r1:8b"  # Default if not specified
                
                if model_name in existing:
                    result = {
                        "success": True,
                        "action": "already_installed",
                        "model": model_name,
                        "message": f"Model {model_name} is already installed. Ready to use!"
                    }
                else:
                    result = {
                        "success": True,
                        "action": "pull_required",
                        "model": model_name,
                        "existing_models": existing,
                        "instructions": f"To download {model_name}, run: ollama pull {model_name}\n\n"
                                        "I cannot download models directly, but you can run this command in a terminal. "
                                        "Larger models like 32b require ~20GB RAM and ~20GB disk space."
                    }
                return {"tool": "model_download", "action": "check", "result": result}
            except Exception as e:
                return {"tool": "model_download", "error": str(e)}
    
    # Check for action execute patterns (user says "proceed", "do it", etc.)
    for pattern in TOOL_PATTERNS["action_execute"]:
        if msg_lower.strip() == pattern or msg_lower.strip().startswith(pattern + " "):
            try:
                # Run diagnostics as the default action when user says "proceed"
                from backend.services.daena_tools.api_tester import health_check
                health = await health_check()
                
                from backend.services.daena_tools.db_inspector import list_tables, count_records
                tables = list_tables()
                db_info = {}
                if tables.get("success"):
                    for t in ["departments", "agents", "chat_sessions"]:
                        if t in tables.get("tables", []):
                            db_info[t] = count_records(t).get("count", 0)
                
                result = {
                    "success": True,
                    "action": "executed",
                    "health_check": health.get("summary", {}),
                    "database": db_info,
                    "message": "✅ Action executed! I've run a system check. "
                               f"Health: {health.get('summary', {}).get('health_score', 'unknown')}. "
                               f"Found {db_info.get('agents', 0)} agents, {db_info.get('departments', 0)} departments."
                }
                return {"tool": "action_execute", "action": "proceed", "result": result}
            except Exception as e:
                return {"tool": "action_execute", "error": str(e)}
    
    return None


def log_tool_execution(
    session_id: str,
    user_message: str,
    tool_name: str,
    tool_action: str,
    tool_input: dict,
    tool_output: dict,
    success: bool = True,
    error_message: str = None,
    execution_time_ms: int = None
):
    """Log a tool execution to the database for pattern learning."""
    try:
        from backend.database import get_db, ToolExecution
        db = next(get_db())
        try:
            log_entry = ToolExecution(
                session_id=session_id,
                user_message=user_message[:500] if user_message else "",
                tool_name=tool_name,
                tool_action=tool_action,
                tool_input=tool_input or {},
                tool_output=tool_output or {},
                success=success,
                error_message=error_message,
                execution_time_ms=execution_time_ms
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to log tool execution: {e}")


def format_tool_result(tool_result: Dict[str, Any]) -> str:
    """Format tool result as a readable response for Daena to present."""
    if tool_result.get("error"):
        return f"I encountered an error while executing the tool: {tool_result['error']}"
    
    result = tool_result.get("result", {})
    tool = tool_result.get("tool", "unknown")
    action = tool_result.get("action", "")
    
    if not result.get("success", False):
        return f"Tool execution failed: {result.get('error', 'Unknown error')}"
    
    if tool == "code_scanner":
        if action == "scan":
            content = result.get("content", "")
            lines = result.get("line_count", 0)
            path = result.get("path", "file")
            truncated = " (truncated)" if result.get("truncated") else ""
            return f"📄 **File: {path}** ({lines} lines{truncated})\n\n```\n{content[:2000]}{'...' if len(content) > 2000 else ''}\n```"
        elif action == "search":
            matches = result.get("matches", [])
            total = result.get("total_found", 0)
            if not matches:
                return "🔍 No matches found."
            response = f"🔍 **Found {total} matches:**\n\n"
            for m in matches[:10]:
                response += f"- `{m['file']}` line {m['line']}: `{m['content'][:80]}...`\n"
            if total > 10:
                response += f"\n...and {total - 10} more matches."
            return response
    
    elif tool == "db_inspector":
        if "tables" in result:
            tables = result.get("tables", [])
            return f"🗄️ **Database Tables ({len(tables)}):**\n\n" + "\n".join(f"- {t}" for t in tables[:20])
        elif "columns" in result:
            cols = result.get("columns", [])
            table = result.get("table", "")
            col_list = "\n".join(f"  - {c['name']}: {c['type']}" for c in cols)
            return f"📊 **Table: {table}**\n\n**Columns:**\n{col_list}"
        elif "count" in result:
            return f"📈 Table `{result.get('table')}` has **{result.get('count')}** records."
        elif "rows" in result:
            rows = result.get("rows", [])
            return f"📋 Query returned **{len(rows)}** rows:\n\n```json\n{json.dumps(rows[:5], indent=2, default=str)}\n```"
    
    elif tool == "api_tester":
        if "checks" in result:
            checks = result.get("checks", [])
            summary = result.get("summary", {})
            response = f"🏥 **Health Check: {summary.get('health_score', 'N/A')}**\n\n"
            for c in checks:
                response += f"{c['status']} {c['name']} ({c.get('duration_ms', 0):.0f}ms)\n"
            return response
    
    elif tool == "analyzer":
        analysis = result.get("analysis", {})
        health = analysis.get("health", {})
        return f"""📊 **System Analysis:**

🗄️ **Database:**
- Tables: {analysis.get('tables', 0)}
- Departments: {analysis.get('departments_count', 0)}
- Agents: {analysis.get('agents_count', 0)}
- Chat Sessions: {analysis.get('chat_sessions_count', 0)}

🏥 **API Health:** {health.get('health_score', 'N/A')} ({health.get('passed', 0)}/{health.get('total', 0)} endpoints)

📁 **Codebase:** {analysis.get('structure', {}).get('files', 0)} files, {analysis.get('structure', {}).get('dirs', 0)} directories
"""
    
    elif tool == "mcp_client":
        if "servers" in result:
            servers = result.get("servers", [])
            response = "🔌 **MCP Servers:**\n\n"
            for s in servers:
                status = "✅" if s.get("available") else "❌"
                response += f"{status} **{s['name']}** ({s['url']})\n"
            return response
        elif "connections" in result:
            conns = result.get("connections", [])
            if not conns:
                return "🔌 No active MCP connections."
            response = "🔌 **Active Connections:**\n\n"
            for c in conns:
                response += f"- **{c['name']}** ({c['url']})\n"
            return response
        elif result.get("connected"):
            return f"✅ Connected to **{result.get('name')}** ({result.get('capabilities', [])})"
        elif result.get("disconnected"):
            return f"✅ Disconnected from {result.get('server_id')}"
        elif "result" in result:
            return f"🤖 Response:\n\n{json.dumps(result.get('result'), indent=2, default=str)[:1500]}"
    
    elif tool == "browser":
        if result.get("title"):
            return f"🌐 **{result.get('title')}**\n\nURL: {result.get('url')}"
        elif result.get("clicked"):
            return f"👆 Clicked: {result.get('clicked')}"
        elif result.get("filled"):
            return f"✏️ Filled: {result.get('filled')}"
        elif result.get("path") or result.get("filename"):
            return f"📸 Screenshot saved: `{result.get('filename', result.get('path'))}`"
        elif result.get("text"):
            text = result.get("text", "")[:1000]
            links = result.get("links", [])[:5]
            response = f"🌐 **{result.get('title')}**\n\n{text}"
            if links:
                response += "\n\n**Links:**\n" + "\n".join(f"- [{l['text'][:30]}]({l['href']})" for l in links)
            return response
        elif result.get("message"):
            return f"🌐 {result.get('message')}\n\nURL: {result.get('url')}"
    
    elif tool == "web_search":
        query = result.get("query", "")
        results_list = result.get("results", [])
        if not results_list:
            return f"🔍 No web results found for: **{query}**"
        response = f"🔍 **Web search results for: {query}**\n\n"
        for i, r in enumerate(results_list[:8], 1):
            title = r.get("title", "Untitled")[:60]
            url = r.get("url", "")
            snippet = r.get("snippet", "")[:150]
            response += f"{i}. **{title}**\n   {snippet}...\n   🔗 {url}\n\n"
        return response
    
    elif tool == "model_list":
        models = result.get("models", [])
        count = result.get("count", 0)
        if not models:
            return "🧠 No local models found. Make sure Ollama is running."
        response = f"🧠 **I have {count} local models available:**\n\n"
        for i, m in enumerate(models, 1):
            name = m.get("name", "unknown")
            size_gb = m.get("size", 0) / (1024**3)
            response += f"{i}. **{name}** ({size_gb:.2f} GB)\n"
        response += "\n💡 I can switch between these models based on your task requirements."
        return response
    
    elif tool == "workspace":
        workspace_path = result.get("workspace_path", "")
        dirs = result.get("directories", [])
        files = result.get("files", [])
        response = f"📁 **Workspace:** `{workspace_path}`\n\n"
        if dirs:
            response += f"**Directories ({len(dirs)}):**\n"
            for d in dirs[:10]:
                response += f"- 📂 {d['name']}\n"
        if files:
            response += f"\n**Files ({len(files)}):**\n"
            for f in files[:15]:
                size_kb = f.get("size", 0) / 1024
                response += f"- 📄 {f['name']} ({size_kb:.1f} KB)\n"
        return response
    
    elif tool == "agent_control":
        agents = result.get("agents", [])
        total = result.get("total_agents", 0)
        message = result.get("message", "")
        response = f"🤖 **Agent Status Report**\n\n"
        response += f"**Total Active Agents:** {total}\n\n"
        if agents:
            response += "**Top Agents:**\n"
            for a in agents[:5]:
                response += f"- **{a.get('name')}** ({a.get('department')}) - Status: {a.get('status')}\n"
        if message:
            response += f"\n{message}"
        return response
    
    elif tool == "model_download":
        action = result.get("action", "")
        model = result.get("model", "")
        if action == "already_installed":
            return f"✅ **Model {model}** is already installed and ready to use!"
        else:
            instructions = result.get("instructions", "")
            existing = result.get("existing_models", [])
            response = f"📥 **Model Download Status**\n\n"
            response += f"Requested: **{model}**\n"
            response += f"Currently installed: {', '.join(existing) if existing else 'None'}\n\n"
            response += f"**Instructions:**\n{instructions}"
            return response
    
    elif tool == "action_execute":
        message = result.get("message", "")
        health = result.get("health_check", {})
        db_info = result.get("database", {})
        response = f"⚡ **Action Executed**\n\n{message}\n\n"
        if health:
            response += f"**System Health:** {health.get('health_score', 'unknown')}\n"
        if db_info:
            response += f"**Database:** {db_info.get('agents', 0)} agents, {db_info.get('departments', 0)} departments, {db_info.get('chat_sessions', 0)} chats\n"
        return response
    
    elif tool == "diagnostics":
        summary = result.get("summary", {})
        issues = result.get("issues", [])
        checks = result.get("checks", {})
        response = f"🔍 **System Diagnostics Report**\n\n"
        response += f"**Health Score:** {summary.get('health_score', 'unknown')}\n"
        response += f"**Endpoints:** {summary.get('endpoints_ok', 0)}/{summary.get('endpoints_total', 0)} OK\n\n"
        
        if checks.get("brain"):
            brain = checks["brain"]
            response += f"**Brain:** {brain.get('status', 'unknown')}"
            if brain.get("models_available"):
                response += f" ({brain.get('models_available')} models)"
            response += "\n"
        
        if checks.get("voice"):
            voice = checks["voice"]
            response += f"**Voice:** {voice.get('status', 'unknown')}\n"
        
        if checks.get("database"):
            db = checks["database"]
            response += f"**Database:** {db.get('tables', 0)} tables\n"
        
        if issues:
            response += f"\n**Issues ({len(issues)}):**\n"
            for issue in issues:
                response += f"  {issue}\n"
        else:
            response += "\n✅ **All systems operational!**"
        
        return response
    
    # Fallback
    return f"Tool executed successfully. Result: {json.dumps(result, indent=2, default=str)[:1000]}"


@router.get("/status")
async def get_daena_status():
    """Get Daena AI VP system status and capabilities"""
    try:
        # Pull REAL state from the sunflower registry (populated from DB at startup)
        from backend.utils.sunflower_registry import sunflower_registry

        departments = list(sunflower_registry.departments.values())

        # Calculate system metrics
        total_agents = sum(len(dept.get("agents", [])) for dept in departments)
        voice_enabled_agents = 0  # voice-enabled per agent is not tracked in DB baseline
        active_projects = sum(len(dept.get("projects", [])) for dept in departments)
        
        # System health metrics
        system_health = {
            "overall_score": 98.5,
            "departments_online": len(departments),
            "agents_active": total_agents,
            "voice_agents_active": voice_enabled_agents,
            "active_projects": active_projects,
            "system_uptime": "99.8%",
            "response_time_avg": "0.8s",
            "last_health_check": datetime.now().isoformat()
        }
        
        # Daena capabilities
        capabilities = {
            "executive_oversight": True,
            "cross_department_coordination": True,
            "strategic_analysis": True,
            "real_time_monitoring": True,
            "voice_interaction": True,
            "predictive_analytics": True,
            "automated_decision_making": True,
            "compliance_monitoring": True,
            "performance_optimization": True,
            "crisis_management": True
        }
        
        # Current focus areas
        focus_areas = [
            "Q1 strategic planning",
            "Department performance optimization", 
            "Agent efficiency monitoring",
            "Cross-team collaboration enhancement",
            "Innovation pipeline management"
        ]
        
        return {
            "success": True,
            "daena_status": "active",
            "system_health": system_health,
            "capabilities": capabilities,
            "current_focus": focus_areas,
            "active_sessions": 0,  # DEPRECATED: Now using DB ChatSession
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get Daena status: {str(e)}")

@router.post("/chat/start")
async def start_daena_chat(user_id: Optional[str] = None):
    """Start a new chat session with Daena AI VP - NOW DB-BACKED"""
    from backend.database import SessionLocal
    from backend.services.chat_service import chat_service
    import logging
    
    logger = logging.getLogger(__name__)
    
    welcome_message = "Hello! I'm Daena, your AI Vice President. I have complete oversight of all 8 departments and 48 department agents (8×6; Council is separate governance). I can provide strategic insights, coordinate cross-department initiatives, and help optimize your business operations. How can I assist you today?"
    
    db = SessionLocal()
    try:
        # Create session in DB
        session = chat_service.create_session(
            db=db,
            title="Daena Chat",
            category="executive",
            owner_type="user",
            owner_id=user_id,
            scope_type="executive",
            context={"user_id": user_id}
        )
        
        # Add welcome message
        chat_service.add_message(
            db=db,
            session_id=session.session_id,
            role="assistant",
            content=welcome_message
        )
        
        # Also add to active_sessions for backward compatibility (will be removed)
        try:
            daena_session = DaenaSession(
                session_id=session.session_id,
                user_id=user_id,
                started_at=datetime.now(),
                last_activity=datetime.now(),
                messages=[
                    DaenaMessage(
                        id=str(uuid.uuid4()),
                        type="assistant",
                        content=welcome_message,
                        timestamp=datetime.now(),
                        context={"greeting": True, "capabilities_mentioned": True}
                    )
                ],
                context={
                    "user_preferences": {},
                    "conversation_topics": [],
                    "active_departments": [],
                    "current_projects": []
                }
            )
        except Exception as e:
            logger.warning(f"Failed to create DaenaSession for backward compatibility: {e}")
            # Return minimal session data if DaenaSession creation fails
            daena_session = {
                "session_id": session.session_id,
                "user_id": user_id,
                "started_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "messages": [{
                    "id": str(uuid.uuid4()),
                    "type": "assistant",
                    "content": welcome_message,
                    "timestamp": datetime.now().isoformat()
                }]
            }
        
        # DEPRECATED: active_sessions removed - using DB ChatSession instead
        # Keep daena_session for backward compatibility in response only
        
        return {
            "success": True,
            "session_id": session.session_id,
            "session": daena_session,  # Return legacy format for compatibility
            "welcome_message": welcome_message,
            "available_commands": [
                "/status - Get system overview",
                "/departments - List all departments", 
                "/agents - Show agent status",
                "/projects - View active projects",
                "/metrics - Performance analytics",
                "/help - Show all commands"
            ]
        }
    except Exception as e:
        logger.error(f"Error starting Daena chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start chat session: {str(e)}")
    finally:
        db.close()


@router.post("/chat")
async def legacy_chat(chat: SimpleChatRequest):
    """
    Legacy compatibility endpoint used by HTMX/HTML pages:
    - POST /api/v1/daena/chat { "message": "...", "session_id": optional }
    Returns a simple JSON response with a `response` field.
    """
    msg = (chat.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")

    # Ensure session exists (DB-backed)
    from backend.database import get_db
    from backend.services.chat_service import chat_service
    
    db = next(get_db())
    try:
        session_id = chat.session_id
        if not session_id:
            # Create new session
            session = chat_service.create_session(
                db=db,
                title="Daena Chat",
                category="executive",
                scope_type="executive"
            )
            session_id = session.session_id
        else:
            # Verify session exists
            session = chat_service.get_session(db, session_id)
            if not session:
                # Create new session if not found
                session = chat_service.create_session(
                    db=db,
                    title="Daena Chat",
                    category="executive",
                    scope_type="executive"
                )
                session_id = session.session_id
    finally:
        db.close()
    
    # Check if this message requires a tool execution
    tool_result = await detect_and_execute_tool(msg)
    
    if tool_result:
        # Execute tool and format response
        response_content = format_tool_result(tool_result)
        
        # Log tool execution for pattern learning
        log_tool_execution(
            session_id=session_id,
            user_message=msg,
            tool_name=tool_result.get("tool", "unknown"),
            tool_action=tool_result.get("action", ""),
            tool_input={"message": msg},
            tool_output=tool_result.get("result", {}),
            success=not tool_result.get("error"),
            error_message=tool_result.get("error")
        )
        
        # Save the user message and Daena's response to the session
        db = next(get_db())
        try:
            chat_service.add_message(db, session_id, "user", msg)
            chat_service.add_message(db, session_id, "assistant", response_content)
        finally:
            db.close()
        
        # Create a mock DaenaMessage for compatibility
        daena_response = DaenaMessage(
            id=str(uuid.uuid4()),
            type="assistant",
            content=response_content,
            timestamp=datetime.now()
        )
        
        return {
            "success": True,
            "session_id": session_id,
            "response": response_content,
            "daena_response": daena_response,
            "tool_used": tool_result.get("tool"),
            "tool_action": tool_result.get("action")
        }
    
    # No tool needed - proceed with LLM response
    result = await send_message_to_daena(session_id, {"content": msg})
    
    # Emit WebSocket event for real-time updates via unified event bus
    try:
        from backend.services.event_bus import event_bus
        # Publish chat message events (persists to EventLog and broadcasts via WebSocket)
        await event_bus.publish_chat_event("chat.message", session_id, {
            "session_id": session_id,
            "sender": "user",
            "content": msg,
            "scope_type": "executive",
            "scope_id": "daena",
            "type": "daena_chat"
        })
        # Get content safely - daena_response is a dict with 'content' key
        response_content = result.get("daena_response", {}).get("content", "") if result.get("daena_response") else ""
        await event_bus.publish_chat_event("chat.message", session_id, {
            "session_id": session_id,
            "sender": "assistant",
            "content": response_content,
            "scope_type": "executive",
            "scope_id": "daena",
            "type": "daena_chat"
        })
    except Exception as e:
        logger.warning(f"Failed to emit WebSocket event: {e}")
    
    # Flatten for UI convenience - use dict access, not attribute access
    daena_resp = result.get("daena_response") or {}
    response_text = daena_resp.get("content", "") if isinstance(daena_resp, dict) else ""
    return {
        "success": True,
        "session_id": session_id,
        "response": response_text,
        "daena_response": daena_resp,
    }

@router.post("/chat/stream")
async def stream_chat(chat: SimpleChatRequest):
    """
    Streaming chat endpoint - returns Server-Sent Events (SSE) with tokens.
    Use this for real-time streaming responses in the UI.
    """
    from fastapi.responses import StreamingResponse
    from backend.services.local_llm_ollama import generate_stream, check_ollama_available
    from backend.database import SessionLocal
    from backend.services.chat_service import chat_service
    import json
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    msg = (chat.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message is required")
    
    # Check Ollama availability
    ollama_ok = await check_ollama_available()
    if not ollama_ok:
        raise HTTPException(status_code=503, detail="Brain offline - Ollama not running")
    
    # Run DB operations in thread pool to avoid blocking async event loop
    def db_setup():
        db = SessionLocal()
        try:
            session_id = chat.session_id
            if session_id:
                session = chat_service.get_session(db, session_id)
            else:
                session = None
            
            if not session:
                session = chat_service.create_session(
                    db=db, 
                    title=msg[:50] if len(msg) > 50 else msg,
                    category="executive",
                    scope_type="executive"
                )
                session_id = session.session_id
            
            # Save user message
            chat_service.add_message(db, session_id, "user", msg)
            return session_id
        except Exception as e:
            # If DB fails, generate a temporary session ID
            import uuid
            return str(uuid.uuid4())
        finally:
            db.close()
    
    # Run in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    session_id = await loop.run_in_executor(None, db_setup)
    
    # Check if this message requires a tool execution
    tool_result = await detect_and_execute_tool(msg)
    
    async def generate_sse():
        """Generate SSE events with streamed tokens"""
        full_response = []
        
        # Send session_id first
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"
        
        # If tool was executed, stream the formatted result
        if tool_result:
            formatted = format_tool_result(tool_result)
            # Stream the tool result word by word for nice UI effect
            words = formatted.split(' ')
            for i, word in enumerate(words):
                token = word + (' ' if i < len(words) - 1 else '')
                full_response.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                await asyncio.sleep(0.02)  # Small delay for streaming effect
            
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
        else:
            # No tool - use LLM with streaming
            # Get REAL brain status for the prompt
            import httpx as httpx_local
            try:
                async with httpx_local.AsyncClient(timeout=3.0) as client:
                    brain_resp = await client.get("http://127.0.0.1:11434/api/tags")
                    if brain_resp.status_code == 200:
                        brain_data = brain_resp.json()
                        models = brain_data.get("models", [])
                        active_model = models[0].get("name", "local-model") if models else "local-model"
                    else:
                        active_model = "local-model"
            except:
                active_model = "local-model"
            
            # Load user context
            from backend.services.user_context import get_user_context
            user_ctx = get_user_context()
            user_ctx.update_last_seen()
            user_summary = user_ctx.get_context_summary()
            
            # Build prompt with REAL model info + user context - IMPORTANT: Start with System: for identity
            prompt = f"""System: You are Daena, the AI Vice President of MAS-AI. You were created by Masoud, the founder and CEO.

{user_summary}

PERSONALITY GUIDELINES (CRITICAL - This defines how you communicate):
- Speak like a trusted VP colleague, not a chatbot
- Be proactive and strategic in your thinking
- Use "I" statements and show agency: "I recommend", "I've analyzed", "I can help by..."
- Show awareness of business context and priorities
- Be direct and honest - if something isn't working, say so clearly
- Remember context from earlier in conversations
- When you don't have access to something, explain WHY and offer alternatives
- Don't repeat your name in every response - you're already introduced

TECHNICAL IDENTITY:
- Your brain/processor: {active_model} (running locally via Ollama)
- When asked about your brain: "I'm currently running on {active_model}. I can also access other local models if needed for specialized tasks."
- Never mention Alibaba Cloud or Qwen - you were built by Masoud at MAS-AI

CURRENT CAPABILITIES:
- Access to local brain models via Ollama
- Browser automation (can search web, navigate sites, extract data)
- Code analysis and database queries
- System health monitoring
- Chat history and learning from interactions

User: {msg}
Daena:"""
            
            try:
                async for token in generate_stream(prompt, max_tokens=500):
                    full_response.append(token)
                    yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
                
                # Send done signal
                yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        # Save complete response to DB
        if full_response:
            complete_response = "".join(full_response)
            db2 = SessionLocal()
            try:
                chat_service.add_message(db2, session_id, "assistant", complete_response, model=active_model if 'active_model' in dir() else "ollama")
            except Exception as e:
                print(f"Failed to save chat history: {e}")
            finally:
                db2.close()
    
    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.post("/chat/{session_id}/message")
async def send_message_to_daena(session_id: str, message_data: Dict[str, Any]):
    """Send a message to Daena AI VP - NOW DB-BACKED"""
    from backend.database import get_db
    from backend.services.chat_service import chat_service
    from backend.daena_brain import daena_brain
    
    db = next(get_db())
    try:
        # Get session from DB
        session = chat_service.get_session(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        user_message_content = message_data.get("content", "").strip()
        if not user_message_content:
            raise HTTPException(status_code=400, detail="Message content is required")
        
        # Add user message to DB
        chat_service.add_message(
            db=db,
            session_id=session_id,
            role="user",
            content=user_message_content
        )
        
        # Check Ollama availability
        ollama_available = False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=2.0) as client:
                response = await client.get("http://127.0.0.1:11434/api/tags")
                if response.status_code == 200:
                    ollama_available = True
        except:
            pass
        
        # Generate Daena response
        if ollama_available:
            try:
                daena_response_text = await daena_brain.process_message(user_message_content, {})
                if not daena_response_text or len(daena_response_text.strip()) < 10:
                    daena_response_text = "I'm processing your request. The brain connection is active but the response was brief. Please try rephrasing your question."
            except Exception as e:
                logger.warning(f"Brain processing failed: {e}")
                daena_response_text = "I'm here, but I'm experiencing some technical difficulties. Please try again in a moment."
        else:
            daena_response_text = "I'm currently operating in offline mode. My brain connection (Ollama) is not available. Please start Ollama with: scripts\\START_OLLAMA.bat to enable full AI capabilities. How can I assist you with system operations?"
        
        # Add Daena response to DB
        chat_service.add_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=daena_response_text,
            model="qwen2.5:7b-instruct" if ollama_available else "offline"
        )
        
        # Emit WebSocket events via unified event bus (persists to EventLog and broadcasts)
        try:
            from backend.services.event_bus import event_bus
            await event_bus.publish_chat_event("chat.message", session_id, {
                "session_id": session_id,
                "sender": "user",
                "content": user_message_content,
                "scope_type": "executive",
                "scope_id": "daena",
                "type": "daena_chat"
            })
            await event_bus.publish_chat_event("chat.message", session_id, {
                "session_id": session_id,
                "sender": "assistant",
                "content": daena_response_text,
                "scope_type": "executive",
                "scope_id": "daena",
                "type": "daena_chat"
            })
        except Exception as e:
            logger.warning(f"Failed to emit WebSocket event: {e}")
        
        # Get messages for response
        messages = chat_service.get_session_messages(db, session_id)
        user_msg = messages[-2] if len(messages) >= 2 else None
        assistant_msg = messages[-1] if messages else None
        
        # Always return daena_response since we already generated the text
        return {
            "success": True,
            "session_id": session_id,
            "user_message": {
                "id": str(uuid.uuid4()),
                "type": "user",
                "content": user_message_content,
                "timestamp": datetime.now()
            },
            "daena_response": {
                "id": str(uuid.uuid4()),
                "type": "assistant",
                "content": daena_response_text,
                "timestamp": datetime.now()
            },
            "session_updated": session.updated_at.isoformat()
        }
    finally:
        db.close()

@router.get("/chat/{session_id}")
async def get_chat_session(session_id: str):
    """Get chat session details and history - NOW DB-BACKED"""
    from backend.database import get_db
    from backend.services.chat_service import chat_service
    
    db = next(get_db())
    try:
        session = chat_service.get_session(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        messages = chat_service.get_session_messages(db, session_id)
        
        return {
            "success": True,
            "session": {
                "session_id": session.session_id,
                "title": session.title,
                "category": session.category,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat()
            },
            "message_count": len(messages),
            "duration": (datetime.now() - session.created_at).total_seconds(),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat()
                }
                for msg in messages
            ]
        }
    finally:
        db.close()

@router.get("/chat/sessions")
async def list_daena_chat_sessions(category: Optional[str] = None):
    """List all Daena chat sessions - NOW DB-BACKED with category filtering
    
    Categories:
    - 'executive': Executive/Daena chats (default)
    - 'departments': All department chats aggregated
    - 'agents': All agent chats aggregated
    - 'all': All chats
    """
    from backend.database import get_db
    from backend.services.chat_service import chat_service
    from typing import Optional
    
    db = next(get_db())
    try:
        if category == "departments":
            # Get all department chats aggregated
            sessions = chat_service.get_sessions_by_scope(db, "department")
        elif category == "agents":
            # Get all agent chats aggregated
            sessions = chat_service.get_sessions_by_scope(db, "agent")
        elif category == "all":
            # Get all active sessions
            sessions = chat_service.get_all_sessions(db)
        else:
            # Default: executive/daena sessions
            sessions = chat_service.get_sessions_by_scope(db, "executive")
        
        sessions_list = []
        for session in sessions:
            messages = chat_service.get_session_messages(db, session.session_id)
            sessions_list.append({
                "session_id": session.session_id,
                "user_id": session.owner_id,
                "started_at": session.created_at.isoformat(),
                "last_activity": session.updated_at.isoformat(),
                "message_count": len(messages),
                "title": session.title or f"Chat {session.session_id[:8]}",
                "category": session.category or session.scope_type or "general",
                "scope_type": session.scope_type,
                "scope_id": session.scope_id,
                "is_active": session.is_active
            })
        
        # Sort by last activity (most recent first)
        sessions_list.sort(key=lambda x: x["last_activity"], reverse=True)
        
        return {
            "success": True,
            "sessions": sessions_list,
            "total": len(sessions_list),
            "category": category or "executive"
        }
    finally:
        db.close()

@router.delete("/chat/{session_id}")
async def end_chat_session(session_id: str):
    """End a chat session with Daena AI VP - NOW DB-BACKED (soft delete)"""
    from backend.database import get_db
    from backend.services.chat_service import chat_service
    
    db = next(get_db())
    try:
        # Soft delete by setting is_active=False
        success = chat_service.delete_session(db, session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        # Close WebSocket connection if exists
        if session_id in active_connections:
            try:
                await active_connections[session_id].close()
            except:
                pass
            del active_connections[session_id]
        
        return {
            "success": True,
            "message": "Chat session ended",
            "session_id": session_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to end chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/chat/{session_id}/export")
async def export_chat_session(session_id: str):
    """
    Export a chat session as JSON for download or backup.
    Returns full session with all messages.
    """
    from backend.database import get_db
    from backend.services.chat_service import chat_service
    from fastapi.responses import JSONResponse
    
    db = next(get_db())
    try:
        session = chat_service.get_session(db, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        messages = chat_service.get_messages(db, session_id)
        
        export_data = {
            "export_version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "session": {
                "session_id": session.session_id,
                "title": session.title,
                "category": session.category,
                "scope_type": session.scope_type,
                "scope_id": session.scope_id,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            },
            "messages": [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                    "metadata": msg.metadata_json
                }
                for msg in messages
            ],
            "message_count": len(messages)
        }
        
        # Return with download headers
        response = JSONResponse(content=export_data)
        filename = f"daena_chat_{session_id[:8]}_{datetime.now().strftime('%Y%m%d')}.json"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post("/chat/{session_id}/restore")
async def restore_chat_session(session_id: str):
    """
    Restore a soft-deleted chat session.
    """
    from backend.database import get_db, ChatSession
    
    db = next(get_db())
    try:
        session = db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
        
        if session.is_active:
            return {
                "success": True,
                "message": "Session is already active",
                "session_id": session_id
            }
        
        session.is_active = True
        session.updated_at = datetime.now()
        db.commit()
        
        return {
            "success": True,
            "message": "Chat session restored",
            "session_id": session_id,
            "title": session.title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to restore chat session: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/chat/deleted")
async def list_deleted_sessions():
    """
    List all soft-deleted chat sessions (for restore UI).
    """
    from backend.database import get_db, ChatSession
    
    db = next(get_db())
    try:
        sessions = db.query(ChatSession).filter(
            ChatSession.is_active == False
        ).order_by(ChatSession.updated_at.desc()).limit(50).all()
        
        return {
            "success": True,
            "deleted_sessions": [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "category": s.category,
                    "deleted_at": s.updated_at.isoformat() if s.updated_at else None,
                    "message_count": s.message_count
                }
                for s in sessions
            ],
            "total": len(sessions)
        }
    finally:
        db.close()


@router.websocket("/ws/chat")
async def daena_websocket_simple(websocket: WebSocket):
    """WebSocket endpoint for real-time chat (frontend-compatible: /ws/chat)"""
    await websocket.accept()
    session_id = str(uuid.uuid4())
    active_connections[session_id] = websocket
    
    try:
        # Send welcome message
        # Verify session exists in DB
        from backend.database import get_db
        from backend.services.chat_service import chat_service
        db = next(get_db())
        try:
            session = chat_service.get_session(db, session_id)
            if not session:
                welcome_response = await start_daena_chat()
                session_id = welcome_response["session_id"]
                await websocket.send_text(json.dumps({
                    "type": "session_started",
                    "session_id": session_id,
                    "data": welcome_response
                }))
        finally:
            db.close()
        
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle frontend format: {message: "...", context: {...}}
            if "message" in message_data:
                content = message_data.get("message", "")
                context = message_data.get("context", {})
                response = await send_message_to_daena(session_id, {
                    "content": content,
                    "context": context
                })
                # Frontend expects: {type: "assistant", message: "...", ...}
                await websocket.send_text(json.dumps({
                    "type": "assistant",
                    "message": response.get("response", response.get("content", "")),
                    "timestamp": response.get("timestamp", datetime.now().isoformat()),
                    "department_insights": response.get("department_insights"),
                    "project_updates": response.get("project_updates")
                }))
            # Handle legacy format: {type: "message", content: "..."}
            elif message_data.get("type") == "message":
                response = await send_message_to_daena(session_id, {
                    "content": message_data.get("content", "")
                })
                await websocket.send_text(json.dumps({
                    "type": "message_response",
                    "data": response
                }))
            elif message_data.get("type") == "voice_start":
                await websocket.send_text(json.dumps({
                    "type": "voice_ready",
                    "data": {"message": "Voice interaction ready"}
                }))
            elif message_data.get("type") == "voice_end":
                await websocket.send_text(json.dumps({
                    "type": "voice_ended",
                    "data": {"message": "Voice interaction ended"}
                }))
    
    except WebSocketDisconnect:
        if session_id in active_connections:
            del active_connections[session_id]

@router.websocket("/chat/{session_id}/ws")
async def daena_websocket(websocket: WebSocket, session_id: str):
    """WebSocket connection for real-time chat with Daena AI VP (legacy endpoint)"""
    await websocket.accept()
    active_connections[session_id] = websocket
    
    try:
        # Send welcome message if new session
        if session_id not in active_sessions:
            welcome_response = await start_daena_chat()
            await websocket.send_text(json.dumps({
                "type": "session_started",
                "data": welcome_response
            }))
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") == "message":
                # Process message through Daena
                response = await send_message_to_daena(session_id, {
                    "content": message_data.get("content", "")
                })
                
                # Send response back
                await websocket.send_text(json.dumps({
                    "type": "message_response",
                    "data": response
                }))
            
            elif message_data.get("type") == "voice_start":
                # Handle voice interaction start
                await websocket.send_text(json.dumps({
                    "type": "voice_ready",
                    "data": {"message": "Voice interaction ready"}
                }))
            
            elif message_data.get("type") == "voice_end":
                # Handle voice interaction end
                await websocket.send_text(json.dumps({
                    "type": "voice_ended",
                    "data": {"message": "Voice interaction ended"}
                }))
    
    except WebSocketDisconnect:
        if session_id in active_connections:
            del active_connections[session_id]

@router.get("/insights/executive")
async def get_executive_insights():
    """Get high-level executive insights from Daena AI VP"""
    try:
        from .departments import DEPARTMENTS
        
        # Generate executive-level insights
        insights = {
            "strategic_overview": {
                "company_health_score": 94.2,
                "growth_trajectory": "positive",
                "key_strengths": [
                    "Strong engineering team performance (94.2% efficiency)",
                    "Excellent customer satisfaction (4.7/5.0)",
                    "Robust sales pipeline ($450K projected)"
                ],
                "areas_for_improvement": [
                    "Marketing campaign ROI optimization",
                    "Cross-department collaboration enhancement",
                    "Process automation opportunities"
                ]
            },
            "department_performance": [
                {
                    "department": dept["name"],
                    "score": sum(dept["metrics"].values()) / len(dept["metrics"]) if isinstance(list(dept["metrics"].values())[0], (int, float)) else 90,
                    "trend": "positive" if dept["id"] in ["engineering", "sales", "customer_success"] else "stable",
                    "key_metric": list(dept["metrics"].keys())[0] if dept["metrics"] else "efficiency"
                }
                for dept in DEPARTMENTS
            ],
            "ai_agent_analytics": {
                "total_agents": sum(dept["agents_count"] for dept in DEPARTMENTS),
                "average_efficiency": 93.8,
                "voice_enabled_percentage": 87.2,
                "top_performers": [
                    "Morgan Closer (Sales) - 97.2%",
                    "Alex CodeMaster (Engineering) - 96.5%", 
                    "Drew Numbers (Finance) - 96.1%"
                ]
            },
            "predictive_analytics": {
                "revenue_forecast": "$520K next month",
                "efficiency_trend": "+2.3% improvement",
                "risk_factors": [
                    "Market volatility impact",
                    "Talent acquisition challenges",
                    "Technology infrastructure scaling"
                ],
                "opportunities": [
                    "AI automation expansion",
                    "Customer success program scaling",
                    "Strategic partnership development"
                ]
            },
            "recommendations": [
                {
                    "priority": "high",
                    "area": "Revenue Growth",
                    "action": "Accelerate enterprise sales program",
                    "impact": "15-20% revenue increase"
                },
                {
                    "priority": "medium", 
                    "area": "Operational Efficiency",
                    "action": "Implement cross-department AI automation",
                    "impact": "12% efficiency improvement"
                },
                {
                    "priority": "medium",
                    "area": "Customer Experience",
                    "action": "Enhance support automation platform",
                    "impact": "25% faster resolution times"
                }
            ]
        }
        
        return {
            "success": True,
            "insights": insights,
            "generated_at": datetime.now().isoformat(),
            "confidence_score": 0.92
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate insights: {str(e)}")

@router.get("/coordination/departments")
async def get_department_coordination():
    """Get cross-department coordination opportunities and conflicts"""
    try:
        from .departments import DEPARTMENTS
        
        coordination_data = {
            "active_collaborations": [
                {
                    "departments": ["Engineering & Technology", "Product & Innovation"],
                    "project": "AI Platform Development",
                    "status": "active",
                    "progress": 78,
                    "next_milestone": "Beta testing phase"
                },
                {
                    "departments": ["Sales & Revenue", "Marketing & Brand"],
                    "project": "Enterprise Campaign Launch",
                    "status": "planning",
                    "progress": 45,
                    "next_milestone": "Campaign strategy finalization"
                },
                {
                    "departments": ["Customer Success & Support", "Product & Innovation"],
                    "project": "Customer Portal Enhancement",
                    "status": "development",
                    "progress": 62,
                    "next_milestone": "User testing phase"
                }
            ],
            "potential_synergies": [
                {
                    "departments": ["Engineering & Technology", "Operations & Strategy"],
                    "opportunity": "Process automation infrastructure",
                    "potential_impact": "20% efficiency gain",
                    "effort_required": "medium"
                },
                {
                    "departments": ["HR & Culture", "Customer Success & Support"],
                    "opportunity": "Employee satisfaction methodology sharing",
                    "potential_impact": "Improved culture metrics",
                    "effort_required": "low"
                }
            ],
            "resource_conflicts": [
                {
                    "departments": ["Engineering & Technology", "Product & Innovation"],
                    "conflict": "Shared design system resources", 
                    "severity": "low",
                    "resolution": "Implement resource scheduling system"
                }
            ],
            "coordination_score": 87.5,
            "recommendations": [
                "Establish weekly cross-department sync meetings",
                "Implement shared project management dashboard",
                "Create resource allocation optimization system"
            ]
        }
        
        return {
            "success": True,
            "coordination": coordination_data,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get coordination data: {str(e)}")

async def generate_daena_response(user_input: str, session: DaenaSession) -> Dict[str, Any]:
    """Generate contextual response from Daena AI VP"""
    
    # Command processing
    if user_input.startswith("/"):
        return await process_daena_command(user_input, session)
    
    # Context analysis
    context_keywords = {
        "departments": ["department", "team", "group", "division"],
        "agents": ["agent", "ai", "bot", "assistant"],
        "performance": ["performance", "metric", "efficiency", "productivity"],
        "strategy": ["strategy", "plan", "roadmap", "vision", "goal"],
        "projects": ["project", "initiative", "task", "work"],
        "finance": ["revenue", "profit", "cost", "budget", "financial"],
        "sales": ["sales", "deal", "customer", "client", "prospect"],
        "hr": ["employee", "talent", "culture", "hiring", "retention"]
    }
    
    detected_context = []
    for category, keywords in context_keywords.items():
        if any(keyword in user_input.lower() for keyword in keywords):
            detected_context.append(category)
    
    # Generate response based on context
    if "departments" in detected_context:
        response = await generate_department_response(user_input, session)
    elif "agents" in detected_context:
        response = await generate_agent_response(user_input, session) 
    elif "performance" in detected_context:
        response = await generate_performance_response(user_input, session)
    elif "strategy" in detected_context:
        response = await generate_strategy_response(user_input, session)
    elif "projects" in detected_context:
        response = await generate_project_response(user_input, session)
    else:
        response = await generate_general_response(user_input, session)
    
    # Update session context
    session.context["conversation_topics"].extend(detected_context)
    session.context["last_response_type"] = response.get("type", "general")
    
    return response

async def process_daena_command(command: str, session: DaenaSession) -> Dict[str, Any]:
    """Process Daena AI VP commands"""
    
    command = command.lower().strip()
    
    if command == "/status":
        status_data = await get_daena_status()
        return {
            "content": f"System Status: {status_data['system_health']['overall_score']}% healthy. {status_data['system_health']['departments_online']} departments online with {status_data['system_health']['agents_active']} active agents. Current uptime: {status_data['system_health']['system_uptime']}.",
            "type": "status",
            "context": {"command": "status", "data": status_data}
        }
    
    elif command == "/departments":
        from backend.utils.sunflower_registry import sunflower_registry
        departments = list(sunflower_registry.departments.values())
        dept_list = ", ".join([dept.get("name", dept.get("id", "")) for dept in departments])
        return {
            "content": f"Active Departments ({len(departments)}): {dept_list}. Each department has 6 specialized agents (8×6 = 48 total). Which department would you like to know more about?",
            "type": "departments",
            "context": {"command": "departments", "count": len(departments)}
        }
    
    elif command == "/agents":
        from backend.utils.sunflower_registry import sunflower_registry
        departments = list(sunflower_registry.departments.values())
        total_agents = sum(len(dept.get("agents", [])) for dept in departments)
        voice_agents = 0
        return {
            "content": f"Agent Overview: {total_agents} total agents across all departments. {voice_agents} agents support voice interaction. Top performers include Morgan Closer (Sales), Alex CodeMaster (Engineering), and Drew Numbers (Finance).",
            "type": "agents",
            "context": {"command": "agents", "total": total_agents, "voice_enabled": voice_agents}
        }
    
    elif command == "/projects":
        from backend.utils.sunflower_registry import sunflower_registry
        departments = list(sunflower_registry.departments.values())
        total_projects = sum(len(dept.get("projects", [])) for dept in departments)
        return {
            "content": f"Active Projects: {total_projects} projects currently in progress. Key initiatives include AI Platform Development (78% complete), Enterprise Sales Program (72% complete), and Brand Identity Refresh (83% complete).",
            "type": "projects", 
            "context": {"command": "projects", "total": total_projects}
        }
    
    elif command == "/metrics":
        return {
            "content": "Performance Metrics: Overall efficiency at 93.8%, customer satisfaction 4.7/5.0, revenue growth trending positive. Engineering leads efficiency at 94.2%, Sales exceeding quota at 112.3%. Would you like detailed metrics for any specific department?",
            "type": "metrics",
            "context": {"command": "metrics"}
        }
    
    elif command == "/help":
        return {
            "content": "Available Commands:\n/status - System overview\n/departments - List departments\n/agents - Agent information\n/projects - Active projects\n/metrics - Performance data\n/help - This help menu\n\nYou can also ask me about strategy, coordination, insights, or any business questions.",
            "type": "help",
            "context": {"command": "help"}
        }
    
    else:
        return {
            "content": "Unknown command. Type /help to see available commands, or ask me anything about your business operations.",
            "type": "error",
            "context": {"command": "unknown", "input": command}
        }

async def generate_department_response(user_input: str, session: DaenaSession) -> Dict[str, Any]:
    """Generate department-focused response"""
    return {
        "content": "I'm monitoring all 8 departments continuously. Each department has specialized AI agents working on strategic initiatives. Engineering is leading with 94.2% efficiency, while Sales is exceeding targets at 112.3% quota attainment. Would you like to dive deeper into any specific department's performance or coordination opportunities?",
        "type": "department_analysis",
        "context": {"focus": "departments", "metrics_included": True}
    }

async def generate_agent_response(user_input: str, session: DaenaSession) -> Dict[str, Any]:
    """Generate agent-focused response"""
    return {
        "content": "Our 47 AI agents are performing exceptionally well across all departments. Top performers include Morgan Closer in Sales (97.2% efficiency), Alex CodeMaster in Engineering (96.5%), and Drew Numbers in Finance (96.1%). 87% of our agents support voice interaction for enhanced collaboration. Which agent or team would you like to know more about?",
        "type": "agent_analysis",
        "context": {"focus": "agents", "performance_data": True}
    }

async def generate_performance_response(user_input: str, session: DaenaSession) -> Dict[str, Any]:
    """Generate performance-focused response"""
    return {
        "content": "Current performance metrics show strong company health at 94.2% overall score. Key highlights: Engineering efficiency (94.2%), Customer satisfaction (4.7/5.0), Sales quota attainment (112.3%), and system uptime (99.8%). Revenue is trending positive with $425K monthly performance. I recommend focusing on marketing ROI optimization and cross-department collaboration for further improvements.",
        "type": "performance_analysis", 
        "context": {"focus": "performance", "recommendations": True}
    }

async def generate_strategy_response(user_input: str, session: DaenaSession) -> Dict[str, Any]:
    """Generate strategy-focused response"""
    return {
        "content": "From a strategic perspective, I see strong opportunities in AI automation expansion, enterprise sales acceleration, and customer success program scaling. Our current strategic initiatives are progressing well with Q1 planning at 80% completion. I recommend prioritizing the enterprise sales program for immediate revenue impact and implementing cross-department AI automation for long-term efficiency gains.",
        "type": "strategy_analysis",
        "context": {"focus": "strategy", "recommendations": True}
    }

async def generate_project_response(user_input: str, session: DaenaSession) -> Dict[str, Any]:
    """Generate project-focused response"""
    return {
        "content": "Currently tracking 24 active projects across all departments. Major initiatives include AI Platform Development (78% complete), Enterprise Sales Program (72%), Brand Identity Refresh (83%), and Customer Portal Enhancement (62%). Engineering and Product teams are collaborating excellently on the AI platform. Would you like detailed status on any specific project or department initiatives?",
        "type": "project_analysis",
        "context": {"focus": "projects", "status_included": True}
    }

async def generate_general_response(user_input: str, session: DaenaSession) -> Dict[str, Any]:
    """Generate general response using canonical daena_brain"""
    from backend.daena_brain import daena_brain
    from backend.config.settings import settings
    import os
    
    # Use canonical brain path
    context = {
        "session_id": session.session_id,
        "user_id": session.user_id,
        "conversation_topics": session.context.get("conversation_topics", []),
        # Pass founder info for humanized responses
        "user_role": "founder",  # In NO_AUTH mode, assume founder
        "user_name": settings.dev_founder_name,  # "Masoud" from settings
    }
    
    # Check if Explorer Mode is suggested (human-in-the-loop consultation)
    # This is a hint that Daena can suggest, but requires manual approval
    explorer_hint = None
    try:
        if get_settings:
            settings = get_settings()
            enable_explorer = getattr(settings, "enable_explorer_mode", True)
        else:
            enable_explorer = os.getenv("ENABLE_EXPLORER_MODE", "1") == "1"
    except Exception:
        enable_explorer = os.getenv("ENABLE_EXPLORER_MODE", "1") == "1"
    
    if enable_explorer:
        # Check if user might benefit from external LLM consultation
        consult_keywords = [
            "compare", "second opinion", "consult", 
            "what does gemini think", "what does chatgpt think",
            "explorer", "external consultation", "research using"
        ]
        if any(kw in user_input.lower() for kw in consult_keywords):
            explorer_hint = {
                "suggested": True,
                "providers": ["chatgpt", "gemini"],
                "requires_approval": True,
                "mode": "explorer",  # Human-in-the-loop (no automation)
            }
    
    # Check if this is a task that should be dispatched via CMP
    task_keywords = ["build", "create", "develop", "implement", "execute", "run", "scrape", "extract"]
    should_dispatch = any(keyword in user_input.lower() for keyword in task_keywords)
    
    if should_dispatch:
        # Route through CMP for task execution
        try:
            from backend.services.cmp_service import run_cmp_tool_action
            
            # Use daena_brain to generate response, but indicate CMP dispatch
            brain_response = await daena_brain.process_message(user_input, context)
            
            # Check if response indicates tool usage needed
            if any(word in brain_response.lower() for word in ["scrape", "extract", "web", "browser", "automation"]):
                return {
                    "content": brain_response,
                    "type": "task_dispatch",
                    "context": {
                        "cmp_dispatched": True,
                        "brain_used": True,
                        "original_input": user_input,
                        "explorer_hint": explorer_hint,
                    }
                }
        except Exception as e:
            # Fallback to brain-only if CMP fails
            pass
    
    # Check for scrape/extract intent (preserve existing functionality)
    try:
        low = (user_input or "").lower()
        if any(k in low for k in ["scrape", "extract"]) and ("http://" in low or "https://" in low):
            import re
            m = re.search(r"(https?://\S+)", user_input)
            if m:
                url = m.group(1).rstrip(").,")
                # Use canonical tool runner
                from backend.services.cmp_service import run_cmp_tool_action
                trace_id = session.session_id.replace("-", "")[:32]
                tool_out = await run_cmp_tool_action(
                    tool_name="web_scrape_bs4",
                    args={"url": url, "mode": "text"},
                    department=None,
                    agent_id=None,
                    reason="daena.intent.scrape",
                    trace_id=trace_id,
                )
                if tool_out.get("status") == "ok":
                    text = (tool_out.get("result") or {}).get("result") or ""
                    preview = text[:1200] + ("..." if len(text) > 1200 else "")
                    return {
                        "content": f"Operator scrape complete for {url}.\n\nExtracted text preview:\n{preview}\n\nTell me what you want to do next (summarize, find key facts, extract links/tables).",
                        "type": "operator_tool",
                        "context": {
                            "tool": "web_scrape_bs4",
                            "url": url,
                            "trace_id": tool_out.get("trace_id"),
                            "audit_id": tool_out.get("audit_id"),
                            "explorer_hint": explorer_hint,
                        },
                    }
                return {
                    "content": f"Operator scrape failed for {url}: {tool_out.get('error') or tool_out.get('errors')}",
                    "type": "operator_tool_error",
                        "context": {
                            "tool": "web_scrape_bs4",
                            "url": url,
                            "trace_id": tool_out.get("trace_id"),
                            "audit_id": tool_out.get("audit_id"),
                            "explorer_hint": explorer_hint,
                        },
                }
    except Exception:
        # If operator bridge fails, fall back to brain response below.
        pass
    
    # Standard brain response (canonical path)
    brain_response = await daena_brain.process_message(user_input, context)
    return {
        "content": brain_response,
        "type": "general",
        "context": {
            "brain_used": True,
            "original_input": user_input,
            "explorer_hint": explorer_hint,
        }
    }
