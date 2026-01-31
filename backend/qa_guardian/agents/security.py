"""
QA Security Agent - Security scanning capabilities

This agent is responsible for:
- Secret scanning (API keys, passwords, tokens)
- Dependency vulnerability scanning
- Basic static analysis
- Security reports
"""

import asyncio
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from backend.qa_guardian.schemas.agent_schemas import (
    SecurityInput, SecurityOutput, SecurityFinding
)

logger = logging.getLogger("qa_guardian.agents.security")


class QASecurityAgent:
    """
    QA Security Agent
    
    Performs security scanning for secrets, vulnerabilities, and code issues.
    
    Permission Boundaries:
    - CAN READ: All source files, config files, dependency files
    - CAN EXECUTE: Security scanning tools (detect-secrets, pip-audit)
    - CANNOT: Modify files, access actual secrets, make external calls
    """
    
    AGENT_ID = "qa_security_agent"
    DEPARTMENT = "qa_guardian"
    
    PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
    
    # Secret patterns to detect (for redaction)
    SECRET_PATTERNS = [
        (r'(?i)(api[_-]?key|apikey)["\s:=]+["\']?([a-zA-Z0-9_-]{20,})["\']?', 'api_key'),
        (r'(?i)(secret|password|passwd|pwd)["\s:=]+["\']?([^\s"\']{8,})["\']?', 'password'),
        (r'(?i)(token)["\s:=]+["\']?([a-zA-Z0-9_-]{20,})["\']?', 'token'),
        (r'Bearer\s+([a-zA-Z0-9_-]{20,})', 'bearer_token'),
        (r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+', 'jwt'),
        (r'sk-[a-zA-Z0-9]{48}', 'openai_key'),
        (r'ghp_[a-zA-Z0-9]{36}', 'github_pat'),
        (r'AKIA[A-Z0-9]{16}', 'aws_access_key'),
    ]
    
    # Files to always skip
    SKIP_PATTERNS = [
        '*.pyc', '__pycache__', '*.git*', 'venv*', 'node_modules',
        '*.whl', '*.egg-info', '*.so', '*.dll', '*.exe'
    ]
    
    def __init__(self):
        pass
    
    async def process(self, input: SecurityInput) -> SecurityOutput:
        """
        Perform security scanning based on input parameters.
        
        Args:
            input: SecurityInput specifying scan type and scope
            
        Returns:
            SecurityOutput with findings and summary
        """
        start_time = datetime.utcnow()
        
        try:
            findings: List[SecurityFinding] = []
            vulnerable_deps = []
            outdated_deps = []
            
            # Determine paths to scan
            scan_paths = input.paths if input.paths else [str(self.PROJECT_ROOT)]
            
            if input.scan_type in ["full", "secrets"]:
                secret_findings = await self._scan_for_secrets(scan_paths)
                findings.extend(secret_findings)
            
            if input.scan_type in ["full", "dependencies"]:
                dep_findings, vuln_deps = await self._scan_dependencies()
                findings.extend(dep_findings)
                vulnerable_deps = vuln_deps
            
            if input.scan_type in ["full", "static_analysis"]:
                static_findings = await self._run_static_analysis(scan_paths)
                findings.extend(static_findings)
            
            # Count severities
            critical_count = sum(1 for f in findings if f.severity == "critical")
            high_count = sum(1 for f in findings if f.severity == "high")
            medium_count = sum(1 for f in findings if f.severity == "medium")
            low_count = sum(1 for f in findings if f.severity == "low")
            
            # Determine verdicts
            secrets_clean = not any(f.category == "secret" for f in findings)
            dependencies_clean = not any(f.category == "vulnerability" for f in findings)
            code_clean = not any(f.category == "code_issue" for f in findings)
            
            # Generate immediate actions
            immediate_actions = self._generate_actions(findings, vulnerable_deps)
            
            exec_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return SecurityOutput(
                request_id=input.request_id,
                success=True,
                execution_time_ms=exec_time,
                total_findings=len(findings),
                critical_count=critical_count,
                high_count=high_count,
                medium_count=medium_count,
                low_count=low_count,
                secrets_clean=secrets_clean,
                dependencies_clean=dependencies_clean,
                code_clean=code_clean,
                findings=findings,
                vulnerable_dependencies=vulnerable_deps,
                outdated_dependencies=outdated_deps,
                immediate_actions=immediate_actions
            )
            
        except Exception as e:
            logger.error(f"Security agent error: {e}")
            return SecurityOutput(
                request_id=input.request_id,
                success=False,
                error=str(e),
                execution_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000)
            )
    
    async def _scan_for_secrets(self, paths: List[str]) -> List[SecurityFinding]:
        """Scan files for potential secrets"""
        findings = []
        finding_count = 0
        
        for path in paths:
            path_obj = Path(path)
            
            if path_obj.is_file():
                file_findings = await self._scan_file_for_secrets(path_obj)
                findings.extend(file_findings)
            elif path_obj.is_dir():
                # Walk directory
                for file_path in path_obj.rglob('*'):
                    if file_path.is_file() and self._should_scan_file(file_path):
                        file_findings = await self._scan_file_for_secrets(file_path)
                        findings.extend(file_findings)
                        
                        # Limit findings
                        if len(findings) > 100:
                            findings.append(SecurityFinding(
                                finding_id=f"sec_{finding_count}",
                                severity="info",
                                category="secret",
                                title="Scan limit reached",
                                description="More than 100 potential secrets found",
                                recommendation="Review individually"
                            ))
                            break
        
        return findings
    
    async def _scan_file_for_secrets(self, file_path: Path) -> List[SecurityFinding]:
        """Scan a single file for secrets"""
        findings = []
        
        try:
            content = file_path.read_text(errors='ignore')
            
            for pattern, secret_type in self.SECRET_PATTERNS:
                matches = re.finditer(pattern, content)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    
                    # Determine severity based on context
                    severity = "high" if secret_type in ['password', 'api_key', 'openai_key'] else "medium"
                    
                    # Don't report if in .env.example or similar
                    if 'example' in str(file_path).lower():
                        severity = "low"
                    
                    findings.append(SecurityFinding(
                        finding_id=f"sec_{len(findings)}",
                        severity=severity,
                        category="secret",
                        title=f"Potential {secret_type} detected",
                        description=f"Found pattern matching {secret_type} in file",
                        file_path=str(file_path.relative_to(self.PROJECT_ROOT)),
                        line_number=line_num,
                        recommendation=f"Verify if this is an actual {secret_type}. If so, rotate it and use environment variables."
                    ))
                    
        except Exception as e:
            logger.debug(f"Could not scan {file_path}: {e}")
        
        return findings
    
    def _should_scan_file(self, file_path: Path) -> bool:
        """Check if file should be scanned"""
        # Skip binary files
        binary_extensions = ['.pyc', '.whl', '.egg', '.so', '.dll', '.exe', 
                           '.png', '.jpg', '.gif', '.wav', '.mp3', '.zip', '.db']
        if file_path.suffix.lower() in binary_extensions:
            return False
        
        # Skip large files
        try:
            if file_path.stat().st_size > 1_000_000:  # 1MB
                return False
        except:
            return False
        
        # Skip venv and cache
        path_str = str(file_path).lower()
        if any(skip in path_str for skip in ['venv', '__pycache__', '.git', 'node_modules']):
            return False
        
        return True
    
    async def _scan_dependencies(self) -> tuple[List[SecurityFinding], List[Dict]]:
        """Scan dependencies for vulnerabilities"""
        findings = []
        vulnerable_deps = []
        
        try:
            # Try pip-audit
            cmd = [sys.executable, "-m", "pip_audit", "--format=json"]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=120
            )
            
            if stdout:
                import json
                try:
                    results = json.loads(stdout.decode())
                    for vuln in results:
                        severity = "critical" if "critical" in str(vuln).lower() else "high"
                        
                        findings.append(SecurityFinding(
                            finding_id=f"dep_{len(findings)}",
                            severity=severity,
                            category="vulnerability",
                            title=f"Vulnerable package: {vuln.get('name', 'unknown')}",
                            description=vuln.get('description', 'Vulnerability detected'),
                            recommendation=f"Upgrade to {vuln.get('fix_versions', 'latest')}",
                            cve_id=vuln.get('cve_id')
                        ))
                        
                        vulnerable_deps.append(vuln)
                except json.JSONDecodeError:
                    pass
                    
        except asyncio.TimeoutError:
            findings.append(SecurityFinding(
                finding_id="dep_timeout",
                severity="info",
                category="vulnerability",
                title="Dependency scan timed out",
                description="pip-audit took too long",
                recommendation="Run manually: pip-audit"
            ))
        except Exception as e:
            logger.debug(f"pip-audit not available: {e}")
        
        return findings, vulnerable_deps
    
    async def _run_static_analysis(self, paths: List[str]) -> List[SecurityFinding]:
        """Run basic static analysis for security issues"""
        findings = []
        
        # Common security anti-patterns
        security_patterns = [
            (r'eval\s*\(', 'eval_usage', 'Use of eval() is dangerous'),
            (r'exec\s*\(', 'exec_usage', 'Use of exec() is dangerous'),
            (r'subprocess\.call\s*\([^)]*shell\s*=\s*True', 'shell_injection', 'Shell injection risk'),
            (r'pickle\.loads?\s*\(', 'pickle_deserialization', 'Pickle deserialization can be exploited'),
            (r'yaml\.load\s*\([^)]*\)', 'unsafe_yaml', 'Use yaml.safe_load instead'),
            (r'\.execute\s*\([^)]*[+%]', 'sql_injection', 'Potential SQL injection'),
        ]
        
        for path in paths:
            path_obj = Path(path)
            
            if path_obj.is_dir():
                for file_path in path_obj.rglob('*.py'):
                    if self._should_scan_file(file_path):
                        try:
                            content = file_path.read_text(errors='ignore')
                            
                            for pattern, issue_type, description in security_patterns:
                                matches = re.finditer(pattern, content)
                                for match in matches:
                                    line_num = content[:match.start()].count('\n') + 1
                                    
                                    findings.append(SecurityFinding(
                                        finding_id=f"static_{len(findings)}",
                                        severity="medium",
                                        category="code_issue",
                                        title=issue_type.replace('_', ' ').title(),
                                        description=description,
                                        file_path=str(file_path.relative_to(self.PROJECT_ROOT)),
                                        line_number=line_num,
                                        recommendation=f"Review and refactor to avoid {issue_type}"
                                    ))
                                    
                        except Exception as e:
                            logger.debug(f"Could not analyze {file_path}: {e}")
        
        return findings
    
    def _generate_actions(self, findings: List[SecurityFinding], 
                          vulnerable_deps: List[Dict]) -> List[str]:
        """Generate immediate action items"""
        actions = []
        
        critical = [f for f in findings if f.severity == "critical"]
        high = [f for f in findings if f.severity == "high"]
        
        if critical:
            actions.append(f"🔴 CRITICAL: {len(critical)} critical issues require immediate attention")
        
        if high:
            actions.append(f"🟠 HIGH: {len(high)} high-severity issues should be addressed soon")
        
        if vulnerable_deps:
            actions.append(f"📦 Update {len(vulnerable_deps)} vulnerable dependencies")
        
        secrets = [f for f in findings if f.category == "secret"]
        if secrets:
            actions.append(f"🔑 Review {len(secrets)} potential secrets and rotate if needed")
        
        return actions
