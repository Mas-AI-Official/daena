"""Tests for PoC artifact builders + Zero-FP gate PoC-requirement flag.

Covers all 7 builder functions, SHA-256 determinism, content-type
correctness, safety-flag logic, and the new require_poc_artifact
gate behavior. These tests are pure-function where possible (no I/O)
so they run in milliseconds.
"""

from __future__ import annotations

import hashlib

import pytest

from app.services.security.poc_artifact import (
    PocArtifact,
    PocKind,
    build_behavioral_trace_poc,
    build_curl_poc,
    build_diff_hunk_poc,
    build_http_pair_poc,
    build_package_reference_poc,
    build_replay_script_poc,
    verify_artifact_integrity,
)
from app.services.security.report_tiers import ReportTier
from app.services.security.zero_fp_gate import apply_gate


# ----------------------------------------------------------------------
# PocArtifact core
# ----------------------------------------------------------------------


def test_sha256_computed_on_construction():
    a = PocArtifact(
        finding_id="F1",
        kind=PocKind.CURL,
        content=b"curl https://example.com",
        content_type="text/x-shellscript",
    )
    assert len(a.sha256) == 64
    assert a.sha256 == hashlib.sha256(b"curl https://example.com").hexdigest()


def test_created_at_iso_populated_on_construction():
    a = PocArtifact(
        finding_id="F2", kind=PocKind.CURL,
        content=b"x", content_type="text/plain",
    )
    # ISO 8601 starts with YYYY-MM-DD
    assert len(a.created_at) >= 19
    assert a.created_at[4] == "-" and a.created_at[7] == "-"


def test_safe_handover_defaults():
    """CURL/HTTP_PAIR/SCREENSHOT/PACKAGE_REF/DIFF_HUNK/TRACE = safe.
    REPLAY_SCRIPT = not safe.
    """
    curl = build_curl_poc("F", curl_command="curl x", target="x")
    assert curl.safe_handover is True

    script = build_replay_script_poc(
        "F", script_body="rm x", language="bash", target="x",
    )
    assert script.safe_handover is False


def test_destructive_flag_overrides_safe_handover():
    """Even a CURL is not safe-handover if marked destructive."""
    a = build_curl_poc(
        "F", curl_command="curl -X DELETE x", target="x",
        destructive=True,
    )
    assert a.safe_handover is False


def test_to_dict_excludes_content_by_default():
    a = build_curl_poc("F", curl_command="curl x", target="x")
    d = a.to_dict()
    assert "content" not in d
    assert d["sha256"] == a.sha256


def test_to_dict_includes_content_when_requested():
    a = build_curl_poc("F", curl_command="curl http://x", target="x")
    d = a.to_dict(include_content=True)
    assert d["content"] == "curl http://x"


def test_to_dict_base64_encodes_binary_content():
    binary = bytes(range(256))
    a = PocArtifact(
        finding_id="F",
        kind=PocKind.SCREENSHOT,
        content=binary,
        content_type="image/png",
    )
    d = a.to_dict(include_content=True)
    assert d.get("content_encoding") == "base64"


# ----------------------------------------------------------------------
# Builder functions
# ----------------------------------------------------------------------


def test_build_curl_poc_sets_kind_and_content_type():
    a = build_curl_poc("F1", curl_command="curl x", target="x")
    assert a.kind == PocKind.CURL
    assert a.content_type == "text/x-shellscript"
    assert a.reproducible is True


def test_build_http_pair_poc_embeds_markers():
    a = build_http_pair_poc(
        "F2",
        request_raw="GET / HTTP/1.1\r\nHost: x\r\n\r\n",
        response_raw="HTTP/1.1 200 OK\r\n\r\nok",
        target="http://x",
    )
    assert a.kind == PocKind.HTTP_PAIR
    text = a.content.decode("utf-8")
    assert "---REQUEST---" in text
    assert "---RESPONSE---" in text
    assert a.reproducible is False


def test_build_package_reference_poc_json_payload():
    a = build_package_reference_poc(
        "F3",
        ecosystem="npm",
        package_name="event-stream",
        version="3.3.6",
        observed_hash="a" * 64,
        expected_hash="b" * 64,
    )
    assert a.kind == PocKind.PACKAGE_REFERENCE
    assert a.content_type == "application/json"
    import json as _json
    payload = _json.loads(a.content)
    assert payload["package"] == "event-stream"
    assert payload["hash_matches"] is False
    assert a.metadata["ecosystem"] == "npm"


def test_build_package_reference_matches_when_hashes_equal():
    a = build_package_reference_poc(
        "F4",
        ecosystem="pypi",
        package_name="requests",
        version="2.31.0",
        observed_hash="c" * 64,
        expected_hash="c" * 64,
    )
    import json as _json
    payload = _json.loads(a.content)
    assert payload["hash_matches"] is True


def test_build_diff_hunk_poc_uses_language_content_type():
    a = build_diff_hunk_poc(
        "F5",
        file_path="app/api.py",
        hunk="query = f\"SELECT * FROM t WHERE n = {name}\"",
        language="python",
    )
    assert a.kind == PocKind.DIFF_HUNK
    assert "python" in a.content_type
    assert a.metadata["file_path"] == "app/api.py"


def test_build_behavioral_trace_poc_text_content():
    a = build_behavioral_trace_poc(
        "F6",
        trace_summary="connect(3.16.45.1:80); exec(/bin/sh)",
        target="sandboxed_postinstall",
    )
    assert a.kind == PocKind.BEHAVIORAL_TRACE
    assert a.content_type == "text/plain"


def test_build_replay_script_poc_sets_destructive_default():
    a = build_replay_script_poc(
        "F7",
        script_body="#!/bin/bash\nrm -rf target/",
        language="bash",
        target="target/",
    )
    assert a.kind == PocKind.REPLAY_SCRIPT
    assert a.destructive is True  # Default for replay scripts
    assert a.safe_handover is False


# ----------------------------------------------------------------------
# Integrity verification
# ----------------------------------------------------------------------


def test_verify_artifact_integrity_detects_tamper():
    a = build_curl_poc("F", curl_command="curl x", target="x")
    assert verify_artifact_integrity(a) is True
    # Tamper: rewrite content but not sha256.
    tampered = PocArtifact(
        finding_id=a.finding_id,
        kind=a.kind,
        content=b"curl MALICIOUS",
        content_type=a.content_type,
        sha256=a.sha256,  # stale hash
    )
    assert verify_artifact_integrity(tampered) is False


# ----------------------------------------------------------------------
# Zero-FP gate: require_poc_artifact flag
# ----------------------------------------------------------------------


def test_gate_with_poc_required_rejects_evidence_only_finding():
    findings = [
        {
            "id": "F1",
            "title": "SQL injection",
            "evidence_chain_id": "E-123",
            # No poc_artifact_sha256!
        },
    ]
    result = apply_gate(
        findings, ReportTier.OPERATOR, require_poc_artifact=True,
    )
    assert result.rejected_count == 1
    assert "PoC artifact" in result.rejected[0]["rejection_reason"]


def test_gate_with_poc_required_accepts_finding_with_valid_sha():
    findings = [
        {
            "id": "F1",
            "title": "SQL injection",
            "evidence_chain_id": "E-123",
            "poc_artifact_sha256": "a" * 64,
        },
    ]
    result = apply_gate(
        findings, ReportTier.OPERATOR, require_poc_artifact=True,
    )
    assert result.accepted_count == 1


def test_gate_rejects_malformed_sha():
    """Not 64 hex chars = not accepted as PoC."""
    findings = [
        {
            "id": "F1",
            "evidence_chain_id": "E-1",
            "poc_artifact_sha256": "nothex",
        },
    ]
    result = apply_gate(
        findings, ReportTier.OPERATOR, require_poc_artifact=True,
    )
    assert result.rejected_count == 1


def test_gate_accepts_poc_artifact_as_dict():
    findings = [
        {
            "id": "F1",
            "evidence_chain_id": "E-1",
            "poc_artifact": {"sha256": "b" * 64, "kind": "curl"},
        },
    ]
    result = apply_gate(
        findings, ReportTier.OPERATOR, require_poc_artifact=True,
    )
    assert result.accepted_count == 1


def test_gate_poc_optional_when_flag_off():
    """When the flag is False, findings without PoC still pass as
    long as they have regular evidence."""
    findings = [
        {"id": "F1", "evidence_chain_id": "E-1"},
    ]
    result = apply_gate(
        findings, ReportTier.OPERATOR, require_poc_artifact=False,
    )
    assert result.accepted_count == 1


def test_gate_scout_tier_bypasses_poc_requirement():
    """SCOUT tier never gates. PoC requirement ignored."""
    findings = [{"id": "F1", "title": "hypothetical"}]
    result = apply_gate(
        findings, ReportTier.SCOUT, require_poc_artifact=True,
    )
    assert result.accepted_count == 1


def test_gate_founder_override_covers_missing_poc():
    findings = [{"id": "F1", "evidence_chain_id": "E-1"}]
    result = apply_gate(
        findings, ReportTier.EVILBOB,
        founder_override_ids={"F1"},
        require_poc_artifact=True,
    )
    assert result.override_count == 1
    assert result.rejected_count == 0
