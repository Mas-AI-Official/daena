"""MCP sync endpoints -- detect CLI-installed MCPs and one-click import.

Operator pain it solves
------------------------
Installing the same MCP four times (Claude Code, Codex, Gemini, Daena) for
one capability. This router exposes:

* ``GET /api/v1/mcp-sync/detected`` -- merged, deduplicated list of MCPs
  found in the operator's installed CLI configs.
* ``POST /api/v1/mcp-sync/import`` -- runs the entry through
  ``install_scanner.scan_mcp_server`` and, if safe, stores the result in
  the shared ``MCPRegistry``.

Design notes
------------
Read-only on CLI configs. We never mutate ``~/.claude/mcp.json`` and
friends. Governance runs on every import via the Security Department's
install scanner. No OAuth tokens are copied between tools -- detected
MCPs must be re-authorized inside Daena.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, get_current_user
from app.core.events import get_mcp_registry
from app.core.logging import get_logger
from app.services.mcp_registry import MCPTool
from app.services.mcp_sync.detector import CLIMCPDetector
from app.services.security.install_scanner import InstallScanner

logger = get_logger(__name__)

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────


class DetectedMCPOut(BaseModel):
    """Flat DTO for a detected MCP server."""

    source_cli: str
    config_path: str
    name: str
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""
    notes: str = ""


class MCPImportRequest(BaseModel):
    """Body of the import call.

    Mirrors :class:`DetectedMCP` so the UI can pass through the row it
    picked from ``GET /detected`` untouched.
    """

    name: str
    command: str = ""
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    url: str = ""


class MCPImportResult(BaseModel):
    """What the import endpoint returns on both safe and blocked paths."""

    safe: bool
    registered: bool
    name: str
    governance_tier: int = 0
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Helpers ──────────────────────────────────────────────────────────


def _scan_target(req: MCPImportRequest) -> str:
    """Build the scan target string the install scanner expects.

    ``InstallScanner.scan_mcp_server`` accepts anything that starts with
    ``http://``, ``https://``, ``npx ``, or ``uvx ``. Command-based MCPs
    need a synthetic ``<command> <first_arg>`` string.
    """
    if req.url:
        return req.url
    if req.command:
        first_arg = req.args[0] if req.args else ""
        return f"{req.command} {first_arg}".strip()
    return ""


# ── Routes ───────────────────────────────────────────────────────────


@router.get("/detected", response_model=list[DetectedMCPOut])
async def list_detected(
    user: CurrentUser = Depends(get_current_user),
) -> list[DetectedMCPOut]:
    """Return the deduplicated list of MCPs found in installed CLI configs.

    Empty list when no CLI config is present or readable. Never raises on
    missing files -- a fresh machine with no CLIs is a valid state.
    """
    detector = CLIMCPDetector()
    raw = await detector.discover_all()
    deduped = CLIMCPDetector.deduplicate(raw)
    logger.info(
        "mcp_sync.api.detected",
        user_id=str(user.id),
        total=len(deduped),
    )
    return [
        DetectedMCPOut(
            source_cli=m.source_cli,
            config_path=m.config_path,
            name=m.name,
            command=m.command,
            args=list(m.args),
            env=dict(m.env),
            url=m.url,
            notes=m.notes,
        )
        for m in deduped
    ]


@router.post("/import", response_model=MCPImportResult)
async def import_mcp(
    req: MCPImportRequest,
    user: CurrentUser = Depends(get_current_user),
) -> MCPImportResult:
    """Scan then register a detected MCP.

    The scan runs first and an unsafe entry is reported back with the
    specific blockers so the UI can surface them. A safe entry is
    registered in the shared :class:`MCPRegistry` at the default
    governance tier (2 = NOTIFIED for external tools).
    """
    if not req.name:
        raise HTTPException(status_code=422, detail="name is required")

    target = _scan_target(req)
    if not target:
        raise HTTPException(
            status_code=422,
            detail="One of url, command+args must be provided",
        )

    scanner = InstallScanner()
    scan = await scanner.scan_mcp_server(target, server_name=req.name)
    if not scan.safe:
        logger.warning(
            "mcp_sync.api.import_blocked",
            user_id=str(user.id),
            name=req.name,
            blockers=scan.blockers,
        )
        return MCPImportResult(
            safe=False,
            registered=False,
            name=req.name,
            blockers=list(scan.blockers),
            warnings=list(scan.warnings),
        )

    # Safe -- register as a tool placeholder in the MCP registry.
    # Description is kept minimal here because detected entries don't
    # carry schema info; a later MCPRegistry.discover_tools call can
    # enrich once the server is live.
    registry = get_mcp_registry()
    tool = MCPTool(
        name=req.name,
        description=f"Imported from CLI detection ({target})",
        input_schema={},
        connection_id=f"mcp_sync:{user.id}",
        governance_tier=2,
    )
    registered_count = await registry.register_tools([tool])

    logger.info(
        "mcp_sync.api.import_ok",
        user_id=str(user.id),
        name=req.name,
        governance_tier=tool.governance_tier,
        registered=registered_count,
    )
    return MCPImportResult(
        safe=True,
        registered=registered_count > 0,
        name=req.name,
        governance_tier=tool.governance_tier,
        warnings=list(scan.warnings),
    )
