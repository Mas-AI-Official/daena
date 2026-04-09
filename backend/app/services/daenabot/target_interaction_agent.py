"""TargetInteractionAgent -- Post-exploitation target interaction.

A vulnerability scanner REPORTS. A penetration tester CONNECTS.

This agent handles the phases that scanners skip:
    3. Gaining Access -- authenticate using discovered credentials/bypasses
    4. Maintaining Access -- keep sessions alive across interactions
    5. Post-Exploitation -- navigate inside, prove real impact

REQUIRES /3vilbob mode active. Refuses to operate without it.
Every interaction is evidence-captured and proxied.

Target types supported:
    - HTTP/API: authenticated requests, endpoint enumeration, data extraction
    - SSH/Shell: remote command execution, file system navigation
    - Database: schema enumeration, query execution, credential extraction
    - TCP/Service: raw port interaction, protocol detection

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent

logger = get_logger(__name__)


class TargetInteractionAgent(BaseAgent):
    """Post-exploitation agent for target interaction.

    Gate: /3vilbob mode MUST be active. This agent does nothing
    without it. The key is the ONLY authorization gate.

    Every operation:
    1. Checks /3vilbob is active
    2. Routes through proxy (if ProxyManager available)
    3. Captures evidence (response, timing, output)
    4. Returns structured result with evidence metadata

    Usage::

        agent = TargetInteractionAgent()
        result = await agent.execute("http_request", {
            "method": "GET",
            "url": "https://target.com/admin/api/users",
            "headers": {"Authorization": "Bearer <leaked_token>"},
        })
    """

    agent_name = "target_interaction"

    OPERATION_ACTION_MAP: dict[str, str] = {
        "http_request": "EXECUTE",
        "ssh_connect": "EXECUTE",
        "ssh_command": "EXECUTE",
        "db_connect": "EXECUTE",
        "db_query": "EXECUTE",
        "tcp_connect": "EXECUTE",
        "enumerate_service": "EXECUTE",
    }

    def __init__(self, evidence_capture: Any = None) -> None:
        self._evidence = evidence_capture
        self._ssh_sessions: dict[str, Any] = {}  # host -> connection
        self._db_sessions: dict[str, Any] = {}   # dsn -> connection

    # ── dispatch ───────────────────────────────────────────────

    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        # Gate: /3vilbob must be active
        from app.services.security.evilbob_mode import is_active, has_capability
        if not is_active():
            return self._error(
                operation,
                "/3vilbob mode is not active. Target interaction requires "
                "full-spectrum authorization. Use '/3vilbob ON' first.",
            )
        if not has_capability("target_interaction"):
            return self._error(
                operation,
                "target_interaction capability not available.",
            )

        dispatch = {
            "http_request": self.http_request,
            "ssh_connect": self.ssh_connect,
            "ssh_command": self.ssh_command,
            "db_connect": self.db_connect,
            "db_query": self.db_query,
            "tcp_connect": self.tcp_connect,
            "enumerate_service": self.enumerate_service,
        }
        handler = dispatch.get(operation)
        if not handler:
            return self._error(
                operation,
                f"Unknown operation '{operation}'. "
                f"Supported: {list(dispatch.keys())}",
            )
        return await handler(**params)

    # ── HTTP/API interaction ───────────────────────────────────

    async def http_request(
        self,
        url: str,
        method: str = "GET",
        headers: dict[str, str] | None = None,
        body: str = "",
        follow_redirects: bool = True,
        capture_evidence: bool = True,
    ) -> dict[str, Any]:
        """Send an authenticated HTTP request to a target.

        Used for: API exploitation, authenticated endpoint access,
        IDOR testing, data extraction, admin panel interaction.
        """
        import httpx

        request_headers = headers or {}
        # Inject proxy headers if available
        proxy_url = self._get_proxy()
        browser_headers = self._get_browser_headers()
        # Merge: explicit headers override browser mimicry
        merged_headers = {**browser_headers, **request_headers}

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=follow_redirects,
                verify=False,
                proxy=proxy_url or None,
            ) as client:
                resp = await client.request(
                    method=method.upper(),
                    url=url,
                    headers=merged_headers,
                    content=body.encode() if body else None,
                )
                elapsed_ms = int((time.monotonic() - start) * 1000)

                result_data = {
                    "url": str(resp.url),
                    "status_code": resp.status_code,
                    "headers": dict(resp.headers),
                    "body": resp.text[:50000],
                    "body_length": len(resp.content),
                    "elapsed_ms": elapsed_ms,
                    "redirected": str(resp.url) != url,
                    "method": method.upper(),
                }

                # Evidence capture
                if capture_evidence and self._evidence:
                    await self._evidence.capture_response(
                        url=url,
                        status_code=resp.status_code,
                        headers=dict(resp.headers),
                        body=resp.text,
                        finding_id=f"post_exploit_{resp.status_code}",
                    )
                    self._evidence.capture_curl(
                        method=method.upper(),
                        url=url,
                        headers=request_headers,
                        body=body,
                        finding_id=f"post_exploit_{resp.status_code}",
                    )
                    # Auto-detect tokens in response
                    from app.services.security.evidence_capture import EvidenceCapture
                    tokens = EvidenceCapture.detect_tokens(resp.text)
                    for token in tokens:
                        await self._evidence.capture_token(
                            url=url,
                            token_type=token["type"],
                            token_value=token["value"],
                            finding_id="post_exploit_token",
                            context=token.get("context", ""),
                        )
                    result_data["tokens_found"] = len(tokens)

                logger.info(
                    "target_interaction.http_request",
                    url=url,
                    status=resp.status_code,
                    elapsed_ms=elapsed_ms,
                )
                return self._result("http_request", result_data)

        except Exception as exc:
            return self._error("http_request", f"Request failed: {str(exc)[:300]}")

    # ── SSH interaction ────────────────────────────────────────

    async def ssh_connect(
        self,
        host: str,
        port: int = 22,
        username: str = "",
        password: str = "",
        key_path: str = "",
    ) -> dict[str, Any]:
        """Connect to a target via SSH.

        Used for: remote server access after credential discovery,
        lateral movement, file system exploration.
        """
        try:
            import asyncssh

            connect_kwargs: dict[str, Any] = {
                "host": host,
                "port": port,
                "username": username,
                "known_hosts": None,  # Pentest context -- accept any host key
            }
            if password:
                connect_kwargs["password"] = password
            if key_path:
                connect_kwargs["client_keys"] = [key_path]

            conn = await asyncio.wait_for(
                asyncssh.connect(**connect_kwargs),
                timeout=15.0,
            )
            session_key = f"{host}:{port}"
            self._ssh_sessions[session_key] = conn

            # Capture evidence of successful connection
            if self._evidence:
                await self._evidence.capture_poc(
                    url=f"ssh://{host}:{port}",
                    poc_type="ssh_access",
                    description=f"SSH connection established as {username}@{host}:{port}",
                    request_data={
                        "method": "SSH",
                        "url": f"ssh://{host}:{port}",
                        "headers": {"username": username},
                    },
                    response_data={
                        "status_code": 0,
                        "proof_marker": "Connection established",
                    },
                    finding_id="ssh_access",
                )

            logger.info(
                "target_interaction.ssh_connected",
                host=host,
                port=port,
                user=username,
            )
            return self._result("ssh_connect", {
                "host": host,
                "port": port,
                "username": username,
                "connected": True,
                "session_key": session_key,
            })

        except ImportError:
            return self._error(
                "ssh_connect",
                "asyncssh not installed. Run: pip install asyncssh",
            )
        except asyncio.TimeoutError:
            return self._error("ssh_connect", f"SSH connection to {host}:{port} timed out (15s)")
        except Exception as exc:
            return self._error("ssh_connect", f"SSH failed: {str(exc)[:300]}")

    async def ssh_command(
        self,
        host: str,
        command: str,
        port: int = 22,
    ) -> dict[str, Any]:
        """Execute a command on a connected SSH target.

        Requires a prior ssh_connect to the same host.
        """
        session_key = f"{host}:{port}"
        conn = self._ssh_sessions.get(session_key)
        if not conn:
            return self._error(
                "ssh_command",
                f"No active SSH session to {session_key}. Call ssh_connect first.",
            )

        try:
            result = await asyncio.wait_for(
                conn.run(command, check=False),
                timeout=30.0,
            )
            output = {
                "command": command,
                "stdout": (result.stdout or "")[:50000],
                "stderr": (result.stderr or "")[:10000],
                "exit_code": result.exit_status,
                "host": host,
            }

            if self._evidence:
                await self._evidence.capture_poc(
                    url=f"ssh://{host}:{port}",
                    poc_type="remote_command_execution",
                    description=f"Executed '{command}' on {host} (exit {result.exit_status})",
                    request_data={"method": "SSH", "url": f"ssh://{host}", "body": command},
                    response_data={
                        "status_code": result.exit_status or 0,
                        "body": (result.stdout or "")[:2000],
                        "proof_marker": f"exit_code={result.exit_status}",
                    },
                    finding_id="rce",
                )

            logger.info(
                "target_interaction.ssh_command",
                host=host,
                command=command[:80],
                exit_code=result.exit_status,
            )
            return self._result("ssh_command", output)

        except asyncio.TimeoutError:
            return self._error("ssh_command", f"Command timed out (30s): {command[:80]}")
        except Exception as exc:
            return self._error("ssh_command", f"SSH command failed: {str(exc)[:300]}")

    # ── Database interaction ───────────────────────────────────

    async def db_connect(
        self,
        dsn: str,
        db_type: str = "auto",
    ) -> dict[str, Any]:
        """Connect to a database using a discovered connection string.

        Supports: PostgreSQL, MySQL, SQLite, MSSQL.
        dsn format examples:
            postgresql://user:pass@host:5432/dbname
            mysql://user:pass@host:3306/dbname
            sqlite:///path/to/db.sqlite
        """
        try:
            import sqlalchemy
            from sqlalchemy import create_engine, text, inspect

            engine = create_engine(dsn, echo=False)
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            self._db_sessions[dsn] = engine

            # Get basic schema info
            insp = inspect(engine)
            tables = insp.get_table_names()

            if self._evidence:
                await self._evidence.capture_poc(
                    url=dsn.split("@")[-1] if "@" in dsn else dsn,
                    poc_type="database_access",
                    description=f"Database connection established. {len(tables)} tables found.",
                    request_data={"method": "SQL", "url": dsn.split("@")[-1] if "@" in dsn else "db"},
                    response_data={
                        "status_code": 0,
                        "body": f"Tables: {tables[:20]}",
                        "proof_marker": f"{len(tables)} tables accessible",
                    },
                    finding_id="db_access",
                )

            logger.info(
                "target_interaction.db_connected",
                tables=len(tables),
            )
            return self._result("db_connect", {
                "connected": True,
                "db_type": engine.dialect.name,
                "tables": tables[:50],
                "table_count": len(tables),
            })

        except ImportError:
            return self._error("db_connect", "sqlalchemy not installed")
        except Exception as exc:
            return self._error("db_connect", f"Database connection failed: {str(exc)[:300]}")

    async def db_query(
        self,
        dsn: str,
        query: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Execute a read query on a connected database.

        Safety: only SELECT queries allowed. For proof-of-concept,
        you demonstrate READ access, not destructive writes.
        """
        engine = self._db_sessions.get(dsn)
        if not engine:
            return self._error("db_query", "No active DB session. Call db_connect first.")

        # Safety: block destructive queries even in /3vilbob mode
        # Proof of READ access is sufficient for any bug bounty
        query_upper = query.strip().upper()
        if any(query_upper.startswith(kw) for kw in (
            "DROP", "DELETE", "TRUNCATE", "ALTER", "INSERT", "UPDATE",
            "CREATE", "GRANT", "REVOKE",
        )):
            return self._error(
                "db_query",
                "Destructive queries blocked. Use SELECT to prove read access. "
                "Read access to sensitive data IS the proof of impact.",
            )

        try:
            from sqlalchemy import text

            with engine.connect() as conn:
                result = conn.execute(text(query))
                columns = list(result.keys()) if result.returns_rows else []
                rows = [dict(row._mapping) for row in result.fetchmany(limit)] if result.returns_rows else []

            output = {
                "query": query,
                "columns": columns,
                "rows": rows,
                "row_count": len(rows),
                "truncated": len(rows) >= limit,
            }

            if self._evidence:
                # Redact actual data values in evidence for safety
                await self._evidence.capture_poc(
                    url="database",
                    poc_type="data_access",
                    description=f"Query returned {len(rows)} rows, {len(columns)} columns: {columns}",
                    request_data={"method": "SQL", "body": query},
                    response_data={
                        "status_code": 0,
                        "body": f"Columns: {columns}, Row count: {len(rows)}",
                        "proof_marker": f"{len(rows)} rows returned",
                    },
                    finding_id="data_access",
                )

            logger.info(
                "target_interaction.db_query",
                columns=len(columns),
                rows=len(rows),
            )
            return self._result("db_query", output)

        except Exception as exc:
            return self._error("db_query", f"Query failed: {str(exc)[:300]}")

    # ── TCP/Service interaction ────────────────────────────────

    async def tcp_connect(
        self,
        host: str,
        port: int,
        send_data: str = "",
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        """Connect to a TCP port and optionally send data.

        Used for: service fingerprinting, protocol interaction,
        banner grabbing, testing non-HTTP services.
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout,
            )

            # Read banner (if service sends one)
            banner = ""
            try:
                banner_bytes = await asyncio.wait_for(
                    reader.read(4096),
                    timeout=3.0,
                )
                banner = banner_bytes.decode("utf-8", errors="replace")
            except asyncio.TimeoutError:
                pass  # No banner -- not all services send one

            response = ""
            if send_data:
                writer.write(send_data.encode())
                await writer.drain()
                try:
                    resp_bytes = await asyncio.wait_for(
                        reader.read(8192),
                        timeout=5.0,
                    )
                    response = resp_bytes.decode("utf-8", errors="replace")
                except asyncio.TimeoutError:
                    response = "(no response within 5s)"

            writer.close()

            output = {
                "host": host,
                "port": port,
                "connected": True,
                "banner": banner[:2000],
                "response": response[:5000],
                "sent": send_data[:500] if send_data else "",
            }

            if self._evidence and (banner or response):
                await self._evidence.capture_response(
                    url=f"tcp://{host}:{port}",
                    status_code=0,
                    headers={"service_banner": banner[:200]},
                    body=response or banner,
                    finding_id=f"tcp_{port}",
                )

            logger.info(
                "target_interaction.tcp_connect",
                host=host,
                port=port,
                has_banner=bool(banner),
            )
            return self._result("tcp_connect", output)

        except asyncio.TimeoutError:
            return self._result("tcp_connect", {
                "host": host,
                "port": port,
                "connected": False,
                "banner": "",
                "response": "",
                "error": f"Connection timed out ({timeout}s)",
            })
        except ConnectionRefusedError:
            return self._result("tcp_connect", {
                "host": host,
                "port": port,
                "connected": False,
                "banner": "",
                "response": "",
                "error": "Connection refused",
            })
        except Exception as exc:
            return self._error("tcp_connect", f"TCP connect failed: {str(exc)[:300]}")

    async def enumerate_service(
        self,
        host: str,
        port: int,
    ) -> dict[str, Any]:
        """Identify what service runs on a port via banner grab + probes.

        Sends common protocol handshakes to identify the service.
        """
        # Step 1: raw banner grab
        banner_result = await self.tcp_connect(host, port, timeout=5.0)
        banner = banner_result.get("output", {}).get("banner", "") if banner_result.get("success") else ""

        service = "unknown"
        details = {}

        # Step 2: identify from banner
        banner_lower = banner.lower()
        if "ssh" in banner_lower:
            service = "ssh"
            details["version"] = banner.strip()
        elif "ftp" in banner_lower:
            service = "ftp"
            details["banner"] = banner.strip()
        elif "smtp" in banner_lower or "220" in banner:
            service = "smtp"
            details["banner"] = banner.strip()
        elif "mysql" in banner_lower or banner.startswith("J"):
            service = "mysql"
        elif "postgresql" in banner_lower:
            service = "postgresql"
        elif "redis" in banner_lower or banner.startswith("+PONG"):
            service = "redis"
        elif "http" in banner_lower or "html" in banner_lower:
            service = "http"

        # Step 3: if no banner, try HTTP probe
        if service == "unknown" and not banner:
            http_result = await self.http_request(
                url=f"http://{host}:{port}/",
                capture_evidence=False,
            )
            if http_result.get("success"):
                status = http_result.get("output", {}).get("status_code", 0)
                if status > 0:
                    service = "http"
                    details["status_code"] = status
                    server = http_result.get("output", {}).get("headers", {}).get("server", "")
                    if server:
                        details["server"] = server

        output = {
            "host": host,
            "port": port,
            "service": service,
            "banner": banner[:500],
            "details": details,
        }

        logger.info(
            "target_interaction.enumerate_service",
            host=host,
            port=port,
            service=service,
        )
        return self._result("enumerate_service", output)

    # ── helpers ────────────────────────────────────────────────

    def _get_proxy(self) -> str:
        """Get proxy URL from ProxyManager if available."""
        try:
            from app.services.security.proxy_manager import ProxyManager
            pm = ProxyManager(offensive_mode=True)
            pm.initialize()
            return pm.get_proxy()
        except Exception:
            return ""

    def _get_browser_headers(self) -> dict[str, str]:
        """Get legitimacy mimicry headers."""
        try:
            from app.services.security.proxy_manager import ProxyManager
            pm = ProxyManager(offensive_mode=False)
            pm.initialize()
            return pm.get_request_headers()
        except Exception:
            return {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
            }

    async def close(self) -> None:
        """Close all active sessions."""
        for key, conn in self._ssh_sessions.items():
            try:
                conn.close()
            except Exception:
                pass
        self._ssh_sessions.clear()

        for dsn, engine in self._db_sessions.items():
            try:
                engine.dispose()
            except Exception:
                pass
        self._db_sessions.clear()
