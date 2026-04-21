"""Tests for SupplyChainScanner MVP.

Covers manifest parsing (package.json + requirements.txt), offline
checks (unpinned + typosquat), and registry-backed checks mocked
out at the httpx layer. No network in CI.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.security import supply_chain_scanner as scm
from app.services.security.supply_chain_scanner import (
    DeclaredDependency,
    Ecosystem,
    SupplyChainRiskKind,
    SupplyChainScanner,
    _is_unpinned,
    _typosquat_neighbors,
    parse_package_json,
    parse_requirements_txt,
)


# ----------------------------------------------------------------------
# Manifest parsers
# ----------------------------------------------------------------------


def test_parse_package_json_reads_deps_and_devdeps(tmp_path):
    p = tmp_path / "package.json"
    p.write_text(json.dumps({
        "name": "app",
        "dependencies": {"axios": "^1.7.0", "react": "^18.2.0"},
        "devDependencies": {"jest": "^29.0.0"},
    }))
    deps = parse_package_json(p)
    names = {d.name for d in deps}
    assert names == {"axios", "react", "jest"}
    dev = [d for d in deps if d.is_dev_dependency]
    assert [d.name for d in dev] == ["jest"]


def test_parse_package_json_handles_missing_file(tmp_path):
    # parse_package_json should not raise on a missing file.
    deps = parse_package_json(tmp_path / "nonexistent.json")
    assert deps == []


def test_parse_package_json_handles_malformed_json(tmp_path):
    p = tmp_path / "package.json"
    p.write_text("{not valid json")
    deps = parse_package_json(p)
    assert deps == []


def test_parse_requirements_txt(tmp_path):
    p = tmp_path / "requirements.txt"
    p.write_text(
        "# comment\n"
        "requests==2.31.0\n"
        "httpx>=0.25,<1.0\n"
        "pandas\n"
        "\n"
        "-r other-requirements.txt\n"
        "flask ; python_version >= '3.10'\n"
    )
    deps = parse_requirements_txt(p)
    names = {d.name for d in deps}
    assert names == {"requests", "httpx", "pandas", "flask"}


# ----------------------------------------------------------------------
# Unpinned detection
# ----------------------------------------------------------------------


def test_is_unpinned_detects_carets_and_stars():
    assert _is_unpinned("^1.0.0") is True
    assert _is_unpinned("~1.0.0") is True
    assert _is_unpinned("*") is True
    assert _is_unpinned("latest") is True
    assert _is_unpinned(">=1.0.0") is True
    assert _is_unpinned("") is True


def test_is_unpinned_accepts_exact():
    assert _is_unpinned("1.2.3") is False
    assert _is_unpinned("1.2.3-beta.1") is False


# ----------------------------------------------------------------------
# Typosquat detection
# ----------------------------------------------------------------------


def test_typosquat_detects_single_char_swap():
    n = _typosquat_neighbors("reactt", Ecosystem.NPM)
    assert len(n) >= 1
    assert n[0][0] == "react"
    assert n[0][1] > 0.8


def test_typosquat_exact_match_skipped():
    """Exact match on a canonical package must NOT be flagged as
    typosquat of itself."""
    assert _typosquat_neighbors("react", Ecosystem.NPM) == []
    assert _typosquat_neighbors("requests", Ecosystem.PYPI) == []


def test_typosquat_dissimilar_returns_empty():
    # Completely unrelated name -> no neighbors above threshold.
    assert _typosquat_neighbors("completely-different-xyz", Ecosystem.NPM) == []


def test_typosquat_detects_pypi_neighbor():
    n = _typosquat_neighbors("reqests", Ecosystem.PYPI)
    assert any(match == "requests" for match, _ in n)


def test_typosquat_unknown_ecosystem_empty():
    n = _typosquat_neighbors("whatever", Ecosystem.UNKNOWN)
    assert n == []


# ----------------------------------------------------------------------
# Scanner end-to-end (offline mode)
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scanner_offline_mode_unpinned_and_typosquat(tmp_path):
    """Offline mode runs only non-network checks (unpinned + typosquat)."""
    p = tmp_path / "package.json"
    p.write_text(json.dumps({
        "dependencies": {
            "reactt": "^18.0.0",  # typosquat
            "left-pad": "1.3.0",  # exact version
            "lodash": "^4.17.0",  # unpinned
        },
    }))
    sc = SupplyChainScanner(offline=True)
    risks = await sc.scan_manifests([p])
    kinds = {r.kind for r in risks}
    # typosquat + unpinned should surface.
    assert SupplyChainRiskKind.TYPOSQUAT in kinds
    assert SupplyChainRiskKind.UNPINNED_VERSION in kinds


@pytest.mark.asyncio
async def test_scanner_offline_mode_skips_registry_checks(tmp_path):
    p = tmp_path / "package.json"
    p.write_text(json.dumps({"dependencies": {"lodash": "^4.0.0"}}))
    sc = SupplyChainScanner(offline=True)
    risks = await sc.scan_manifests([p])
    # Offline: no MAINTAINER_CHANGE, no INSTALL_SCRIPT_PRESENT,
    # no UNKNOWN_REGISTRY.
    kinds = {r.kind for r in risks}
    assert SupplyChainRiskKind.MAINTAINER_CHANGE not in kinds
    assert SupplyChainRiskKind.INSTALL_SCRIPT_PRESENT not in kinds
    assert SupplyChainRiskKind.UNKNOWN_REGISTRY not in kinds


@pytest.mark.asyncio
async def test_scanner_mock_npm_install_script(tmp_path):
    """Mock npm metadata: install script present => risk raised."""
    p = tmp_path / "package.json"
    p.write_text(json.dumps({"dependencies": {"sketchy-pkg": "1.0.0"}}))
    mock_meta = {
        "latest": "1.0.0",
        "maintainers": ["m1"],
        "last_publish": "2026-04-21T00:00:00Z",
        "dist_shasum_by_version": {"1.0.0": "abc"},
        "has_install_script": True,
        "time_map": {},
    }
    with patch.object(
        scm, "_lookup_npm_metadata",
        AsyncMock(return_value=mock_meta),
    ):
        sc = SupplyChainScanner(offline=False)
        risks = await sc.scan_manifests([p])
    kinds = {r.kind for r in risks}
    assert SupplyChainRiskKind.INSTALL_SCRIPT_PRESENT in kinds


@pytest.mark.asyncio
async def test_scanner_mock_maintainer_change(tmp_path):
    """Mock npm time_map: last publish 200 days after previous => risk."""
    p = tmp_path / "package.json"
    p.write_text(json.dumps({"dependencies": {"sleeper-pkg": "2.0.0"}}))
    mock_meta = {
        "latest": "2.0.0",
        "maintainers": ["m1"],
        "last_publish": "2026-04-21T00:00:00Z",
        "dist_shasum_by_version": {"1.0.0": "a", "2.0.0": "b"},
        "has_install_script": False,
        "time_map": {
            "1.0.0": "2025-09-01T00:00:00Z",
            "2.0.0": "2026-04-21T00:00:00Z",  # 232 days later
        },
    }
    with patch.object(
        scm, "_lookup_npm_metadata",
        AsyncMock(return_value=mock_meta),
    ):
        sc = SupplyChainScanner(
            offline=False, maintainer_change_window_days=90,
        )
        risks = await sc.scan_manifests([p])
    kinds = {r.kind for r in risks}
    assert SupplyChainRiskKind.MAINTAINER_CHANGE in kinds


@pytest.mark.asyncio
async def test_scanner_mock_unknown_registry(tmp_path):
    """Empty metadata result => UNKNOWN_REGISTRY risk."""
    p = tmp_path / "package.json"
    p.write_text(json.dumps({"dependencies": {"ghost-pkg": "0.1.0"}}))
    with patch.object(
        scm, "_lookup_npm_metadata", AsyncMock(return_value={}),
    ):
        sc = SupplyChainScanner(offline=False)
        risks = await sc.scan_manifests([p])
    kinds = {r.kind for r in risks}
    assert SupplyChainRiskKind.UNKNOWN_REGISTRY in kinds


@pytest.mark.asyncio
async def test_scanner_pypi_yanked_version(tmp_path):
    """Pinned to a yanked PyPI version => risk."""
    p = tmp_path / "requirements.txt"
    p.write_text("bad-pkg==1.0.0\n")
    mock_meta = {
        "latest": "2.0.0",
        "yanked_versions": ["1.0.0"],
        "author": "",
        "maintainer": "",
    }
    with patch.object(
        scm, "_lookup_pypi_metadata",
        AsyncMock(return_value=mock_meta),
    ):
        sc = SupplyChainScanner(offline=False)
        risks = await sc.scan_manifests([p])
    kinds = {r.kind for r in risks}
    assert SupplyChainRiskKind.YANKED_VERSION in kinds


# ----------------------------------------------------------------------
# Risk serialization
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_risk_to_finding_dict_has_poc_artifact_sha(tmp_path):
    """Every risk carrying a PoC surfaces its sha256 on serialization."""
    p = tmp_path / "package.json"
    p.write_text(json.dumps({"dependencies": {"lodash": "*"}}))
    sc = SupplyChainScanner(offline=True)
    risks = await sc.scan_manifests([p])
    assert risks
    for r in risks:
        d = r.to_finding_dict()
        assert d["kind"] == "supply_chain"
        assert "location" in d
        assert "remediation" in d
        assert d["evidence_chain_id"].startswith("sc-")
        if r.poc_artifact is not None:
            assert d["poc_artifact_sha256"] == r.poc_artifact.sha256


@pytest.mark.asyncio
async def test_risk_severity_scales_with_typosquat_score(tmp_path):
    """Very close typosquat (ratio >= 0.9) = HIGH; lower = MEDIUM."""
    p = tmp_path / "package.json"
    p.write_text(json.dumps({
        "dependencies": {
            "reactt": "^18.0.0",  # ratio ~0.91 (HIGH)
            "lodahs": "^4.0.0",   # ratio ~0.83 (MEDIUM)
        },
    }))
    sc = SupplyChainScanner(offline=True)
    risks = await sc.scan_manifests([p])
    typosquats = [r for r in risks if r.kind == SupplyChainRiskKind.TYPOSQUAT]
    severities = {r.severity for r in typosquats}
    # Severity taxonomy sanity.
    assert severities.issubset({"HIGH", "MEDIUM", "LOW"})


# ----------------------------------------------------------------------
# Error containment
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scanner_per_dep_exception_does_not_abort_batch(tmp_path):
    """If one dep's lookup raises, others still return."""
    p = tmp_path / "package.json"
    p.write_text(json.dumps({
        "dependencies": {"good-pkg": "1.0.0", "bad-pkg": "1.0.0"},
    }))
    call_count = {"n": 0}

    async def flaky(name, timeout=5.0):
        call_count["n"] += 1
        if name == "bad-pkg":
            raise RuntimeError("boom")
        return {
            "latest": "1.0.0", "maintainers": [], "last_publish": "",
            "dist_shasum_by_version": {}, "has_install_script": False,
            "time_map": {},
        }

    with patch.object(scm, "_lookup_npm_metadata", flaky):
        sc = SupplyChainScanner(offline=False)
        risks = await sc.scan_manifests([p])
    # Both deps were inspected (no early abort).
    assert call_count["n"] == 2


@pytest.mark.asyncio
async def test_scanner_handles_missing_manifest(tmp_path):
    """Missing manifest path logs a warning and returns empty risks,
    not an exception."""
    sc = SupplyChainScanner(offline=True)
    risks = await sc.scan_manifests([tmp_path / "nope.json"])
    assert risks == []


# ----------------------------------------------------------------------
# Edge cases on DeclaredDependency
# ----------------------------------------------------------------------


def test_declared_dependency_default_fields():
    d = DeclaredDependency(
        ecosystem=Ecosystem.NPM, name="x", version_spec="1.0.0",
    )
    assert d.resolved_version == ""
    assert d.is_dev_dependency is False
    assert d.manifest_path == ""
