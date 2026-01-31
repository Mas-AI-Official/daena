"""
DeFi/Web3 Smart Contract Security Routes
Integrated into Control Plane - NO new department
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid
import asyncio
import subprocess
import json
import os
from pathlib import Path

from backend.config.settings import settings, project_root
from backend.services.audit_service import audit_log

router = APIRouter(prefix="/defi", tags=["DeFi Security"])

# In-memory scan storage (production would use DB)
SCANS: Dict[str, Dict[str, Any]] = {}

# Workspace allowlist
ALLOWED_WORKSPACES = [
    str(project_root),
    str(project_root / "contracts"),
    str(project_root / "workspace"),
]


class ScanRequest(BaseModel):
    workspace_path: str = Field(default=".", description="Path within allowed workspace")
    contract_path: str = Field(..., description="Relative path to contract file")
    chain: Optional[str] = Field(default="ethereum", description="Target chain")
    mode: str = Field(default="read_only", description="read_only | fix_suggest | fix_apply")
    tools: List[str] = Field(default=["slither"], description="Tools to run")


class ScanResponse(BaseModel):
    scan_id: str
    status: str
    estimated_time: int
    message: Optional[str] = None


class Finding(BaseModel):
    id: str
    severity: str  # critical, high, medium, low, info
    title: str
    location: str
    tool: str
    description: str
    recommendation: Optional[str] = None
    evidence: Optional[str] = None


class ScanResult(BaseModel):
    scan_id: str
    status: str
    contract_path: str
    started_at: str
    completed_at: Optional[str] = None
    findings: List[Finding] = []
    summary: Dict[str, int] = {}
    raw_outputs: Dict[str, str] = {}
    errors: List[str] = []


class FixRequest(BaseModel):
    finding_ids: List[str] = Field(default=[], description="Findings to fix")
    create_branch: bool = Field(default=True)
    branch_name: Optional[str] = None


def validate_workspace(path: str) -> Path:
    """Validate path is within allowed workspace."""
    resolved = Path(path).resolve()
    for allowed in ALLOWED_WORKSPACES:
        if str(resolved).startswith(allowed):
            return resolved
    raise HTTPException(status_code=403, detail=f"Path not in allowed workspace: {path}")


def check_tool_installed(tool: str) -> tuple[bool, str]:
    """Check if a DeFi tool is installed."""
    tool_commands = {
        "slither": "slither --version",
        "mythril": "myth version",
        "foundry": "forge --version",
        "echidna": "echidna-test --version"
    }
    cmd = tool_commands.get(tool)
    if not cmd:
        return False, f"Unknown tool: {tool}"
    
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            timeout=10,
            shell=True
        )
        if result.returncode == 0:
            return True, result.stdout.decode().strip()
        return False, f"Tool {tool} not found. Install with: pip install {tool}-analyzer"
    except Exception as e:
        return False, f"Error checking {tool}: {str(e)}"


async def run_slither(contract_path: Path, scan_id: str) -> Dict[str, Any]:
    """Run Slither static analysis."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "slither", str(contract_path), "--json", "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(contract_path.parent)
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        
        if proc.returncode == 0 or stdout:
            try:
                return json.loads(stdout.decode())
            except json.JSONDecodeError:
                return {"raw_output": stdout.decode(), "error": None}
        return {"error": stderr.decode()}
    except asyncio.TimeoutError:
        return {"error": "Slither timed out after 5 minutes"}
    except FileNotFoundError:
        return {"error": "Slither not installed. Run: pip install slither-analyzer"}
    except Exception as e:
        return {"error": str(e)}


def parse_slither_findings(slither_output: Dict) -> List[Finding]:
    """Parse Slither JSON output into Finding objects."""
    findings = []
    detectors = slither_output.get("results", {}).get("detectors", [])
    
    for i, det in enumerate(detectors):
        severity_map = {
            "High": "high",
            "Medium": "medium", 
            "Low": "low",
            "Informational": "info",
            "Optimization": "info"
        }
        findings.append(Finding(
            id=f"slither-{i}",
            severity=severity_map.get(det.get("impact", ""), "info"),
            title=det.get("check", "Unknown"),
            location=det.get("first_markdown_element", ""),
            tool="slither",
            description=det.get("description", ""),
            recommendation=det.get("recommendation", None),
            evidence=det.get("markdown", None)
        ))
    
    return findings


async def run_scan_background(scan_id: str, request: ScanRequest, contract_full_path: Path):
    """Background task to run the scan."""
    scan = SCANS[scan_id]
    scan["status"] = "running"
    
    try:
        for tool in request.tools:
            if tool == "slither":
                result = await run_slither(contract_full_path, scan_id)
                scan["raw_outputs"]["slither"] = json.dumps(result, indent=2)[:50000]  # Limit size
                
                if "error" in result and result["error"]:
                    scan["errors"].append(f"Slither: {result['error']}")
                else:
                    findings = parse_slither_findings(result)
                    scan["findings"].extend(findings)
            else:
                scan["errors"].append(f"Tool '{tool}' not yet implemented")
        
        # Calculate summary
        scan["summary"] = {
            "critical": len([f for f in scan["findings"] if f.severity == "critical"]),
            "high": len([f for f in scan["findings"] if f.severity == "high"]),
            "medium": len([f for f in scan["findings"] if f.severity == "medium"]),
            "low": len([f for f in scan["findings"] if f.severity == "low"]),
            "info": len([f for f in scan["findings"] if f.severity == "info"]),
        }
        
        scan["status"] = "completed"
        scan["completed_at"] = datetime.utcnow().isoformat()
        
    except Exception as e:
        scan["status"] = "failed"
        scan["errors"].append(str(e))
        scan["completed_at"] = datetime.utcnow().isoformat()


@router.post("/scan", response_model=ScanResponse)
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """
    Start a smart contract security scan.
    
    Mode options:
    - read_only: Only analyze, no changes
    - fix_suggest: Analyze and suggest fixes
    - fix_apply: Apply fixes (requires approval)
    """
    # Validate workspace
    workspace = validate_workspace(request.workspace_path)
    contract_full_path = workspace / request.contract_path
    
    if not contract_full_path.exists():
        raise HTTPException(status_code=404, detail=f"Contract not found: {request.contract_path}")
    
    if not contract_full_path.suffix in [".sol", ".vy"]:
        raise HTTPException(status_code=400, detail="Only .sol and .vy files supported")
    
    # Check tools
    missing_tools = []
    for tool in request.tools:
        installed, msg = check_tool_installed(tool)
        if not installed:
            missing_tools.append(msg)
    
    if missing_tools:
        return ScanResponse(
            scan_id="",
            status="error",
            estimated_time=0,
            message="Missing dependencies: " + "; ".join(missing_tools)
        )
    
    # Create scan record
    scan_id = f"scan_{uuid.uuid4().hex[:12]}"
    SCANS[scan_id] = {
        "scan_id": scan_id,
        "status": "queued",
        "contract_path": str(request.contract_path),
        "workspace": str(workspace),
        "mode": request.mode,
        "tools": request.tools,
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "findings": [],
        "summary": {},
        "raw_outputs": {},
        "errors": []
    }
    
    # Log audit entry
    await audit_log.log(
        event_type="defi.scan.started",
        entity_type="contract",
        entity_id=scan_id,
        payload={
            "contract": str(request.contract_path),
            "tools": request.tools,
            "mode": request.mode
        }
    )
    
    # Start background scan
    background_tasks.add_task(run_scan_background, scan_id, request, contract_full_path)
    
    return ScanResponse(
        scan_id=scan_id,
        status="queued",
        estimated_time=len(request.tools) * 60
    )


@router.get("/scan/{scan_id}")
async def get_scan_result(scan_id: str):
    """Get scan results by ID."""
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    scan = SCANS[scan_id]
    
    # Convert findings to dict for response
    return {
        "scan_id": scan["scan_id"],
        "status": scan["status"],
        "contract_path": scan["contract_path"],
        "started_at": scan["started_at"],
        "completed_at": scan.get("completed_at"),
        "findings": [f.dict() if hasattr(f, 'dict') else f for f in scan.get("findings", [])],
        "summary": scan.get("summary", {}),
        "errors": scan.get("errors", [])
    }


@router.post("/report/{scan_id}")
async def generate_report(scan_id: str):
    """Generate an investor-ready audit report."""
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    scan = SCANS[scan_id]
    if scan["status"] != "completed":
        raise HTTPException(status_code=400, detail="Scan not yet completed")
    
    # Generate markdown report
    report_id = f"report_{uuid.uuid4().hex[:8]}"
    
    report_md = f"""# Smart Contract Security Audit Report

## Contract: {scan['contract_path']}
## Date: {datetime.utcnow().strftime('%Y-%m-%d')}
## Scan ID: {scan_id}

---

## Executive Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | {scan['summary'].get('critical', 0)} |
| 🟠 High | {scan['summary'].get('high', 0)} |
| 🟡 Medium | {scan['summary'].get('medium', 0)} |
| 🟢 Low | {scan['summary'].get('low', 0)} |
| ℹ️ Info | {scan['summary'].get('info', 0)} |

---

## Findings

"""
    for finding in scan.get("findings", []):
        f = finding if isinstance(finding, dict) else finding.dict()
        severity_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢", "info": "ℹ️"}.get(f["severity"], "")
        report_md += f"""
### {severity_icon} {f['title']}

- **Severity**: {f['severity'].upper()}
- **Location**: `{f['location']}`
- **Tool**: {f['tool']}

**Description**: {f['description']}

**Recommendation**: {f.get('recommendation', 'N/A')}

---
"""
    
    report_md += """
## Methodology

This report was generated using automated static analysis tools:
- Slither (Trail of Bits)

All findings should be reviewed by a human auditor before deployment.

---

*Generated by Daena DeFi Guardian*
"""
    
    return {
        "report_id": report_id,
        "format": "markdown",
        "content": report_md,
        "download_url": f"/api/v1/defi/report/{report_id}/download"
    }


@router.post("/fix/{scan_id}")
async def apply_fixes(scan_id: str, request: FixRequest):
    """
    Apply fixes for findings. REQUIRES APPROVAL.
    """
    if scan_id not in SCANS:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    scan = SCANS[scan_id]
    if scan["status"] != "completed":
        raise HTTPException(status_code=400, detail="Scan not yet completed")
    
    # This action requires approval
    approval_id = f"apr_{uuid.uuid4().hex[:8]}"
    
    await audit_log.log(
        event_type="defi.fix.requested",
        entity_type="approval",
        entity_id=approval_id,
        payload={
            "scan_id": scan_id,
            "finding_ids": request.finding_ids,
            "requires_approval": True
        }
    )
    
    return {
        "approval_required": True,
        "approval_id": approval_id,
        "message": "This action requires founder approval. Check Approvals Inbox.",
        "pending_changes": [
            {
                "file": scan["contract_path"],
                "action": "Apply security fixes",
                "finding_count": len(request.finding_ids) or len(scan.get("findings", []))
            }
        ]
    }


@router.get("/tools")
async def list_defi_tools():
    """List available DeFi security tools and their status."""
    tools = [
        {
            "name": "slither",
            "description": "Static analysis for Solidity",
            "installed": check_tool_installed("slither")[0],
            "install_cmd": "pip install slither-analyzer"
        },
        {
            "name": "mythril", 
            "description": "Symbolic execution for EVM",
            "installed": check_tool_installed("mythril")[0],
            "install_cmd": "pip install mythril"
        },
        {
            "name": "foundry",
            "description": "Fuzz testing with Forge",
            "installed": check_tool_installed("foundry")[0],
            "install_cmd": "curl -L https://foundry.paradigm.xyz | bash"
        },
        {
            "name": "echidna",
            "description": "Property-based fuzzing",
            "installed": check_tool_installed("echidna")[0],
            "install_cmd": "See https://github.com/crytic/echidna"
        }
    ]
    return {"tools": tools}


@router.get("/dependencies")
async def check_dependencies():
    """Check all DeFi tool dependencies."""
    results = {}
    for tool in ["slither", "mythril", "foundry", "echidna"]:
        installed, msg = check_tool_installed(tool)
        results[tool] = {"installed": installed, "message": msg}
    return {"dependencies": results}
