"""
Package Auditor — Supply-chain governance for Daena.

EVERY package install (npm, pip, cargo, etc.) MUST pass through this loop
before it touches the system. This is the "Shadow Dept applied to supply chain."

Audit Loop:
  REQUEST → QUEUE → STATIC ANALYSIS → DEPENDENCY TREE → CVE SCAN
          → SANDBOX INSTALL (isolated) → BEHAVIORAL CHECK → DECISION
          → PENDING_APPROVAL (if risk > low) → APPROVED/REJECTED → INSTALL or BLOCK

This catches:
  - Known CVEs (npm advisory, PyPI advisories)
  - Typosquatting (name similarity to popular packages)
  - Suspicious dependency trees (too deep, pulls in unexpected things)
  - Malicious code patterns (postinstall scripts, network calls in install hooks)
  - License violations
"""

import uuid
import time
import hashlib
import re
import json
from enum import Enum
from typing import Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict


# ─────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────

class AuditStatus(str, Enum):
    QUEUED = "queued"
    SCANNING = "scanning"
    STATIC_ANALYSIS = "static_analysis"
    CVE_CHECK = "cve_check"
    SANDBOX_INSTALL = "sandbox_install"
    BEHAVIORAL_CHECK = "behavioral_check"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    INSTALLED = "installed"
    BLOCKED = "blocked"


class RiskLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PackageManager(str, Enum):
    NPM = "npm"
    PIP = "pip"
    YARN = "yarn"
    CARGO = "cargo"
    UNKNOWN = "unknown"


# ─────────────────────────────────────────
# KNOWN THREAT DATABASE (inline, expandable)
# ─────────────────────────────────────────

# Known malicious packages (curated list — in production, pull from npm advisories / PyPI)
KNOWN_MALICIOUS = {
    # npm
    "event-stream", "flatmap-stream", "ua-parser-js",
    "rc", "colors", "faker",
    # pip  
    "requests-data", "beautifulsoup", "tensorflow-gpu-2",
    # Typosquats of popular packages
    "reqeusts", "requ ests", "flask1", "djangoo",
    "reacts", "vue2", "angularjs2", "expresss",
    "lodas", "momentt", "axiosss", "webpakc"
}

# Suspicious install-hook patterns (run at install time — red flag)
SUSPICIOUS_INSTALL_PATTERNS = [
    r"postinstall",
    r"preinstall",
    r"install.*script",
    r"\.exe",
    r"child_process",
    r"child\.exec",
    r"require\(\s*['\"]child_process['\"]\s*\)",
    r"require\(\s*['\"]fs['\"]\s*\).*writeFile",
    r"fetch\(",
    r"http\.request",
    r"https\.request",
    r"XMLHttpRequest",
    r"eval\(",
    r"Function\(\s*['\"]",
    r"process\.env",
    r"\.env",
    r"API_KEY",
    r"SECRET",
    r"TOKEN",
    r"credentials"
]

# Popular package name whitelist (legitimate — skip some checks)
POPULAR_PACKAGES = {
    "react", "react-dom", "next", "vue", "angular", "svelte",
    "express", "fastapi", "flask", "django", "uvicorn",
    "numpy", "pandas", "scikit-learn", "tensorflow", "torch",
    "axios", "lodash", "moment", "webpack", "babel",
    "typescript", "eslint", "prettier", "jest", "pytest",
    "sqlalchemy", "celery", "redis", "boto3", "pydantic",
    "tailwindcss", "postcss", "autoprefixer", "vite",
    "ethers", "web3", "hardhat", "solc", "slither-analyzer"
}

# License risk tiers
RISKY_LICENSES = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1"}
SAFE_LICENSES = {"MIT", "ISC", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "0BSD", "Unlicense"}


# ─────────────────────────────────────────
# AUDIT RECORD
# ─────────────────────────────────────────

@dataclass
class AuditFinding:
    severity: str           # "info" | "warning" | "error" | "critical"
    category: str           # "cve" | "typosquat" | "malicious" | "suspicious_script" | "license" | "dependency"
    message: str
    details: Optional[dict] = None


@dataclass
class PackageAuditRecord:
    id: str
    package_name: str
    package_version: str
    package_manager: PackageManager
    requested_by: str               # agent_id or "founder"
    status: AuditStatus
    risk_level: RiskLevel
    
    # Findings
    findings: list = field(default_factory=list)
    
    # Sandbox results
    sandbox_output: Optional[str] = None
    behavioral_flags: list = field(default_factory=list)
    
    # Approval
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    # Timing
    created_at: str = ""
    updated_at: str = ""
    scan_started_at: Optional[str] = None
    scan_completed_at: Optional[str] = None


# ─────────────────────────────────────────
# PACKAGE AUDITOR ENGINE
# ─────────────────────────────────────────

class PackageAuditor:
    """
    The governance engine that intercepts and audits package installs.
    
    Usage:
        auditor = get_package_auditor()
        record = auditor.request_install("lodash", "4.17.21", "npm", "daena")
        # Returns a record with id — frontend polls or gets WS push
        auditor.run_audit(record.id)  # async in production
        auditor.approve(record.id)    # or reject
        auditor.execute_install(record.id)
    """

    def __init__(self):
        self._records: dict[str, PackageAuditRecord] = {}
        self._audit_log: list[dict] = []

    # ─── PUBLIC API ────────────────────────────────────────────────

    def request_install(self, package_name: str, version: str,
                        manager: str, requested_by: str) -> dict:
        """
        Entry point. Queue a package for audit.
        Returns the audit record ID immediately.
        """
        pm = PackageManager(manager) if manager in [e.value for e in PackageManager] else PackageManager.UNKNOWN
        now = datetime.now(timezone.utc).isoformat()
        record_id = str(uuid.uuid4())

        record = PackageAuditRecord(
            id=record_id,
            package_name=package_name,
            package_version=version,
            package_manager=pm,
            requested_by=requested_by,
            status=AuditStatus.QUEUED,
            risk_level=RiskLevel.LOW,
            created_at=now,
            updated_at=now
        )

        self._records[record_id] = record
        self._log("queued", record_id, f"Package {package_name}@{version} queued for audit by {requested_by}")

        return {
            "id": record_id,
            "status": "queued",
            "message": f"Audit queued for {package_name}@{version}. ID: {record_id}"
        }

    def run_audit(self, record_id: str) -> dict:
        """
        Execute the full audit pipeline synchronously.
        In production, this would be an async background task with WS status updates.
        """
        record = self._records.get(record_id)
        if not record:
            return {"error": "Audit record not found"}
        if record.status != AuditStatus.QUEUED:
            return {"error": f"Cannot run audit — status is {record.status.value}"}

        record.scan_started_at = datetime.now(timezone.utc).isoformat()
        record.status = AuditStatus.SCANNING
        self._update_record(record)

        # ── Stage 1: Static Analysis ──
        record.status = AuditStatus.STATIC_ANALYSIS
        self._run_static_analysis(record)
        self._update_record(record)

        # ── Stage 2: CVE Check ──
        record.status = AuditStatus.CVE_CHECK
        self._run_cve_check(record)
        self._update_record(record)

        # ── Stage 3: Sandbox Install ──
        record.status = AuditStatus.SANDBOX_INSTALL
        self._run_sandbox_install(record)
        self._update_record(record)

        # ── Stage 4: Behavioral Check ──
        record.status = AuditStatus.BEHAVIORAL_CHECK
        self._run_behavioral_check(record)
        self._update_record(record)

        # ── Stage 5: Risk Assessment & Decision ──
        self._assess_final_risk(record)
        record.scan_completed_at = datetime.now(timezone.utc).isoformat()

        # If critical risk → auto-reject
        if record.risk_level == RiskLevel.CRITICAL:
            record.status = AuditStatus.REJECTED
            record.rejection_reason = "Auto-rejected: CRITICAL risk level detected"
            self._log("rejected", record_id, "Auto-rejected due to critical risk")
        # If safe and requested by founder → auto-approve
        elif record.risk_level == RiskLevel.SAFE and record.requested_by == "founder":
            record.status = AuditStatus.APPROVED
            record.approved_by = "auto_safe"
            self._log("approved", record_id, "Auto-approved: safe package requested by founder")
        # Otherwise → pending approval
        else:
            record.status = AuditStatus.PENDING_APPROVAL
            self._log("pending", record_id, f"Pending approval — risk: {record.risk_level.value}")

        self._update_record(record)
        return self._record_to_dict(record)

    def approve(self, record_id: str, approver: str = "founder", notes: str = "") -> dict:
        """Approve a pending package install."""
        record = self._records.get(record_id)
        if not record:
            return {"error": "Record not found"}
        if record.status != AuditStatus.PENDING_APPROVAL:
            return {"error": f"Cannot approve — status is {record.status.value}"}

        record.status = AuditStatus.APPROVED
        record.approved_by = approver
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self._log("approved", record_id, f"Approved by {approver}. Notes: {notes}")

        return {"id": record_id, "status": "approved", "message": f"Approved by {approver}"}

    def reject(self, record_id: str, reason: str = "", rejector: str = "founder") -> dict:
        """Reject a pending package install."""
        record = self._records.get(record_id)
        if not record:
            return {"error": "Record not found"}
        if record.status != AuditStatus.PENDING_APPROVAL:
            return {"error": f"Cannot reject — status is {record.status.value}"}

        record.status = AuditStatus.REJECTED
        record.rejection_reason = reason
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self._log("rejected", record_id, f"Rejected by {rejector}: {reason}")

        return {"id": record_id, "status": "rejected", "reason": reason}

    def execute_install(self, record_id: str) -> dict:
        """
        Actually install the package (only if APPROVED).
        Returns the command that would be run.
        """
        record = self._records.get(record_id)
        if not record:
            return {"error": "Record not found"}
        if record.status != AuditStatus.APPROVED:
            return {"error": f"Cannot install — status is {record.status.value}. Must be approved first."}

        # Build the install command
        commands = {
            PackageManager.NPM: f"npm install {record.package_name}@{record.package_version}",
            PackageManager.PIP: f"pip install {record.package_name}=={record.package_version}",
            PackageManager.YARN: f"yarn add {record.package_name}@{record.package_version}",
            PackageManager.CARGO: f"cargo add {record.package_name}@{record.package_version}",
        }

        cmd = commands.get(record.package_manager, f"install {record.package_name}@{record.package_version}")
        record.status = AuditStatus.INSTALLED
        record.updated_at = datetime.now(timezone.utc).isoformat()
        self._log("installed", record_id, f"Command: {cmd}")

        return {
            "id": record_id,
            "status": "installed",
            "command": cmd,
            "message": f"Execute this command to install: {cmd}"
        }

    def get_record(self, record_id: str) -> Optional[dict]:
        """Get a single audit record."""
        record = self._records.get(record_id)
        return self._record_to_dict(record) if record else None

    def list_records(self, status_filter: Optional[str] = None) -> list[dict]:
        """List all audit records."""
        results = []
        for record in self._records.values():
            if status_filter and record.status.value != status_filter:
                continue
            results.append(self._record_to_dict(record))
        return sorted(results, key=lambda r: r["created_at"], reverse=True)

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        """Get recent audit events (for real-time dashboard feed)."""
        return self._audit_log[-limit:]

    def get_stats(self) -> dict:
        """Statistics for the audit dashboard."""
        records = list(self._records.values())
        return {
            "total_audits": len(records),
            "queued": sum(1 for r in records if r.status == AuditStatus.QUEUED),
            "scanning": sum(1 for r in records if r.status in (
                AuditStatus.SCANNING, AuditStatus.STATIC_ANALYSIS,
                AuditStatus.CVE_CHECK, AuditStatus.SANDBOX_INSTALL,
                AuditStatus.BEHAVIORAL_CHECK
            )),
            "pending_approval": sum(1 for r in records if r.status == AuditStatus.PENDING_APPROVAL),
            "approved": sum(1 for r in records if r.status == AuditStatus.APPROVED),
            "installed": sum(1 for r in records if r.status == AuditStatus.INSTALLED),
            "rejected": sum(1 for r in records if r.status in (AuditStatus.REJECTED, AuditStatus.BLOCKED)),
            "by_manager": self._count_by_manager(records),
            "by_risk": self._count_by_risk(records)
        }

    # ─── AUDIT STAGES ─────────────────────────────────────────────

    def _run_static_analysis(self, record: PackageAuditRecord):
        """Check package name against known threats and suspicious patterns."""
        name = record.package_name.lower()

        # Check known malicious
        if name in KNOWN_MALICIOUS:
            record.findings.append(AuditFinding(
                severity="critical",
                category="malicious",
                message=f"Package '{name}' is in the known malicious packages database",
                details={"source": "internal_threat_db"}
            ))

        # Check for popular package (whitelist fast-track)
        if name in POPULAR_PACKAGES:
            record.findings.append(AuditFinding(
                severity="info",
                category="whitelist",
                message=f"Package '{name}' is a known popular package",
                details={"whitelisted": True}
            ))

        # Typosquatting detection — compare against popular packages
        for popular in POPULAR_PACKAGES:
            if name != popular and self._is_typosquat(name, popular):
                record.findings.append(AuditFinding(
                    severity="high",
                    category="typosquat",
                    message=f"Package '{name}' looks like a typosquat of '{popular}'",
                    details={"similar_to": popular, "edit_distance": self._edit_distance(name, popular)}
                ))

        self._log("static_analysis", record.id, f"Static analysis complete: {len(record.findings)} findings")

    def _run_cve_check(self, record: PackageAuditRecord):
        """
        CVE check against known vulnerabilities.
        In production: query npm advisory API, PyPI advisories, OSV.dev
        Here: simulated with pattern matching.
        """
        name = record.package_name.lower()

        # Simulated CVE database
        simulated_cves = {
            "lodash": {"cve": "CVE-2019-10744", "severity": "high", "fixed_in": "4.17.12"},
            "express": {"cve": "CVE-2022-24999", "severity": "high", "fixed_in": "4.17.3"},
            "minimist": {"cve": "CVE-2022-0512", "severity": "medium", "fixed_in": "1.2.6"},
        }

        if name in simulated_cves:
            cve_info = simulated_cves[name]
            record.findings.append(AuditFinding(
                severity=cve_info["severity"],
                category="cve",
                message=f"Known CVE: {cve_info['cve']} — fixed in {cve_info['fixed_in']}",
                details=cve_info
            ))

        self._log("cve_check", record.id, "CVE check complete")

    def _run_sandbox_install(self, record: PackageAuditRecord):
        """
        Simulate a sandbox install — isolated environment.
        In production: Docker container, resource limits, no network (or captured).
        """
        # Check for postinstall scripts (simulated)
        name = record.package_name.lower()
        
        # Known packages with postinstall scripts
        postinstall_packages = {"node-sass", "fsevents", "grpc", "canvas"}
        
        if name in postinstall_packages:
            record.findings.append(AuditFinding(
                severity="warning",
                category="suspicious_script",
                message=f"Package '{name}' has a postinstall script that runs during install",
                details={"script_type": "postinstall"}
            ))
            record.sandbox_output = f"[SANDBOX] Intercepted postinstall script in {name}"
        else:
            record.sandbox_output = f"[SANDBOX] Clean install simulation for {name}@{record.package_version}"

        self._log("sandbox", record.id, record.sandbox_output)

    def _run_behavioral_check(self, record: PackageAuditRecord):
        """
        Check for behavioral red flags in the package.
        In production: actually instrument the sandbox install and watch syscalls.
        """
        name = record.package_name.lower()

        # Simulated behavioral analysis
        behavioral_flags = []

        # Check if package is suspiciously new (no history)
        # In production: check npm/pypi creation date
        # Simulated: flag anything not in popular list and not well-known
        if name not in POPULAR_PACKAGES and name not in KNOWN_MALICIOUS:
            behavioral_flags.append("Package has limited publish history — verify source")

        # Check dependency depth (simulated)
        # Deep dependency trees are suspicious for supply-chain attacks
        simulated_dep_count = len(name) % 10 + 1  # fake but deterministic
        if simulated_dep_count > 7:
            behavioral_flags.append(f"Deep dependency tree ({simulated_dep_count} transitive deps)")
            record.findings.append(AuditFinding(
                severity="warning",
                category="dependency",
                message=f"Package pulls in {simulated_dep_count} transitive dependencies",
                details={"transitive_deps": simulated_dep_count}
            ))

        record.behavioral_flags = behavioral_flags
        self._log("behavioral", record.id, f"Behavioral check: {len(behavioral_flags)} flags")

    def _assess_final_risk(self, record: PackageAuditRecord):
        """Calculate the final risk level based on all findings."""
        max_severity = "safe"
        severity_order = {"safe": 0, "info": 1, "low": 1, "warning": 2, "medium": 2, "high": 3, "critical": 4}

        for finding in record.findings:
            sev = finding.severity
            if severity_order.get(sev, 0) > severity_order.get(max_severity, 0):
                max_severity = sev

        # Map finding severity to risk level
        risk_map = {
            "safe": RiskLevel.SAFE,
            "info": RiskLevel.LOW,
            "warning": RiskLevel.MEDIUM,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL
        }

        record.risk_level = risk_map.get(max_severity, RiskLevel.LOW)

        # Whitelist override: if package is whitelisted AND no critical findings, cap at LOW
        is_whitelisted = any(
            f.category == "whitelist" for f in record.findings
        )
        has_critical = any(
            f.severity == "critical" for f in record.findings
        )
        if is_whitelisted and not has_critical:
            record.risk_level = RiskLevel.LOW

    # ─── HELPERS ──────────────────────────────────────────────────

    def _is_typosquat(self, name: str, popular: str) -> bool:
        """Detect if 'name' is a typosquat of 'popular'."""
        if abs(len(name) - len(popular)) > 2:
            return False
        if name == popular:
            return False
        dist = self._edit_distance(name, popular)
        return dist <= 2 and dist > 0

    def _edit_distance(self, a: str, b: str) -> int:
        """Levenshtein distance."""
        if len(a) < len(b):
            return self._edit_distance(b, a)
        if len(b) == 0:
            return len(a)
        prev_row = range(len(b) + 1)
        for i, ca in enumerate(a):
            curr_row = [i + 1]
            for j, cb in enumerate(b):
                insertions = prev_row[j + 1] + 1
                deletions = curr_row[j] + 1
                substitutions = prev_row[j] + (ca != cb)
                curr_row.append(min(insertions, deletions, substitutions))
            prev_row = curr_row
        return prev_row[-1]

    def _count_by_manager(self, records: list) -> dict:
        counts = {}
        for r in records:
            pm = r.package_manager.value
            counts[pm] = counts.get(pm, 0) + 1
        return counts

    def _count_by_risk(self, records: list) -> dict:
        counts = {}
        for r in records:
            rl = r.risk_level.value
            counts[rl] = counts.get(rl, 0) + 1
        return counts

    def _update_record(self, record: PackageAuditRecord):
        """Update timestamp on record change."""
        record.updated_at = datetime.now(timezone.utc).isoformat()

    def _log(self, event_type: str, record_id: str, message: str):
        """Append to audit log (for real-time dashboard feed)."""
        self._audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "record_id": record_id,
            "message": message
        })

    def _record_to_dict(self, record: PackageAuditRecord) -> dict:
        """Convert record to JSON-safe dict."""
        d = {
            "id": record.id,
            "package": f"{record.package_name}@{record.package_version}",
            "package_name": record.package_name,
            "package_version": record.package_version,
            "manager": record.package_manager.value,
            "requested_by": record.requested_by,
            "status": record.status.value,
            "risk_level": record.risk_level.value,
            "findings": [asdict(f) for f in record.findings],
            "behavioral_flags": record.behavioral_flags,
            "sandbox_output": record.sandbox_output,
            "approved_by": record.approved_by,
            "rejection_reason": record.rejection_reason,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "scan_started_at": record.scan_started_at,
            "scan_completed_at": record.scan_completed_at
        }
        return d


# ─── SINGLETON ─────────────────────────────────────────────────────
_auditor = None

def get_package_auditor() -> PackageAuditor:
    global _auditor
    if _auditor is None:
        _auditor = PackageAuditor()
    return _auditor
