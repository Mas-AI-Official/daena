#!/usr/bin/env python3
"""
Daena Security Audit - Secrets Scanner
Scans the entire repo for hardcoded secrets, API keys, and sensitive data.

Output: JSON report with file, line, severity, masked value
"""

import os
import re
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Secret patterns with severity levels
SECRET_PATTERNS = {
    # API Keys
    "azure_openai_key": {
        "pattern": r"(?i)(azure[_-]?openai[_-]?(?:api[_-]?)?key|AZURE_OPENAI_API_KEY)\s*[=:]\s*['\"]?([a-zA-Z0-9]{20,})['\"]?",
        "severity": "CRITICAL",
        "description": "Azure OpenAI API Key"
    },
    "openai_key": {
        "pattern": r"(?i)(sk-[a-zA-Z0-9]{20,})",
        "severity": "CRITICAL",
        "description": "OpenAI API Key"
    },
    "anthropic_key": {
        "pattern": r"(?i)(sk-ant-[a-zA-Z0-9]{20,})",
        "severity": "CRITICAL",
        "description": "Anthropic API Key"
    },
    "huggingface_token": {
        "pattern": r"(?i)(hf_[a-zA-Z0-9]{20,})",
        "severity": "CRITICAL",
        "description": "HuggingFace Token"
    },
    "google_api_key": {
        "pattern": r"(?i)(AIza[a-zA-Z0-9_-]{35})",
        "severity": "HIGH",
        "description": "Google API Key"
    },
    "aws_access_key": {
        "pattern": r"(?i)(AKIA[A-Z0-9]{16})",
        "severity": "CRITICAL",
        "description": "AWS Access Key"
    },
    "aws_secret_key": {
        "pattern": r"(?i)(aws[_-]?secret[_-]?(?:access[_-]?)?key)\s*[=:]\s*['\"]?([a-zA-Z0-9/+=]{40})['\"]?",
        "severity": "CRITICAL",
        "description": "AWS Secret Key"
    },
    
    # Tokens
    "generic_token": {
        "pattern": r"(?i)(token|api[_-]?key|secret[_-]?key|auth[_-]?key)\s*[=:]\s*['\"]([a-zA-Z0-9_-]{20,})['\"]",
        "severity": "MEDIUM",
        "description": "Generic Token/Key"
    },
    "bearer_token": {
        "pattern": r"(?i)bearer\s+([a-zA-Z0-9_-]{20,})",
        "severity": "HIGH",
        "description": "Bearer Token"
    },
    
    # Passwords
    "password_assignment": {
        "pattern": r"(?i)(password|passwd|pwd|secret)\s*[=:]\s*['\"]([^'\"]{8,})['\"]",
        "severity": "HIGH",
        "description": "Password Assignment"
    },
    
    # Connection Strings
    "connection_string": {
        "pattern": r"(?i)(mongodb\+srv|postgresql|mysql|redis|amqp)://[^'\"\s]+",
        "severity": "HIGH",
        "description": "Database Connection String"
    },
    
    # Private Keys
    "private_key_header": {
        "pattern": r"-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----",
        "severity": "CRITICAL",
        "description": "Private Key File Content"
    },
    
    # Discord/Telegram
    "discord_token": {
        "pattern": r"(?i)(discord[_-]?(?:bot[_-]?)?token)\s*[=:]\s*['\"]?([a-zA-Z0-9._-]{50,})['\"]?",
        "severity": "HIGH",
        "description": "Discord Bot Token"
    },
    "telegram_token": {
        "pattern": r"(?i)(\d{9,10}:[a-zA-Z0-9_-]{35})",
        "severity": "HIGH",
        "description": "Telegram Bot Token"
    },
    
    # Crypto
    "ethereum_private_key": {
        "pattern": r"(0x)?[a-fA-F0-9]{64}",
        "severity": "CRITICAL",
        "description": "Possible Ethereum Private Key"
    },
}

# Files/directories to skip
SKIP_PATTERNS = [
    r"\.git/",
    r"__pycache__/",
    r"node_modules/",
    r"\.venv/",
    r"venv/",
    r"\.pyc$",
    r"\.so$",
    r"\.dll$",
    r"\.exe$",
    r"\.bin$",
    r"\.safetensors$",
    r"\.gguf$",
    r"\.db$",
    r"\.db-wal$",
    r"\.db-shm$",
    r"\.png$",
    r"\.jpg$",
    r"\.jpeg$",
    r"\.gif$",
    r"\.ico$",
    r"\.woff$",
    r"\.ttf$",
    r"\.mp3$",
    r"\.wav$",
    r"\.mp4$",
    r"\.webm$",
    r"\.pdf$",
    r"\.docx$",
    r"secrets_audit\.py$",  # Skip self
    r"\.env\.example$",  # Skip example files
]

# False positive patterns to ignore
FALSE_POSITIVES = [
    r"your[_-]?api[_-]?key[_-]?here",
    r"PLACEHOLDER",
    r"ROTATE_ME",
    r"your[_-]?.*[_-]?here",
    r"example\.com",
    r"localhost",
    r"127\.0\.0\.1",
    r"test[_-]?key",
    r"dummy",
    r"sample",
    r"xxxxxxxx",
    r"00000000",
]


def should_skip_file(filepath: str) -> bool:
    """Check if file should be skipped."""
    for pattern in SKIP_PATTERNS:
        if re.search(pattern, filepath, re.IGNORECASE):
            return True
    return False


def is_false_positive(value: str) -> bool:
    """Check if a match is a false positive."""
    for pattern in FALSE_POSITIVES:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    return False


def mask_secret(secret: str) -> str:
    """Mask a secret for safe display."""
    if len(secret) <= 8:
        return "*" * len(secret)
    return secret[:4] + "*" * (len(secret) - 8) + secret[-4:]


def scan_file(filepath: str) -> List[Dict[str, Any]]:
    """Scan a single file for secrets."""
    findings = []
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
    except Exception as e:
        return findings
    
    for pattern_name, pattern_info in SECRET_PATTERNS.items():
        try:
            matches = re.finditer(pattern_info["pattern"], content)
            for match in matches:
                # Get the matched value
                groups = match.groups()
                secret_value = groups[-1] if groups else match.group(0)
                
                # Skip false positives
                if is_false_positive(secret_value):
                    continue
                
                # Skip if too short (likely false positive)
                if len(secret_value) < 8:
                    continue
                
                # Find line number
                start_pos = match.start()
                line_number = content[:start_pos].count('\n') + 1
                
                # Get context (the line)
                line_content = lines[line_number - 1] if line_number <= len(lines) else ""
                
                findings.append({
                    "file": filepath,
                    "line": line_number,
                    "pattern": pattern_name,
                    "severity": pattern_info["severity"],
                    "description": pattern_info["description"],
                    "masked_value": mask_secret(secret_value),
                    "context": line_content[:100] + ("..." if len(line_content) > 100 else "")
                })
        except Exception as e:
            continue
    
    return findings


def scan_directory(root_path: str) -> Dict[str, Any]:
    """Scan entire directory for secrets."""
    all_findings = []
    files_scanned = 0
    files_skipped = 0
    
    root = Path(root_path)
    
    for filepath in root.rglob("*"):
        if filepath.is_file():
            rel_path = str(filepath.relative_to(root))
            
            if should_skip_file(rel_path):
                files_skipped += 1
                continue
            
            findings = scan_file(str(filepath))
            all_findings.extend(findings)
            files_scanned += 1
    
    # Sort by severity
    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    all_findings.sort(key=lambda x: severity_order.get(x["severity"], 4))
    
    return {
        "scan_date": datetime.now().isoformat(),
        "root_path": root_path,
        "files_scanned": files_scanned,
        "files_skipped": files_skipped,
        "total_findings": len(all_findings),
        "findings_by_severity": {
            "CRITICAL": len([f for f in all_findings if f["severity"] == "CRITICAL"]),
            "HIGH": len([f for f in all_findings if f["severity"] == "HIGH"]),
            "MEDIUM": len([f for f in all_findings if f["severity"] == "MEDIUM"]),
            "LOW": len([f for f in all_findings if f["severity"] == "LOW"]),
        },
        "findings": all_findings
    }


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Scan repository for secrets")
    parser.add_argument("path", nargs="?", default=".", help="Path to scan (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument("--fail-on-critical", action="store_true", help="Exit with code 1 if CRITICAL findings")
    parser.add_argument("--fail-on-high", action="store_true", help="Exit with code 1 if HIGH or CRITICAL findings")
    
    args = parser.parse_args()
    
    print(f"🔍 Scanning {args.path} for secrets...")
    report = scan_directory(args.path)
    
    if args.json or args.output:
        output = json.dumps(report, indent=2)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(output)
            print(f"✅ Report written to {args.output}")
        else:
            print(output)
    else:
        # Pretty print
        print(f"\n{'='*60}")
        print(f"DAENA SECRETS AUDIT REPORT")
        print(f"{'='*60}")
        print(f"Scan Date: {report['scan_date']}")
        print(f"Files Scanned: {report['files_scanned']}")
        print(f"Files Skipped: {report['files_skipped']}")
        print(f"\nFindings Summary:")
        print(f"  🔴 CRITICAL: {report['findings_by_severity']['CRITICAL']}")
        print(f"  🟠 HIGH: {report['findings_by_severity']['HIGH']}")
        print(f"  🟡 MEDIUM: {report['findings_by_severity']['MEDIUM']}")
        print(f"  🔵 LOW: {report['findings_by_severity']['LOW']}")
        
        if report['findings']:
            print(f"\n{'='*60}")
            print("DETAILED FINDINGS")
            print(f"{'='*60}\n")
            
            for finding in report['findings']:
                severity_emoji = {
                    "CRITICAL": "🔴",
                    "HIGH": "🟠",
                    "MEDIUM": "🟡",
                    "LOW": "🔵"
                }.get(finding['severity'], "⚪")
                
                print(f"{severity_emoji} [{finding['severity']}] {finding['description']}")
                print(f"   File: {finding['file']}:{finding['line']}")
                print(f"   Value: {finding['masked_value']}")
                print(f"   Context: {finding['context']}")
                print()
        else:
            print("\n✅ No secrets found!")
    
    # Exit codes
    if args.fail_on_critical and report['findings_by_severity']['CRITICAL'] > 0:
        sys.exit(1)
    if args.fail_on_high and (report['findings_by_severity']['CRITICAL'] > 0 or report['findings_by_severity']['HIGH'] > 0):
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
