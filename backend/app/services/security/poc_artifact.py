"""Proof-of-Concept artifact model for Klyntar findings.

Every OPERATOR-tier (and above) Klyntar finding must carry a
reproducible artifact that a human can use to verify the bug exists
and to replay the exploit in a controlled environment. This module
defines the artifact shape and the helpers that build typed
artifacts from scan-phase observations.

Shannon Lite coined the "no exploit, no report" discipline. Klyntar
goes further: every artifact is SHA-256 hashed, stored in the
EvidenceCapture vault, linked into the EvidenceChain so tampering
breaks the chain, and surfaced inline in OPERATOR+ reports so
bug-bounty submissions can be copy-pasted.

Artifact kinds intentionally cover non-web threats too:
    * ``curl``              classic web-app PoC (safe to replay)
    * ``http_pair``         request + response transcript
    * ``screenshot``        PNG/JPG, typically from headless browser
    * ``replay_script``     bash/Python replay, always sandboxed
    * ``package_reference`` supply-chain: pkg name + version + hash
                            (NEVER executable; pointer-only for
                            npm/pypi/crate/maven artifacts)
    * ``diff_hunk``         source-code pattern showing the bug
    * ``behavioral_trace``  syscall/network trace summary (not the
                            raw trace; a fingerprint)

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class PocKind(str, Enum):
    """Typed artifact kinds. Each kind has its own safety profile."""
    CURL = "curl"
    HTTP_PAIR = "http_pair"
    SCREENSHOT = "screenshot"
    REPLAY_SCRIPT = "replay_script"
    PACKAGE_REFERENCE = "package_reference"
    DIFF_HUNK = "diff_hunk"
    BEHAVIORAL_TRACE = "behavioral_trace"


# Kinds that are safe to hand to a human analyst with no further
# sandboxing. A replay_script is NOT in this set: always dock it.
_SAFE_TO_HAND_OVER: frozenset[PocKind] = frozenset({
    PocKind.CURL,
    PocKind.HTTP_PAIR,
    PocKind.SCREENSHOT,
    PocKind.PACKAGE_REFERENCE,
    PocKind.DIFF_HUNK,
    PocKind.BEHAVIORAL_TRACE,
})


@dataclass(slots=True)
class PocArtifact:
    """A reproducible proof-of-concept artifact attached to a finding.

    ``content`` carries raw bytes (UTF-8 text for scripts and curl,
    binary for screenshots, JSON for package references). ``sha256``
    is computed at construction time and is the key used in the
    EvidenceChain hash chain.

    Safety flags:
        ``reproducible``     analyst can replay with no infrastructure
        ``safe_handover``    no sandbox needed
        ``destructive``      replaying could mutate target state
    """

    finding_id: str
    kind: PocKind
    content: bytes
    content_type: str               # MIME type, e.g., "text/plain", "image/png"
    sha256: str = ""                # Derived from content at __post_init__
    description: str = ""
    target: str = ""                # URL, package name, repo, etc.
    reproducible: bool = True
    destructive: bool = False
    created_at: str = ""            # ISO 8601 UTC
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.sha256:
            self.sha256 = hashlib.sha256(self.content).hexdigest()
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    @property
    def safe_handover(self) -> bool:
        """True when the artifact can go to an analyst with no sandbox."""
        return self.kind in _SAFE_TO_HAND_OVER and not self.destructive

    def to_dict(self, include_content: bool = False) -> dict[str, Any]:
        """Serialize. Content is excluded by default to keep reports lean."""
        d: dict[str, Any] = {
            "finding_id": self.finding_id,
            "kind": self.kind.value,
            "content_type": self.content_type,
            "sha256": self.sha256,
            "description": self.description,
            "target": self.target,
            "reproducible": self.reproducible,
            "destructive": self.destructive,
            "safe_handover": self.safe_handover,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }
        if include_content:
            # Best-effort text decode; fallback to base64 for binary.
            try:
                d["content"] = self.content.decode("utf-8")
            except UnicodeDecodeError:
                import base64
                d["content"] = base64.b64encode(self.content).decode("ascii")
                d["content_encoding"] = "base64"
        return d


# ---------------------------------------------------------------------------
# Builders -- one per kind so finding code never has to construct the
# content_type or safety flags by hand.
# ---------------------------------------------------------------------------


def build_curl_poc(
    finding_id: str,
    *,
    curl_command: str,
    target: str,
    description: str = "",
    destructive: bool = False,
) -> PocArtifact:
    """Build a curl-based PoC artifact.

    ``curl_command`` is the fully-formed command line, including
    method, headers, body, and target URL. Shell-safe (quoted).
    """
    return PocArtifact(
        finding_id=finding_id,
        kind=PocKind.CURL,
        content=curl_command.encode("utf-8"),
        content_type="text/x-shellscript",
        description=description,
        target=target,
        reproducible=True,
        destructive=destructive,
    )


def build_http_pair_poc(
    finding_id: str,
    *,
    request_raw: str,
    response_raw: str,
    target: str,
    description: str = "",
) -> PocArtifact:
    """Build a request+response transcript PoC.

    Stored as a single text blob with ``---REQUEST---`` and
    ``---RESPONSE---`` markers for the analyst's eye. Always
    non-destructive (read-only record).
    """
    blob = (
        "---REQUEST---\n"
        f"{request_raw}\n"
        "---RESPONSE---\n"
        f"{response_raw}\n"
    )
    return PocArtifact(
        finding_id=finding_id,
        kind=PocKind.HTTP_PAIR,
        content=blob.encode("utf-8"),
        content_type="text/plain",
        description=description,
        target=target,
        reproducible=False,   # Transcript, not replayable directly
        destructive=False,
    )


def build_package_reference_poc(
    finding_id: str,
    *,
    ecosystem: str,              # "npm" | "pypi" | "cargo" | "maven"
    package_name: str,
    version: str,
    observed_hash: str,          # sha256/sha512 of the installed artifact
    expected_hash: str = "",     # canonical hash from registry, if known
    description: str = "",
    target: str = "",
) -> PocArtifact:
    """Build a package-reference PoC for supply-chain findings.

    NEVER executable. Pure metadata. The hash mismatch (observed vs
    expected) is the evidence: it shows the installed artifact does
    not match what the registry claims is canonical, which is the
    fingerprint of a trojaned dependency.
    """
    import json
    payload = {
        "ecosystem": ecosystem,
        "package": package_name,
        "version": version,
        "observed_hash": observed_hash,
        "expected_hash": expected_hash,
        "hash_matches": bool(expected_hash) and observed_hash == expected_hash,
    }
    blob = json.dumps(payload, indent=2).encode("utf-8")
    return PocArtifact(
        finding_id=finding_id,
        kind=PocKind.PACKAGE_REFERENCE,
        content=blob,
        content_type="application/json",
        description=description or f"{ecosystem}:{package_name}@{version}",
        target=target or f"{ecosystem}:{package_name}",
        reproducible=False,   # Observational, not replayable
        destructive=False,
        metadata={
            "ecosystem": ecosystem,
            "package": package_name,
            "version": version,
        },
    )


def build_diff_hunk_poc(
    finding_id: str,
    *,
    file_path: str,
    hunk: str,
    language: str = "",
    description: str = "",
) -> PocArtifact:
    """Build a source-code-pattern PoC.

    ``hunk`` is a unified-diff or plain-snippet slice of the
    vulnerable code. Safe to hand over: it's just text.
    """
    return PocArtifact(
        finding_id=finding_id,
        kind=PocKind.DIFF_HUNK,
        content=hunk.encode("utf-8"),
        content_type=f"text/x-{language}" if language else "text/plain",
        description=description,
        target=file_path,
        reproducible=False,
        destructive=False,
        metadata={"file_path": file_path, "language": language},
    )


def build_behavioral_trace_poc(
    finding_id: str,
    *,
    trace_summary: str,           # Human-readable summary, not raw trace
    target: str,
    description: str = "",
) -> PocArtifact:
    """Build a behavioral-trace PoC.

    Stores a summary (not the raw trace) so PII / secrets / binary
    data never land in the vault. The raw trace lives in
    EvidenceCapture itself, separately encrypted.
    """
    return PocArtifact(
        finding_id=finding_id,
        kind=PocKind.BEHAVIORAL_TRACE,
        content=trace_summary.encode("utf-8"),
        content_type="text/plain",
        description=description,
        target=target,
        reproducible=False,
        destructive=False,
    )


def build_replay_script_poc(
    finding_id: str,
    *,
    script_body: str,
    language: str,                # "bash" | "python"
    target: str,
    description: str = "",
    destructive: bool = True,     # Default True: replay scripts ARE destructive
) -> PocArtifact:
    """Build a replay-script PoC. Always needs sandboxing to run."""
    ct = "text/x-shellscript" if language == "bash" else "text/x-python"
    return PocArtifact(
        finding_id=finding_id,
        kind=PocKind.REPLAY_SCRIPT,
        content=script_body.encode("utf-8"),
        content_type=ct,
        description=description,
        target=target,
        reproducible=True,
        destructive=destructive,
        metadata={"language": language},
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def verify_artifact_integrity(artifact: PocArtifact) -> bool:
    """Recompute the SHA-256 and confirm the artifact has not been
    tampered with since construction.
    """
    expected = hashlib.sha256(artifact.content).hexdigest()
    return expected == artifact.sha256
