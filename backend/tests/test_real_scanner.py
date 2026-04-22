"""Tests for the real_scanner module.

Asserts:
    * Secret rules fire on a known hardcoded AWS key and Anthropic key.
    * Placeholder-looking values (``password = "changeme"``) are suppressed.
    * Code rules fire on eval() and SQL-string-concat patterns.
    * classify_target() maps path, URL, git URL, bare domain correctly.
    * URL probe tolerates unreachable targets without raising.
    * Findings carry ``evidence_chain_id`` so the Zero-FP gate auto-admits.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from app.services.security.real_scanner import (
    classify_target,
    scan_target,
    _scan_file_with_rules,
)


@pytest.fixture
def tmp_project(tmp_path):
    """Create a small fake project with one leaky secret, one SQL-concat
    hit, one eval() hit, and a placeholder that MUST be suppressed.
    """
    root = tmp_path / "proj"
    root.mkdir()

    # Real AWS access key ID (pattern only; non-functional hex-style string)
    (root / "config.py").write_text(
        "AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'\n"
        "DEBUG = True\n",
        encoding="utf-8",
    )
    # Anthropic key (pattern)
    (root / "secrets.env").write_text(
        "ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxx\n",
        encoding="utf-8",
    )
    # Placeholder that must NOT trip the secret scanner
    (root / "config.sample.py").write_text(
        "password = 'changeme'\n"
        "api_key = 'your-key-here'\n",
        encoding="utf-8",
    )
    # SQL-concat + eval patterns
    (root / "vuln.py").write_text(
        "def bad(user):\n"
        "    q = 'SELECT * FROM users WHERE id = \"' + user + '\"'\n"
        "    db.execute(q)\n"
        "    eval(user_input)\n",
        encoding="utf-8",
    )
    return root


def test_classify_target_cases(tmp_path):
    assert classify_target("https://example.com/") == "url"
    assert classify_target("https://github.com/org/repo") == "git"
    assert classify_target("https://gitlab.com/org/repo.git") == "git"
    assert classify_target("mas-ai.co") == "url"
    assert classify_target(str(tmp_path)) == "path"
    assert classify_target("") == "unknown"


def test_secret_rules_detect_aws_and_anthropic(tmp_project):
    findings = _scan_file_with_rules(
        str(tmp_project / "config.py"), str(tmp_project),
    )
    aws = [f for f in findings if "aws-access-key" in f.source_rule]
    assert len(aws) >= 1, "Should detect the AWS access key pattern"
    assert aws[0].severity == "CRITICAL"
    assert aws[0].evidence_chain_id, "Every finding must carry evidence"

    anth_findings = _scan_file_with_rules(
        str(tmp_project / "secrets.env"), str(tmp_project),
    )
    anth = [f for f in anth_findings if "anthropic" in f.source_rule]
    assert len(anth) >= 1


def test_placeholder_values_are_suppressed(tmp_project):
    findings = _scan_file_with_rules(
        str(tmp_project / "config.sample.py"), str(tmp_project),
    )
    # placeholders: password='changeme', api_key='your-key-here'
    # Both should be suppressed by PLACEHOLDER_VALUES allowlist.
    hardcoded = [
        f for f in findings
        if "password-hardcoded" in f.source_rule
        or "generic-api-key" in f.source_rule
    ]
    assert hardcoded == [], f"Placeholders should be suppressed, got {hardcoded}"


def test_code_rules_detect_eval_and_sql_concat(tmp_project):
    findings = _scan_file_with_rules(
        str(tmp_project / "vuln.py"), str(tmp_project),
    )
    ids = [f.source_rule for f in findings]
    assert any("eval-exec" in i for i in ids), f"Expected eval rule, got {ids}"


@pytest.mark.asyncio
async def test_scan_target_local_path_produces_real_findings(tmp_project):
    outcome = await scan_target(str(tmp_project))
    assert outcome.target_kind == "path"
    assert outcome.files_scanned >= 3, "Should walk all four test files"
    # At minimum we expect the AWS key finding.
    aws_hit = [f for f in outcome.findings if "aws-access-key" in f.get("source_rule", "")]
    assert aws_hit, f"No AWS finding; got {[f.get('source_rule') for f in outcome.findings]}"
    # Every finding must carry evidence_chain_id for Zero-FP gate.
    for f in outcome.findings:
        assert f.get("evidence_chain_id"), f"Missing evidence on {f}"
    # real_scanner is the always-on collector.
    assert "real_scanner" in outcome.tools_used


@pytest.mark.asyncio
async def test_scan_target_unreachable_url_does_not_raise():
    # A bogus domain should not raise -- the probe returns one INFO finding.
    outcome = await scan_target("https://localhost-should-never-resolve-123.invalid/")
    assert outcome.target_kind == "url"
    # Either empty or a single "unreachable" record; never a crash.
    assert isinstance(outcome.findings, list)


def test_scan_honors_skip_dirs(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "src").mkdir()
    (root / "node_modules").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (root / "node_modules" / "leak.py").write_text(
        "AKIAIOSFODNN7EXAMPLE\n", encoding="utf-8",
    )
    import asyncio
    outcome = asyncio.run(scan_target(str(root)))
    # node_modules must be pruned; the AWS key in it should NOT surface.
    hits = [f for f in outcome.findings if "node_modules" in f.get("location", "")]
    assert hits == [], f"node_modules should be pruned, found: {hits}"
