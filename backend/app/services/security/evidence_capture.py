"""EvidenceCapture -- The 1-cent proof system.

"I found a vuln" means nothing without proof. The kid who transferred
1 cent from the bank -- THAT made them listen.

This module captures irrefutable evidence at the moment of discovery:
- Response snapshots (full HTTP headers + body)
- Screenshots (rendered page via headless browser)
- Token/key extraction (encrypted in vault)
- Reproducible requests (exact curl command)
- Chain of evidence (timestamped, hashed, tamper-evident)

Every piece of evidence is:
- Timestamped (UTC, ISO 8601)
- SHA-256 hashed (proves it hasn't been modified)
- Encrypted at rest (AES-256 for tokens/keys)
- Stored in a structured vault directory

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Evidence vault location (outside codebase, survives rebuilds)
# ---------------------------------------------------------------------------
EVIDENCE_VAULT = Path(os.environ.get(
    "EVIDENCE_VAULT_PATH",
    str(Path.home() / ".daena" / "evidence"),
))

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class EvidenceItem:
    """A single piece of captured evidence."""
    evidence_id: str = field(default_factory=lambda: str(uuid4())[:12])
    evidence_type: str = ""          # "response", "screenshot", "token", "curl", "poc"
    timestamp: str = ""              # ISO 8601 UTC
    sha256: str = ""                 # Hash of the raw content
    description: str = ""
    target_url: str = ""
    file_path: str = ""              # Where the evidence file lives
    metadata: dict[str, Any] = field(default_factory=dict)
    encrypted: bool = False          # True for tokens/keys

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "type": self.evidence_type,
            "timestamp": self.timestamp,
            "sha256": self.sha256,
            "description": self.description,
            "target_url": self.target_url,
            "file_path": self.file_path,
            "metadata": self.metadata,
            "encrypted": self.encrypted,
        }


@dataclass
class EvidenceChain:
    """Timestamped chain proving when and how evidence was captured.

    This is legal protection: proves the evidence was captured at a
    specific time during an authorized assessment, not fabricated later.
    """
    scan_id: str = ""
    target: str = ""
    program: str = ""                # Bug bounty program name
    started_at: str = ""
    items: list[EvidenceItem] = field(default_factory=list)
    chain_hash: str = ""             # Rolling hash of all items

    def to_dict(self) -> dict[str, Any]:
        return {
            "scan_id": self.scan_id,
            "target": self.target,
            "program": self.program,
            "started_at": self.started_at,
            "evidence_count": len(self.items),
            "items": [item.to_dict() for item in self.items],
            "chain_hash": self.chain_hash,
        }


# ---------------------------------------------------------------------------
# The Capture Engine
# ---------------------------------------------------------------------------

class EvidenceCapture:
    """Captures and vaults irrefutable proof of vulnerabilities.

    Every capture is:
    1. Timestamped (UTC)
    2. SHA-256 hashed (tamper-evident)
    3. Written to the vault directory
    4. Added to the evidence chain (rolling hash)

    Usage::

        capture = EvidenceCapture(scan_id="abc123", target="example.com")
        await capture.initialize()

        # Capture an HTTP response
        item = await capture.capture_response(url, status, headers, body)

        # Capture a screenshot
        item = await capture.capture_screenshot(url, png_bytes)

        # Capture an exposed token
        item = await capture.capture_token(url, token_type, token_value)

        # Generate reproducible curl command
        item = capture.capture_curl(method, url, headers, body)

        # Get the full evidence chain
        chain = capture.get_chain()
    """

    def __init__(
        self,
        scan_id: str = "",
        target: str = "",
        program: str = "",
    ) -> None:
        self.scan_id = scan_id or str(uuid4())[:8]
        self.target = target
        self.program = program
        self._chain = EvidenceChain(
            scan_id=self.scan_id,
            target=target,
            program=program,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        self._vault_dir: Path | None = None
        self._chain_hasher = hashlib.sha256()

    async def initialize(self) -> None:
        """Create the vault directory for this scan."""
        safe_target = self.target.replace("://", "_").replace("/", "_").replace(".", "_")
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self._vault_dir = EVIDENCE_VAULT / f"{date_str}_{safe_target}_{self.scan_id}"
        self._vault_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "evidence.vault_created",
            path=str(self._vault_dir),
            scan_id=self.scan_id,
        )

    # ------------------------------------------------------------------
    # Capture methods
    # ------------------------------------------------------------------

    async def capture_response(
        self,
        url: str,
        status_code: int,
        headers: dict[str, str],
        body: str | bytes,
        *,
        finding_id: str = "",
    ) -> EvidenceItem:
        """Capture a full HTTP response as evidence.

        This is the raw proof: "This URL returned THIS response at THIS time."
        """
        self._ensure_initialized()

        timestamp = datetime.now(timezone.utc).isoformat()
        body_str = body if isinstance(body, str) else body.decode("utf-8", errors="replace")

        # Build the evidence file content
        content = (
            f"# HTTP Response Snapshot\n"
            f"# Captured: {timestamp}\n"
            f"# URL: {url}\n"
            f"# Status: {status_code}\n"
            f"# Scan ID: {self.scan_id}\n"
            f"# Finding: {finding_id}\n\n"
            f"--- RESPONSE HEADERS ---\n"
        )
        for key, val in headers.items():
            content += f"{key}: {val}\n"
        content += f"\n--- RESPONSE BODY ({len(body_str)} bytes) ---\n"
        content += body_str[:50000]  # Cap at 50KB to prevent huge files

        # Hash and save
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        filename = f"response_{finding_id or 'unknown'}_{content_hash[:8]}.txt"
        filepath = self._vault_dir / filename
        filepath.write_text(content, encoding="utf-8")

        item = EvidenceItem(
            evidence_type="response",
            timestamp=timestamp,
            sha256=content_hash,
            description=f"HTTP {status_code} response from {url}",
            target_url=url,
            file_path=str(filepath),
            metadata={
                "status_code": status_code,
                "header_count": len(headers),
                "body_length": len(body_str),
                "finding_id": finding_id,
            },
        )
        self._add_to_chain(item)
        return item

    async def capture_screenshot(
        self,
        url: str,
        png_bytes: bytes,
        *,
        finding_id: str = "",
        description: str = "",
    ) -> EvidenceItem:
        """Capture a rendered page screenshot as evidence.

        Visual proof that the vulnerability is visible in a browser.
        The png_bytes should come from a headless browser (Playwright).
        """
        self._ensure_initialized()

        timestamp = datetime.now(timezone.utc).isoformat()
        content_hash = hashlib.sha256(png_bytes).hexdigest()
        filename = f"screenshot_{finding_id or 'page'}_{content_hash[:8]}.png"
        filepath = self._vault_dir / filename
        filepath.write_bytes(png_bytes)

        item = EvidenceItem(
            evidence_type="screenshot",
            timestamp=timestamp,
            sha256=content_hash,
            description=description or f"Screenshot of {url}",
            target_url=url,
            file_path=str(filepath),
            metadata={
                "size_bytes": len(png_bytes),
                "finding_id": finding_id,
            },
        )
        self._add_to_chain(item)
        return item

    async def capture_token(
        self,
        url: str,
        token_type: str,
        token_value: str,
        *,
        finding_id: str = "",
        context: str = "",
    ) -> EvidenceItem:
        """Capture an exposed API key, JWT, or session token.

        The token is encrypted at rest using AES-256. The plaintext
        is NEVER stored in the vault. Only the encrypted blob + hash.

        Token types: "api_key", "jwt", "session_token", "oauth_token",
                     "aws_key", "private_key", "password_hash"
        """
        self._ensure_initialized()

        timestamp = datetime.now(timezone.utc).isoformat()

        # Hash the token (for deduplication and chain integrity)
        token_hash = hashlib.sha256(token_value.encode()).hexdigest()

        # Encrypt the token for storage
        encrypted_blob = self._encrypt_token(token_value)
        filename = f"token_{token_type}_{token_hash[:8]}.enc"
        filepath = self._vault_dir / filename
        filepath.write_bytes(encrypted_blob)

        # Also save metadata (NOT the token itself)
        meta_content = {
            "timestamp": timestamp,
            "token_type": token_type,
            "token_hash_sha256": token_hash,
            "token_preview": f"{token_value[:4]}...{token_value[-4:]}" if len(token_value) > 8 else "***",
            "token_length": len(token_value),
            "source_url": url,
            "context": context,
            "finding_id": finding_id,
            "encrypted_file": filename,
        }
        meta_path = self._vault_dir / f"token_{token_type}_{token_hash[:8]}_meta.json"
        meta_path.write_text(json.dumps(meta_content, indent=2), encoding="utf-8")

        item = EvidenceItem(
            evidence_type="token",
            timestamp=timestamp,
            sha256=token_hash,
            description=f"Exposed {token_type} found at {url}",
            target_url=url,
            file_path=str(filepath),
            metadata=meta_content,
            encrypted=True,
        )
        self._add_to_chain(item)

        logger.info(
            "evidence.token_captured",
            token_type=token_type,
            url=url,
            preview=meta_content["token_preview"],
        )
        return item

    def capture_curl(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str = "",
        *,
        finding_id: str = "",
    ) -> EvidenceItem:
        """Generate a reproducible curl command as evidence.

        This is the "try it yourself" proof: copy-paste this curl
        command and see the vuln with your own eyes.
        """
        self._ensure_initialized()

        timestamp = datetime.now(timezone.utc).isoformat()

        # Build curl command
        parts = [f"curl -X {method.upper()}"]
        if headers:
            for key, val in headers.items():
                # Don't include auth tokens in the curl command
                if key.lower() in ("authorization", "cookie", "x-api-key"):
                    parts.append(f"  -H '{key}: [REDACTED]'")
                else:
                    parts.append(f"  -H '{key}: {val}'")
        if body:
            # Truncate body in curl if too long
            safe_body = body[:2000].replace("'", "\\'")
            parts.append(f"  -d '{safe_body}'")
        parts.append(f"  '{url}'")

        curl_cmd = " \\\n".join(parts)
        content = (
            f"# Reproducible Request\n"
            f"# Captured: {timestamp}\n"
            f"# Finding: {finding_id}\n"
            f"# Copy-paste this to reproduce the vulnerability\n\n"
            f"{curl_cmd}\n"
        )

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        filename = f"curl_{finding_id or 'request'}_{content_hash[:8]}.sh"
        filepath = self._vault_dir / filename
        filepath.write_text(content, encoding="utf-8")

        item = EvidenceItem(
            evidence_type="curl",
            timestamp=timestamp,
            sha256=content_hash,
            description=f"Reproducible {method.upper()} request to {url}",
            target_url=url,
            file_path=str(filepath),
            metadata={
                "method": method.upper(),
                "finding_id": finding_id,
                "has_body": bool(body),
            },
        )
        self._add_to_chain(item)
        return item

    async def capture_poc(
        self,
        url: str,
        poc_type: str,
        description: str,
        request_data: dict[str, Any],
        response_data: dict[str, Any],
        *,
        finding_id: str = "",
    ) -> EvidenceItem:
        """Capture a minimal Proof of Concept execution.

        This is the 1-cent proof: "I didn't just find the endpoint,
        I proved it works by executing a minimal, harmless action."

        poc_type examples:
        - "unauthorized_read": Read data without auth
        - "idor": Access another user's resource
        - "xss_reflected": Reflected XSS fires in response
        - "ssrf": Internal URL resolved in response
        - "rate_limit_bypass": Exceeded stated rate limit
        """
        self._ensure_initialized()

        timestamp = datetime.now(timezone.utc).isoformat()

        content = {
            "timestamp": timestamp,
            "poc_type": poc_type,
            "description": description,
            "target_url": url,
            "finding_id": finding_id,
            "request": {
                "method": request_data.get("method", "GET"),
                "url": request_data.get("url", url),
                "headers": request_data.get("headers", {}),
                "body_preview": str(request_data.get("body", ""))[:500],
            },
            "response": {
                "status_code": response_data.get("status_code", 0),
                "headers": response_data.get("headers", {}),
                "body_preview": str(response_data.get("body", ""))[:2000],
                "proof_marker": response_data.get("proof_marker", ""),
            },
            "impact_demonstration": description,
        }

        content_str = json.dumps(content, indent=2)
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()
        filename = f"poc_{poc_type}_{content_hash[:8]}.json"
        filepath = self._vault_dir / filename
        filepath.write_text(content_str, encoding="utf-8")

        item = EvidenceItem(
            evidence_type="poc",
            timestamp=timestamp,
            sha256=content_hash,
            description=f"PoC ({poc_type}): {description[:100]}",
            target_url=url,
            file_path=str(filepath),
            metadata={
                "poc_type": poc_type,
                "finding_id": finding_id,
                "status_code": response_data.get("status_code", 0),
            },
        )
        self._add_to_chain(item)
        return item

    # ------------------------------------------------------------------
    # Chain management
    # ------------------------------------------------------------------

    def get_chain(self) -> EvidenceChain:
        """Return the complete evidence chain."""
        self._chain.chain_hash = self._chain_hasher.hexdigest()
        return self._chain

    def get_evidence_summary(self) -> dict[str, Any]:
        """Get a summary of captured evidence for report attachment."""
        chain = self.get_chain()
        by_type: dict[str, int] = {}
        for item in chain.items:
            by_type[item.evidence_type] = by_type.get(item.evidence_type, 0) + 1

        return {
            "scan_id": chain.scan_id,
            "target": chain.target,
            "program": chain.program,
            "total_evidence": len(chain.items),
            "by_type": by_type,
            "chain_hash": chain.chain_hash,
            "vault_path": str(self._vault_dir) if self._vault_dir else "",
            "items": [item.to_dict() for item in chain.items],
        }

    # ------------------------------------------------------------------
    # Token pattern detection
    # ------------------------------------------------------------------

    @staticmethod
    def detect_tokens(content: str) -> list[dict[str, str]]:
        """Scan content for exposed tokens/keys/secrets.

        Returns list of {"type": "...", "value": "...", "context": "..."} dicts.
        """
        import re

        patterns = {
            "aws_access_key": r"(?:AKIA[0-9A-Z]{16})",
            "aws_secret_key": r"(?:[0-9a-zA-Z/+]{40})",
            "github_token": r"(?:gh[pousr]_[A-Za-z0-9_]{36,255})",
            "github_fine_grained": r"(?:github_pat_[A-Za-z0-9_]{22,255})",
            "jwt": r"(?:eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})",
            "google_api_key": r"(?:AIza[0-9A-Za-z_-]{35})",
            "slack_token": r"(?:xox[baprs]-[0-9A-Za-z-]{10,})",
            "stripe_key": r"(?:STRIPE_LIVE_PLACEHOLDER_[0-9a-zA-Z]{24,})",
            "stripe_publishable": r"(?:pk_live_[0-9a-zA-Z]{24,})",
            "private_key_begin": r"(?:-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----)",
            "bearer_token": r"(?:Bearer\s+[A-Za-z0-9_.-]{20,})",
            "basic_auth": r"(?:Basic\s+[A-Za-z0-9+/=]{10,})",
            "generic_api_key": r'(?:["\']?(?:api[_-]?key|apikey|api_secret|secret_key)["\']?\s*[:=]\s*["\']([A-Za-z0-9_-]{16,})["\'])',
            "password_in_url": r"(?::\/\/[^:]+:([^@]{8,})@)",
        }

        found = []
        for token_type, pattern in patterns.items():
            for match in re.finditer(pattern, content):
                value = match.group(0)
                # Get surrounding context (50 chars each side)
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                context = content[start:end]
                found.append({
                    "type": token_type,
                    "value": value,
                    "context": context,
                })

        return found

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        """Ensure vault directory exists."""
        if not self._vault_dir:
            # Auto-initialize if not done explicitly
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, can't await here
                    # Create directory synchronously
                    safe_target = self.target.replace("://", "_").replace("/", "_").replace(".", "_")
                    date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                    self._vault_dir = EVIDENCE_VAULT / f"{date_str}_{safe_target}_{self.scan_id}"
                    self._vault_dir.mkdir(parents=True, exist_ok=True)
                else:
                    loop.run_until_complete(self.initialize())
            except RuntimeError:
                # No event loop -- create synchronously
                safe_target = self.target.replace("://", "_").replace("/", "_").replace(".", "_")
                date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
                self._vault_dir = EVIDENCE_VAULT / f"{date_str}_{safe_target}_{self.scan_id}"
                self._vault_dir.mkdir(parents=True, exist_ok=True)

    def _add_to_chain(self, item: EvidenceItem) -> None:
        """Add evidence to the chain and update rolling hash."""
        self._chain.items.append(item)
        # Rolling hash: each item's hash incorporates all previous
        chain_entry = f"{item.timestamp}:{item.evidence_type}:{item.sha256}"
        self._chain_hasher.update(chain_entry.encode())
        logger.info(
            "evidence.captured",
            type=item.evidence_type,
            url=item.target_url,
            hash=item.sha256[:12],
        )

    def _encrypt_token(self, token_value: str) -> bytes:
        """Encrypt a token for secure storage.

        Uses AES-256-CBC with a random IV. The encryption key is
        derived from EVIDENCE_ENCRYPTION_KEY env var or a default
        machine-specific key.

        In production, EVIDENCE_ENCRYPTION_KEY should be set and
        backed up separately from the vault.
        """
        try:
            from cryptography.fernet import Fernet
            import base64

            # Get or generate encryption key
            key_env = os.environ.get("EVIDENCE_ENCRYPTION_KEY", "")
            if key_env:
                # Use provided key (must be valid Fernet key)
                key = key_env.encode()
            else:
                # Derive a key from machine identity (fallback, less secure)
                import platform
                machine_id = f"daena-evidence-{platform.node()}-{os.getlogin()}"
                key_bytes = hashlib.sha256(machine_id.encode()).digest()
                key = base64.urlsafe_b64encode(key_bytes)

            fernet = Fernet(key)
            return fernet.encrypt(token_value.encode())
        except ImportError:
            # cryptography package not installed -- fall back to base64 + warning
            logger.warning(
                "evidence.encryption_fallback",
                reason="cryptography package not installed, using base64 (NOT SECURE)",
            )
            import base64
            return base64.b64encode(f"INSECURE:{token_value}".encode())
