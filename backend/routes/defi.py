"""
DeFi Smart Contract Security Scanner API

Provides endpoints for:
- Smart contract scanning using Slither
- Vulnerability detection and reporting
- Security audit generation
- Fix recommendations

Requires: pip install slither-analyzer
"""

import asyncio
import logging
import subprocess
import tempfile
import json
import os
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/defi", tags=["defi"])


# ============================================
# Data Models
# ============================================

@dataclass
class ScanResult:
    """Result of a security scan"""
    scan_id: str
    contract_path: str
    status: str = "pending"
    started_at: str = ""
    completed_at: Optional[str] = None
    findings: List[Dict[str, Any]] = field(default_factory=list)
    summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def __post_init__(self):
        if not self.started_at:
            self.started_at = datetime.utcnow().isoformat()


# In-memory store for scan results (would be DB in production)
_scans: Dict[str, ScanResult] = {}


class ScanRequest(BaseModel):
    contract_path: str = Field(..., description="Path to .sol file or contract code")
    workspace: str = Field(default=".", description="Base workspace path")
    is_inline_code: bool = Field(default=False, description="True if contract_path is actual Solidity code")


class VerifyRequest(BaseModel):
    tool: str = Field(..., description="Tool to verify: slither, mythril, echidna, foundry")


# ============================================
# Helper Functions
# ============================================

def check_tool_installed(tool: str) -> Dict[str, Any]:
    """Check if a security tool is installed"""
    tool_commands = {
        "slither": ["slither", "--version"],
        "mythril": ["myth", "version"],
        "echidna": ["echidna", "--version"],
        "foundry": ["forge", "--version"],
        "solc": ["solc", "--version"]
    }
    
    if tool not in tool_commands:
        return {"tool": tool, "installed": False, "error": "Unknown tool"}
    
    try:
        result = subprocess.run(
            tool_commands[tool],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0]
            return {"tool": tool, "installed": True, "version": version}
        else:
            return {"tool": tool, "installed": False, "error": result.stderr[:200]}
    except FileNotFoundError:
        return {"tool": tool, "installed": False, "error": "Not found in PATH"}
    except subprocess.TimeoutExpired:
        return {"tool": tool, "installed": False, "error": "Command timed out"}
    except Exception as e:
        return {"tool": tool, "installed": False, "error": str(e)}


async def run_slither_scan(scan_id: str, contract_path: str, is_inline: bool = False) -> None:
    """Run Slither security scan in background"""
    scan = _scans.get(scan_id)
    if not scan:
        return
    
    try:
        scan.status = "scanning"
        
        # If inline code, write to temp file
        if is_inline:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sol', delete=False) as f:
                f.write(contract_path)
                contract_file = f.name
        else:
            contract_file = contract_path
            if not os.path.exists(contract_file):
                scan.status = "error"
                scan.error = f"Contract file not found: {contract_file}"
                return
        
        # Run Slither
        result = subprocess.run(
            ["slither", contract_file, "--json", "-"],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        # Parse JSON output
        if result.stdout:
            try:
                slither_output = json.loads(result.stdout)
                detectors = slither_output.get("results", {}).get("detectors", [])
                
                # Convert to findings
                findings = []
                severity_counts = {"High": 0, "Medium": 0, "Low": 0, "Informational": 0}
                
                for d in detectors:
                    severity = d.get("impact", "Low")
                    if severity in severity_counts:
                        severity_counts[severity] += 1
                    
                    finding = {
                        "id": d.get("id", hashlib.md5(str(d).encode()).hexdigest()[:8]),
                        "title": d.get("check", "Unknown"),
                        "severity": severity,
                        "confidence": d.get("confidence", "Medium"),
                        "description": d.get("description", ""),
                        "location": ", ".join(str(e.get("source_mapping", {}).get("filename_relative", "")) 
                                              for e in d.get("elements", [])[:3]),
                        "recommendation": d.get("markdown", "")[:500]
                    }
                    findings.append(finding)
                
                scan.findings = findings
                scan.summary = {
                    "total_findings": len(findings),
                    "high": severity_counts["High"],
                    "medium": severity_counts["Medium"],
                    "low": severity_counts["Low"],
                    "informational": severity_counts["Informational"],
                    "risk_level": "CRITICAL" if severity_counts["High"] > 0 else 
                                 "HIGH" if severity_counts["Medium"] > 2 else
                                 "MEDIUM" if severity_counts["Medium"] > 0 else "LOW"
                }
                scan.status = "completed"
                
            except json.JSONDecodeError:
                scan.status = "completed"
                scan.findings = []
                scan.summary = {"total_findings": 0, "note": "No vulnerabilities detected or parse error"}
        else:
            scan.status = "completed"
            scan.findings = []
            scan.summary = {"total_findings": 0, "note": "No output from scanner"}
        
        # Clean up temp file
        if is_inline:
            try:
                os.unlink(contract_file)
            except:
                pass
                
        scan.completed_at = datetime.utcnow().isoformat()
        
    except subprocess.TimeoutExpired:
        scan.status = "error"
        scan.error = "Scan timed out after 120 seconds"
    except Exception as e:
        scan.status = "error"
        scan.error = str(e)
        logger.error(f"Slither scan error: {e}")


# ============================================
# API Endpoints
# ============================================

@router.get("/dependencies")
async def get_dependencies() -> Dict[str, Any]:
    """Check which security tools are available"""
    tools = ["slither", "mythril", "echidna", "foundry", "solc"]
    statuses = [check_tool_installed(t) for t in tools]
    
    return {
        "tools": statuses,
        "ready": any(t["installed"] for t in statuses)
    }


@router.post("/verify-tool")
async def verify_tool(request: VerifyRequest) -> Dict[str, Any]:
    """Verify a specific tool is installed and working"""
    result = check_tool_installed(request.tool)
    
    if result["installed"]:
        return {
            "success": True,
            "tool": request.tool,
            "version": result.get("version", "unknown")
        }
    else:
        return {
            "success": False,
            "tool": request.tool,
            "error": result.get("error", "Not installed")
        }


@router.post("/scan")
async def start_scan(
    request: ScanRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """
    Start a smart contract security scan.
    
    Returns a scan_id that can be used to check progress and results.
    """
    # Generate scan ID
    scan_id = hashlib.md5(
        f"{request.contract_path}{datetime.utcnow().isoformat()}".encode()
    ).hexdigest()[:12]
    
    # Determine contract path
    if request.is_inline_code:
        contract_path = request.contract_path
    else:
        if request.workspace != ".":
            contract_path = os.path.join(request.workspace, request.contract_path)
        else:
            contract_path = request.contract_path
    
    # Create scan record
    scan = ScanResult(
        scan_id=scan_id,
        contract_path=request.contract_path[:100],  # Truncate inline code in record
    )
    _scans[scan_id] = scan
    
    # Start background scan
    background_tasks.add_task(
        run_slither_scan, 
        scan_id, 
        contract_path,
        request.is_inline_code
    )
    
    return {
        "scan_id": scan_id,
        "status": "scanning",
        "message": "Scan started. Use /defi/scan/{scan_id} to check progress."
    }


@router.get("/scan/{scan_id}")
async def get_scan_status(scan_id: str) -> Dict[str, Any]:
    """Get the status and results of a scan"""
    scan = _scans.get(scan_id)
    
    if not scan:
        raise HTTPException(404, f"Scan not found: {scan_id}")
    
    return {
        "scan_id": scan.scan_id,
        "status": scan.status,
        "contract_path": scan.contract_path,
        "started_at": scan.started_at,
        "completed_at": scan.completed_at,
        "findings": scan.findings if scan.status == "completed" else [],
        "summary": scan.summary,
        "error": scan.error
    }


@router.get("/scan/{scan_id}/findings")
async def get_scan_findings(scan_id: str) -> Dict[str, Any]:
    """Get just the findings from a completed scan"""
    scan = _scans.get(scan_id)
    
    if not scan:
        raise HTTPException(404, f"Scan not found: {scan_id}")
    
    if scan.status != "completed":
        return {
            "scan_id": scan_id,
            "status": scan.status,
            "message": "Scan not yet complete",
            "findings": []
        }
    
    return {
        "scan_id": scan_id,
        "findings": scan.findings,
        "summary": scan.summary
    }


@router.post("/report/{scan_id}")
async def generate_report(scan_id: str) -> Dict[str, Any]:
    """Generate a markdown security report from scan results"""
    scan = _scans.get(scan_id)
    
    if not scan:
        raise HTTPException(404, f"Scan not found: {scan_id}")
    
    if scan.status != "completed":
        return {
            "error": "Scan not complete",
            "status": scan.status
        }
    
    # Generate markdown report
    report = f"""# Smart Contract Security Audit Report

**Scan ID:** {scan.scan_id}  
**Contract:** {scan.contract_path}  
**Date:** {scan.started_at}  

## Summary

- **Risk Level:** {scan.summary.get('risk_level', 'Unknown')}
- **Total Findings:** {scan.summary.get('total_findings', 0)}
- **High Severity:** {scan.summary.get('high', 0)}
- **Medium Severity:** {scan.summary.get('medium', 0)}
- **Low Severity:** {scan.summary.get('low', 0)}
- **Informational:** {scan.summary.get('informational', 0)}

## Findings

"""
    
    for i, f in enumerate(scan.findings, 1):
        severity_emoji = {"High": "🔴", "Medium": "🟠", "Low": "🟡", "Informational": "🔵"}.get(f['severity'], "⚪")
        report += f"""### {i}. {f['title']}

{severity_emoji} **Severity:** {f['severity']} | **Confidence:** {f['confidence']}

**Location:** {f['location']}

**Description:**
{f['description'][:500]}

---

"""
    
    if not scan.findings:
        report += "_No vulnerabilities detected._\n"
    
    report += f"""
## Recommendations

1. Address all High severity findings before deployment
2. Review Medium severity findings with your security team
3. Consider Low severity findings for code quality improvements

---

*Report generated by Daena DeFi Security Scanner*
*Powered by Slither static analysis*
"""
    
    return {
        "scan_id": scan_id,
        "content": report,
        "format": "markdown"
    }


@router.post("/fix/{scan_id}")
async def apply_fixes(
    scan_id: str,
    finding_ids: List[str] = [],
    create_branch: bool = True
) -> Dict[str, Any]:
    """
    Suggest or apply fixes for findings.
    
    This requires founder approval for actual code changes.
    """
    scan = _scans.get(scan_id)
    
    if not scan:
        raise HTTPException(404, f"Scan not found: {scan_id}")
    
    # For now, return approval required
    return {
        "scan_id": scan_id,
        "approval_required": True,
        "approval_id": f"fix-{scan_id}",
        "message": "Fix application requires founder approval. Check the Approvals Inbox."
    }


@router.get("/health")
async def defi_health() -> Dict[str, Any]:
    """Health check for DeFi scanner"""
    slither_status = check_tool_installed("slither")
    
    return {
        "status": "healthy" if slither_status["installed"] else "degraded",
        "slither": slither_status,
        "active_scans": len([s for s in _scans.values() if s.status == "scanning"])
    }
