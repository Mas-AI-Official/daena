"""Tests for Trivy + Nuclei dispatch in real_scanner (gap-fill pack).

These tests do NOT require the real binaries. They monkey-patch
``shutil.which`` to report the binary as present, then stub
``subprocess.run`` / the JSON writer so the parsers run against
canned output. Asserts:

    * Trivy vuln + misconfig + secret output shapes map to findings.
    * Nuclei JSONL output maps to findings with CVE/CWE refs.
    * Findings carry ``source_tool`` and ``evidence_chain_id`` so the
      Zero-FP gate auto-admits them.
    * Post-install hook dispatcher returns ``ran=True`` only for
      tools that have an entry (nuclei, trivy) and no-ops for the rest.
"""

from __future__ import annotations

import json
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.security import real_scanner as rs


def _trivy_canned_output():
    return {
        "Results": [
            {
                "Target": "package.json",
                "Vulnerabilities": [
                    {
                        "VulnerabilityID": "CVE-2024-1234",
                        "PkgName": "lodash",
                        "InstalledVersion": "4.17.20",
                        "FixedVersion": "4.17.21",
                        "Severity": "HIGH",
                        "Title": "Prototype pollution in lodash",
                        "Description": "lodash < 4.17.21 has prototype pollution",
                        "CweIDs": ["CWE-1321"],
                    }
                ],
                "Misconfigurations": [
                    {
                        "ID": "AVD-DS-0001",
                        "Title": "Dockerfile runs as root",
                        "Description": "Containers should not run as root",
                        "Severity": "MEDIUM",
                        "Message": "add USER directive",
                        "Resolution": "Add a USER line with a non-root user",
                        "Type": "dockerfile",
                        "CauseMetadata": {"StartLine": 7},
                    }
                ],
                "Secrets": [
                    {
                        "RuleID": "aws-access-key",
                        "Title": "AWS key exposed",
                        "Severity": "CRITICAL",
                        "StartLine": 12,
                        "Match": "AKIAIOSFODNN7EXAMPLE",
                    }
                ],
            }
        ]
    }


def _nuclei_canned_jsonl():
    lines = [
        {
            "template-id": "exposed-env-file",
            "matched-at": "https://target.example/.env",
            "matcher-name": "word",
            "type": "http",
            "info": {
                "name": ".env file exposure",
                "severity": "critical",
                "description": "Publicly accessible .env with secrets",
                "reference": ["https://owasp.org/www-community/Exposure_of_Sensitive_Information"],
                "classification": {
                    "cve-id": ["CVE-2021-XXXX"],
                    "cwe-id": ["CWE-538"],
                },
            },
        },
        {
            "template-id": "missing-security-headers",
            "matched-at": "https://target.example/",
            "info": {
                "name": "Missing CSP header",
                "severity": "low",
                "description": "No Content-Security-Policy header set",
                "reference": [],
            },
        },
    ]
    return "\n".join(json.dumps(l) for l in lines)


def test_trivy_parser_maps_vuln_misconfig_secret(tmp_path, monkeypatch):
    # Pretend trivy is on PATH
    monkeypatch.setattr(rs.shutil, "which", lambda x: "/fake/trivy" if x == "trivy" else None)
    canned = _trivy_canned_output()

    def fake_run(cmd, *a, **kw):
        # Trivy writes JSON to --output path; we write canned data there
        out_idx = cmd.index("--output") + 1
        with open(cmd[out_idx], "w", encoding="utf-8") as f:
            json.dump(canned, f)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(rs.subprocess, "run", fake_run)
    findings = rs._run_trivy_fs(str(tmp_path))
    kinds = {f.source_tool for f in findings}
    assert kinds == {"trivy"}, f"unexpected tools: {kinds}"
    rule_ids = [f.source_rule for f in findings]
    assert any(r.startswith("trivy:CVE-") for r in rule_ids), f"no CVE: {rule_ids}"
    assert any(r.startswith("trivy-misconfig:") for r in rule_ids), f"no misconfig: {rule_ids}"
    assert any(r.startswith("trivy-secret:") for r in rule_ids), f"no secret: {rule_ids}"
    # Every finding has evidence_chain_id so Zero-FP gate auto-admits
    for f in findings:
        assert f.evidence_chain_id, f"missing evidence: {f}"


def test_trivy_skipped_when_binary_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(rs.shutil, "which", lambda x: None)
    findings = rs._run_trivy_fs(str(tmp_path))
    assert findings == []


def test_nuclei_parser_maps_jsonl(monkeypatch):
    monkeypatch.setattr(rs.shutil, "which", lambda x: "/fake/nuclei" if x == "nuclei" else None)
    canned_stdout = _nuclei_canned_jsonl()

    def fake_run(cmd, *a, **kw):
        return SimpleNamespace(returncode=0, stdout=canned_stdout, stderr="")

    monkeypatch.setattr(rs.subprocess, "run", fake_run)
    findings = rs._run_nuclei("https://target.example/")
    assert len(findings) == 2
    critical = [f for f in findings if f.severity == "CRITICAL"]
    assert len(critical) == 1
    assert "CVE-2021-XXXX" in critical[0].cve_references
    assert "CWE-538" in critical[0].cve_references
    for f in findings:
        assert f.source_tool == "nuclei"
        assert f.evidence_chain_id.startswith("nuclei-")


def test_nuclei_skipped_when_binary_missing(monkeypatch):
    monkeypatch.setattr(rs.shutil, "which", lambda x: None)
    assert rs._run_nuclei("https://target.example/") == []


def test_post_install_hook_map_covers_nuclei_and_trivy():
    from app.api.v1 import security_dashboard as dash
    assert "nuclei" in dash._POST_INSTALL_HOOKS
    assert "trivy" in dash._POST_INSTALL_HOOKS
    assert "semgrep" not in dash._POST_INSTALL_HOOKS  # fetches on demand


def test_post_install_hook_noop_for_other_tools(monkeypatch):
    from app.api.v1 import security_dashboard as dash
    # Unknown tool -> no command, ran=False
    result = dash._run_post_install_hook("bandit")
    assert result["ran"] is False


def test_post_install_hook_runs_for_nuclei(monkeypatch):
    from app.api.v1 import security_dashboard as dash
    calls = []

    def fake_run(cmd, *a, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(dash.subprocess, "run", fake_run)
    result = dash._run_post_install_hook("nuclei")
    assert result["ran"] is True
    assert result["ok"] is True
    assert calls, "subprocess.run should have been invoked"
    assert "nuclei" in calls[0] and "-update-templates" in calls[0]
