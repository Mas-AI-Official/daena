#!/usr/bin/env python3
"""Pre-ship SECURITY-SCAN gate for Daena (SAST + SCA + secrets-in-source).

This is the source/dependency security-scan counterpart to the existing
deploy-configuration gate `scripts/production_readiness_check.ps1`. The two are
complementary and non-overlapping:

  - production_readiness_check.ps1  -> deploy CONFIG readiness (Cloud Run env,
    Secret Manager BINDINGS, CORS, DISABLE_AUTH, Cloud SQL link, migrations).
  - preship_security_gate.py (this) -> SOURCE + DEPENDENCY security scans:
      * bandit    (SAST, first-party code)
      * pip-audit (Python dependency CVEs)
      * npm audit (frontend dependency CVEs, production-only)
      * a secrets scanner (committed credentials in the working tree)

It operationalizes FOUNDER-REQUIRED item 7 of the 2026-06-18 overnight pre-ship
security sweep ("wire bandit + pip-audit + npm audit + a modern secrets scanner
into pre-deploy so none of these axes can regress"). The thresholds below ENCODE
the dispositions already made and handed off in that sweep (HANDOFF_P7..P10 under
.archive/overnight_20260618/); they are not new unilateral policy.

DELIBERATELY NOT WIRED into cloudbuild.yaml. Wiring a gate into the live deploy
pipeline is an outward-facing infrastructure decision and is the founder's call.
This script is a ready-to-adopt tool; adopt or tune, then wire.

VERDICT VOCABULARY (project standard): each axis returns one of
  HELD          - the axis passed its threshold.
  BREACHED      - the axis found a gate-failing issue. Only BREACHED fails the gate.
  INCONCLUSIVE  - the axis could not produce a decisive result (tool missing,
                  unparseable output). Never a fabricated pass.

EXIT CODES:
  0  all axes HELD.
  1  at least one axis BREACHED (gate fails).
  2  no BREACH, but at least one axis INCONCLUSIVE (CI may treat as soft/hard fail).

HONEST EXPECTATION: run against the live tree today, the pip-audit axis will
BREACH (the sweep found 62 known CVEs across 15 packages, intentionally NOT yet
bumped on the shared RAM-capped venv). That is the gate working as designed; it
clears once the founder applies the P8 dependency bumps behind a green suite.

OFFLINE VERIFICATION: `python scripts/preship_security_gate.py --selftest` runs
the evaluators against canned fixtures (zero network, zero heavy scan, zero model
tokens) and is the deterministic oracle for this script's logic.

SECURITY: like the deploy-readiness gate, this never prints secret VALUES. The
secrets axis reports only counts, detector names, and locations, never the matched
credential.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

HELD = "HELD"
BREACHED = "BREACHED"
INCONCLUSIVE = "INCONCLUSIVE"

# --- Encoded dispositions from the 2026-06-18 sweep -------------------------

# P7: the single bandit HIGH is B501 (SSL verify off) at
# security/real_scanner.py:982 -- INTENTIONAL offensive-scanner behavior and a
# HANDS-OFF file. Allowlisted by (test_id, path-substring) so the gate does not
# block on a reviewed, accepted finding while still catching any NEW HIGH.
BANDIT_ALLOWLIST = (
    {"test_id": "B501", "path_contains": "real_scanner.py"},
)


@dataclass
class AxisResult:
    name: str
    verdict: str
    summary: str
    details: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure evaluators (JSON/text -> AxisResult). These are what --selftest covers.
# ---------------------------------------------------------------------------

def _bandit_allowlisted(result: dict) -> bool:
    test_id = result.get("test_id")
    filename = (result.get("filename") or "").replace("\\", "/")
    for entry in BANDIT_ALLOWLIST:
        if entry["test_id"] == test_id and entry["path_contains"] in filename:
            return True
    return False


def eval_bandit(data: dict, strict_medium: bool = False) -> AxisResult:
    """Gate baseline: BREACH on HIGH-severity/HIGH-confidence findings (the
    standard bandit-in-CI bar), minus the documented allowlist. MEDIUM/LOW are
    reported but do not fail the gate unless --strict-medium is set."""
    if not isinstance(data, dict) or "results" not in data:
        return AxisResult("bandit", INCONCLUSIVE,
                          "bandit produced no parseable 'results' array")
    fail_sev = {"HIGH", "MEDIUM"} if strict_medium else {"HIGH"}
    blocking, allowed, lower = [], 0, {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in data["results"]:
        sev = (r.get("issue_severity") or "").upper()
        conf = (r.get("issue_confidence") or "").upper()
        lower[sev] = lower.get(sev, 0) + 1
        if sev in fail_sev and conf == "HIGH":
            if _bandit_allowlisted(r):
                allowed += 1
                continue
            blocking.append(
                f"{r.get('test_id')} {sev}/{conf} "
                f"{(r.get('filename') or '').replace(chr(92), '/')}:"
                f"{r.get('line_number')}"
            )
    counts = (f"HIGH={lower.get('HIGH', 0)} MEDIUM={lower.get('MEDIUM', 0)} "
              f"LOW={lower.get('LOW', 0)}; allowlisted={allowed}")
    if blocking:
        return AxisResult("bandit", BREACHED,
                          f"{len(blocking)} blocking SAST finding(s); {counts}",
                          blocking)
    return AxisResult("bandit", HELD,
                      f"no blocking SAST findings; {counts}")


def eval_pip_audit(data) -> AxisResult:
    """Pre-deploy bar: zero known CVEs. BREACH on any vulnerable dependency."""
    if isinstance(data, dict):
        deps = data.get("dependencies")
    elif isinstance(data, list):
        deps = data
    else:
        deps = None
    if deps is None:
        return AxisResult("pip-audit", INCONCLUSIVE,
                          "pip-audit produced no parseable dependency list")
    vuln_pkgs, total = [], 0
    for dep in deps:
        vulns = dep.get("vulns") or []
        if vulns:
            total += len(vulns)
            ids = ",".join(v.get("id", "?") for v in vulns)
            vuln_pkgs.append(f"{dep.get('name')}=={dep.get('version')} ({ids})")
    if vuln_pkgs:
        return AxisResult("pip-audit", BREACHED,
                          f"{total} CVE(s) across {len(vuln_pkgs)} package(s)",
                          vuln_pkgs)
    return AxisResult("pip-audit", HELD, "no known CVEs in Python dependencies")


def eval_npm_audit(data: dict) -> AxisResult:
    """Production-only bar (run with --omit=dev): BREACH on any prod vuln.
    The sweep (P9) found all frontend vulns to be dev/build-transitive, so the
    production-only scope is expected to be empty -> HELD."""
    if not isinstance(data, dict):
        return AxisResult("npm-audit", INCONCLUSIVE,
                          "npm audit produced no parseable JSON object")
    # npm v7+ schema.
    meta = (data.get("metadata") or {}).get("vulnerabilities")
    if isinstance(meta, dict):
        total = meta.get("total", 0)
        breakdown = (f"critical={meta.get('critical', 0)} high={meta.get('high', 0)} "
                     f"moderate={meta.get('moderate', 0)} low={meta.get('low', 0)}")
        if total and total > 0:
            return AxisResult("npm-audit", BREACHED,
                              f"{total} production dependency vuln(s); {breakdown}")
        return AxisResult("npm-audit", HELD,
                          f"no production dependency vulns; {breakdown}")
    # npm v6 fallback schema.
    if "advisories" in data:
        n = len(data["advisories"] or {})
        if n > 0:
            return AxisResult("npm-audit", BREACHED, f"{n} advisory/advisories")
        return AxisResult("npm-audit", HELD, "no advisories")
    return AxisResult("npm-audit", INCONCLUSIVE,
                      "npm audit JSON missing 'metadata.vulnerabilities'")


def eval_secrets(tool: str, lines: list) -> AxisResult:
    """BREACH on any verified secret in the working tree. Never echoes values --
    reports only detector name + location."""
    if tool == "none":
        return AxisResult("secrets", INCONCLUSIVE,
                          "no supported secrets scanner found on PATH "
                          "(install Go trufflehog v3 or gitleaks; the legacy "
                          "truffleHog v2 has no verification engine)")
    findings = []
    if tool == "trufflehog":
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except ValueError:
                continue
            if obj.get("Verified") is True:
                src = obj.get("SourceMetadata") or {}
                findings.append(f"{obj.get('DetectorName', '?')} @ {_loc(src)}")
    elif tool == "gitleaks":
        # gitleaks report is a JSON array.
        try:
            arr = json.loads("".join(lines)) if lines else []
        except ValueError:
            arr = None
        if arr is None:
            return AxisResult("secrets", INCONCLUSIVE,
                              "gitleaks report was not parseable JSON")
        for f in arr:
            findings.append(f"{f.get('RuleID', '?')} @ "
                            f"{f.get('File', '?')}:{f.get('StartLine', '?')}")
    if findings:
        return AxisResult("secrets", BREACHED,
                          f"{len(findings)} verified secret(s) in working tree "
                          f"(values NOT shown)", findings)
    return AxisResult("secrets", HELD,
                      f"{tool}: no verified secrets in working tree")


def _loc(src: dict) -> str:
    data = src.get("Data") or {}
    fs = data.get("Filesystem") or {}
    if fs.get("file"):
        return f"{fs.get('file')}:{fs.get('line', '?')}"
    return "tree"


# ---------------------------------------------------------------------------
# Runners (invoke the real tools). Skipped entirely in --selftest.
# ---------------------------------------------------------------------------

def _venv_python(repo_root: str) -> str:
    for rel in ("venv_daena/Scripts/python.exe", "venv_daena/bin/python"):
        cand = os.path.join(repo_root, rel)
        if os.path.exists(cand):
            return cand
    return sys.executable


def _run(cmd, cwd=None):
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as exc:
        return None, "", str(exc)


def run_bandit(repo_root, strict_medium):
    backend = os.path.join(repo_root, "backend")
    py = _venv_python(repo_root)
    rc, out, err = _run([py, "-m", "bandit", "-r", "app", "-f", "json"], cwd=backend)
    if rc is None or not out.strip():
        return AxisResult("bandit", INCONCLUSIVE,
                          f"bandit did not run ({err.strip() or 'no output'})")
    # bandit (>=1.9) prints a "Working... 100%" progress line to stdout before
    # the JSON document; slice from the first '{' so the report parses.
    start = out.find("{")
    if start >= 0:
        out = out[start:]
    try:
        data = json.loads(out)
    except ValueError:
        return AxisResult("bandit", INCONCLUSIVE, "bandit output was not JSON")
    return eval_bandit(data, strict_medium=strict_medium)


def run_pip_audit(repo_root):
    py = _venv_python(repo_root)
    rc, out, err = _run([py, "-m", "pip_audit", "-f", "json"], cwd=repo_root)
    if rc is None or not out.strip():
        return AxisResult("pip-audit", INCONCLUSIVE,
                          f"pip-audit did not run ({err.strip() or 'no output'})")
    try:
        data = json.loads(out)
    except ValueError:
        return AxisResult("pip-audit", INCONCLUSIVE, "pip-audit output was not JSON")
    return eval_pip_audit(data)


def run_npm_audit(repo_root):
    frontend = os.path.join(repo_root, "frontend")
    npm = shutil.which("npm")
    if not npm or not os.path.isdir(frontend):
        return AxisResult("npm-audit", INCONCLUSIVE,
                          "npm not on PATH or frontend/ missing")
    rc, out, err = _run([npm, "audit", "--omit=dev", "--json"], cwd=frontend)
    if not out.strip():
        return AxisResult("npm-audit", INCONCLUSIVE,
                          f"npm audit produced no output ({err.strip()})")
    try:
        data = json.loads(out)
    except ValueError:
        return AxisResult("npm-audit", INCONCLUSIVE, "npm audit output was not JSON")
    return eval_npm_audit(data)


def run_secrets(repo_root):
    if shutil.which("trufflehog"):
        rc, out, err = _run(["trufflehog", "filesystem", repo_root,
                             "--only-verified", "--json"])
        if rc is None:
            return AxisResult("secrets", INCONCLUSIVE, "trufflehog failed to run")
        # A trufflehog v3 verified filesystem scan exits 0 on success (findings,
        # if any, are JSON on stdout; we do NOT pass --fail). A nonzero exit means
        # the tool on PATH is not a working v3 -- most often the legacy Python
        # truffleHog v2, which has no 'filesystem' subcommand or '--only-verified'
        # flag and exits 2 with an "unrecognized arguments" usage error. Reporting
        # HELD off a scan that never ran would be a fabricated pass (Rule 17), so
        # return INCONCLUSIVE with the cause instead.
        if rc != 0:
            hint = (err.strip().splitlines() or ["nonzero exit"])[-1]
            return AxisResult("secrets", INCONCLUSIVE,
                              f"trufflehog on PATH is not a working v3 verified "
                              f"scanner (exit {rc}: {hint}); install Go trufflehog "
                              f"v3 or gitleaks")
        return eval_secrets("trufflehog", out.splitlines())
    if shutil.which("gitleaks"):
        rc, out, err = _run(["gitleaks", "detect", "--no-banner", "--source",
                             repo_root, "--report-format", "json",
                             "--report-path", "-"])
        if rc is None:
            return AxisResult("secrets", INCONCLUSIVE, "gitleaks failed to run")
        return eval_secrets("gitleaks", out.splitlines())
    return eval_secrets("none", [])


AXES = {
    "bandit": lambda root, args: run_bandit(root, args.strict_medium),
    "pip-audit": lambda root, args: run_pip_audit(root),
    "npm-audit": lambda root, args: run_npm_audit(root),
    "secrets": lambda root, args: run_secrets(root),
}


# ---------------------------------------------------------------------------
# Offline self-test (the deterministic oracle for this script's logic).
# ---------------------------------------------------------------------------

def selftest() -> int:
    cases = []

    def check(label, got, want):
        ok = got == want
        cases.append((ok, label, f"got {got}, want {want}"))

    # bandit: a clean tree HELDs.
    check("bandit/clean", eval_bandit({"results": []}).verdict, HELD)
    # bandit: a NEW high/high finding BREACHes.
    check("bandit/new-high", eval_bandit({"results": [
        {"test_id": "B602", "issue_severity": "HIGH", "issue_confidence": "HIGH",
         "filename": "app/x.py", "line_number": 5}]}).verdict, BREACHED)
    # bandit: ONLY the allowlisted B501/real_scanner.py finding -> HELD.
    check("bandit/allowlisted", eval_bandit({"results": [
        {"test_id": "B501", "issue_severity": "HIGH", "issue_confidence": "HIGH",
         "filename": "app/services/security/real_scanner.py", "line_number": 982}]}
    ).verdict, HELD)
    # bandit: HIGH severity but LOW confidence does not fail the baseline.
    check("bandit/low-conf", eval_bandit({"results": [
        {"test_id": "B102", "issue_severity": "HIGH", "issue_confidence": "LOW",
         "filename": "app/y.py", "line_number": 1}]}).verdict, HELD)
    # bandit: MEDIUM ignored by default, fails under strict.
    med = {"results": [{"test_id": "B303", "issue_severity": "MEDIUM",
                        "issue_confidence": "HIGH", "filename": "a.py",
                        "line_number": 2}]}
    check("bandit/medium-default", eval_bandit(med).verdict, HELD)
    check("bandit/medium-strict", eval_bandit(med, strict_medium=True).verdict, BREACHED)
    # bandit: garbage -> INCONCLUSIVE.
    check("bandit/garbage", eval_bandit({"nope": 1}).verdict, INCONCLUSIVE)

    # pip-audit: clean -> HELD; vulnerable -> BREACHED.
    check("pip/clean", eval_pip_audit({"dependencies": [
        {"name": "a", "version": "1", "vulns": []}]}).verdict, HELD)
    check("pip/vuln", eval_pip_audit({"dependencies": [
        {"name": "pyjwt", "version": "2.12.1",
         "vulns": [{"id": "GHSA-xxxx"}]}]}).verdict, BREACHED)
    # pip-audit: bare-list schema variant.
    check("pip/bare-list", eval_pip_audit(
        [{"name": "a", "version": "1", "vulns": []}]).verdict, HELD)
    check("pip/garbage", eval_pip_audit("nope").verdict, INCONCLUSIVE)

    # npm: prod-only empty -> HELD; prod vuln -> BREACHED.
    check("npm/clean", eval_npm_audit({"metadata": {"vulnerabilities":
        {"total": 0, "critical": 0, "high": 0, "moderate": 0, "low": 0}}}).verdict, HELD)
    check("npm/vuln", eval_npm_audit({"metadata": {"vulnerabilities":
        {"total": 2, "critical": 0, "high": 2, "moderate": 0, "low": 0}}}).verdict, BREACHED)
    check("npm/garbage", eval_npm_audit({"x": 1}).verdict, INCONCLUSIVE)

    # secrets: no tool -> INCONCLUSIVE (never a fabricated pass).
    check("secrets/no-tool", eval_secrets("none", []).verdict, INCONCLUSIVE)
    # secrets: trufflehog verified hit -> BREACHED; only-unverified -> HELD.
    check("secrets/th-verified", eval_secrets("trufflehog", [
        json.dumps({"Verified": True, "DetectorName": "AWS",
                    "SourceMetadata": {"Data": {"Filesystem":
                        {"file": "x.py", "line": 3}}}})]).verdict, BREACHED)
    check("secrets/th-unverified", eval_secrets("trufflehog", [
        json.dumps({"Verified": False, "DetectorName": "AWS"})]).verdict, HELD)
    # secrets: gitleaks array.
    check("secrets/gl-hit", eval_secrets("gitleaks",
        [json.dumps([{"RuleID": "aws-key", "File": "x", "StartLine": 1}])]).verdict, BREACHED)
    check("secrets/gl-clean", eval_secrets("gitleaks", ["[]"]).verdict, HELD)

    # verdict that the BREACHED secret summary never leaks the value:
    leak = eval_secrets("trufflehog", [json.dumps({"Verified": True,
        "DetectorName": "AWS", "Raw": "AKIAIOSFODNN7EXAMPLE",
        "SourceMetadata": {"Data": {"Filesystem": {"file": "x", "line": 1}}}})])
    check("secrets/no-value-leak", "AKIAIOSFODNN7EXAMPLE" not in
          (leak.summary + " ".join(leak.details)), True)

    passed = sum(1 for ok, *_ in cases if ok)
    for ok, label, msg in cases:
        print(f"  [{'ok' if ok else 'FAIL'}] {label}: {msg}")
    print(f"\nselftest: {passed}/{len(cases)} checks passed")
    return 0 if passed == len(cases) else 1


# ---------------------------------------------------------------------------
# Reporting + entrypoint.
# ---------------------------------------------------------------------------

def overall_exit(results) -> int:
    if any(r.verdict == BREACHED for r in results):
        return 1
    if any(r.verdict == INCONCLUSIVE for r in results):
        return 2
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--axes", default="all",
                        help="comma list of axes to run, or 'all' "
                             f"(choices: {', '.join(AXES)})")
    parser.add_argument("--repo-root", default=None,
                        help="repo root (default: parent of this script's dir)")
    parser.add_argument("--strict-medium", action="store_true",
                        help="bandit also BREACHES on MEDIUM/HIGH-confidence")
    parser.add_argument("--json", action="store_true",
                        help="emit machine-readable JSON report")
    parser.add_argument("--selftest", action="store_true",
                        help="run offline evaluator self-test (no scans, no net)")
    args = parser.parse_args(argv)

    if args.selftest:
        return selftest()

    repo_root = args.repo_root or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    selected = list(AXES) if args.axes == "all" else [
        a.strip() for a in args.axes.split(",") if a.strip()]
    unknown = [a for a in selected if a not in AXES]
    if unknown:
        parser.error(f"unknown axes: {', '.join(unknown)}")

    results = [AXES[a](repo_root, args) for a in selected]

    if args.json:
        print(json.dumps([{"axis": r.name, "verdict": r.verdict,
                           "summary": r.summary, "details": r.details}
                          for r in results], indent=2))
    else:
        print("\n=== Daena pre-ship SECURITY-SCAN gate ===")
        print(f"repo root: {repo_root}\n")
        for r in results:
            print(f"[{r.verdict:12}] {r.name:10} {r.summary}")
            for d in r.details:
                print(f"               - {d}")
        held = sum(1 for r in results if r.verdict == HELD)
        breached = sum(1 for r in results if r.verdict == BREACHED)
        incon = sum(1 for r in results if r.verdict == INCONCLUSIVE)
        print(f"\nHELD: {held}  BREACHED: {breached}  INCONCLUSIVE: {incon}")
        if breached:
            print("Gate FAILS: resolve BREACHED axes before deploy.")
        elif incon:
            print("Gate INCONCLUSIVE: a scanner could not decide (see above).")
        else:
            print("Gate HELD: all security-scan axes clear.")

    return overall_exit(results)


if __name__ == "__main__":
    raise SystemExit(main())
