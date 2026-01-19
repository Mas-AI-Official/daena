#!/usr/bin/env python3
"""
Security scan for secrets, API keys, and sensitive data.
Scans codebase for potential security issues.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any

# Patterns to detect secrets
SECRET_PATTERNS = [
    (r'password\s*=\s*["\']([^"\']+)["\']', "password"),
    (r'api[_-]?key\s*=\s*["\']([^"\']+)["\']', "api_key"),
    (r'secret[_-]?key\s*=\s*["\']([^"\']+)["\']', "secret_key"),
    (r'access[_-]?token\s*=\s*["\']([^"\']+)["\']', "access_token"),
    (r'private[_-]?key\s*=\s*["\']([^"\']+)["\']', "private_key"),
    (r'sk-[a-zA-Z0-9]{32,}', "openai_key"),
    (r'AIza[0-9A-Za-z-_]{35}', "google_api_key"),
    (r'AKIA[0-9A-Z]{16}', "aws_access_key"),
    (r'ghp_[a-zA-Z0-9]{36}', "github_token"),
    (r'xox[baprs]-[0-9a-zA-Z-]{10,}', "slack_token"),
    (r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', "private_key_file"),
]

# Files to exclude
EXCLUDE_PATTERNS = [
    r'\.git',
    r'__pycache__',
    r'\.pyc',
    r'node_modules',
    r'\.venv',
    r'venv_',
    r'\.env\.example',
    r'\.env\.template',
    r'CHANGELOG',
    r'README',
    r'\.md$',
    r'\.txt$',
    r'\.json$',  # Config files may have examples
]


def scan_file(file_path: Path) -> List[Dict[str, Any]]:
    """Scan a single file for secrets."""
    issues = []
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
            
            for line_num, line in enumerate(lines, 1):
                for pattern, secret_type in SECRET_PATTERNS:
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    for match in matches:
                        # Skip if it's clearly a placeholder
                        matched_text = match.group(0)
                        if any(placeholder in matched_text.lower() for placeholder in [
                            'your_', 'example_', 'placeholder', 'xxx', 'test-', 'demo'
                        ]):
                            continue
                        
                        issues.append({
                            "file": str(file_path),
                            "line": line_num,
                            "type": secret_type,
                            "match": matched_text[:50],  # Truncate for safety
                            "severity": "high" if secret_type in ["private_key", "access_token"] else "medium"
                        })
    except Exception as e:
        print(f"Error scanning {file_path}: {e}")
    
    return issues


def scan_directory(root: Path) -> List[Dict[str, Any]]:
    """Scan directory for secrets."""
    all_issues = []
    
    for file_path in root.rglob("*"):
        # Skip excluded paths
        if any(re.search(pattern, str(file_path)) for pattern in EXCLUDE_PATTERNS):
            continue
        
        # Only scan text files
        if file_path.is_file() and file_path.suffix in ['.py', '.js', '.ts', '.tsx', '.env', '.yaml', '.yml', '.json']:
            issues = scan_file(file_path)
            all_issues.extend(issues)
    
    return all_issues


def main():
    """Main entry point."""
    root = Path(__file__).parent.parent
    
    print("=" * 60)
    print("SECURITY SCAN - SECRETS DETECTION")
    print("=" * 60)
    print(f"Scanning: {root}")
    print()
    
    issues = scan_directory(root)
    
    if not issues:
        print("✅ No secrets detected in codebase")
        return 0
    
    # Group by severity
    high_severity = [i for i in issues if i["severity"] == "high"]
    medium_severity = [i for i in issues if i["severity"] == "medium"]
    
    print(f"⚠️  Found {len(issues)} potential security issues:")
    print(f"   High severity: {len(high_severity)}")
    print(f"   Medium severity: {len(medium_severity)}")
    print()
    
    if high_severity:
        print("HIGH SEVERITY ISSUES:")
        for issue in high_severity[:10]:  # Show first 10
            print(f"  {issue['file']}:{issue['line']} - {issue['type']}")
            print(f"    Match: {issue['match']}")
        if len(high_severity) > 10:
            print(f"  ... and {len(high_severity) - 10} more")
        print()
    
    if medium_severity:
        print("MEDIUM SEVERITY ISSUES:")
        for issue in medium_severity[:10]:  # Show first 10
            print(f"  {issue['file']}:{issue['line']} - {issue['type']}")
        if len(medium_severity) > 10:
            print(f"  ... and {len(medium_severity) - 10} more")
        print()
    
    # Save report
    report_path = root / "reports" / "security_scan.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    
    import json
    with open(report_path, 'w') as f:
        json.dump({
            "total_issues": len(issues),
            "high_severity": len(high_severity),
            "medium_severity": len(medium_severity),
            "issues": issues
        }, f, indent=2)
    
    print(f"📄 Full report saved to: {report_path}")
    print()
    
    if high_severity:
        print("❌ Security scan found high-severity issues. Please review and remove secrets.")
        return 1
    else:
        print("⚠️  Security scan found potential issues. Please review.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

