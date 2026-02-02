# Legacy API & Voice Test Strategy

## Background
The historic FastAPI stack (consultation, voice, document endpoints) predates the NBMF refactor. Full `pytest` runs fail due to:
- Missing DB schema columns (`agents.department_id`) referenced by seed scripts.
- Offline services (voice synthesis, document analysis) returning 404s.
- Tests expecting external dependencies (audio processing, coqpit, trainer modules).

## Options
1. **Restore & Maintain**
   - Reintroduce migrations adding `department_id` and related tables.
   - Mock or stub voice/document services for unit tests.
   - Provision dependency wheels (`coqpit`, `trainer`, audio libs) in CI.
   - Pros: keeps original end-to-end demos alive. Cons: high upkeep with little reuse.

2. **Selective Skips / Markers**
   - Add `@pytest.mark.skip` or `@pytest.mark.integration` to legacy suites.
   - Configure `pytest.ini` to run NBMF suites by default, legacy suites manually.
   - Pros: clean NBMF pipelines. Cons: legacy coverage dormant until needed.

3. **Retire Legacy Tests**
   - Remove or archive the legacy modules/tests if roadmap confirms NBMF-only focus.
   - Pros: reduces noise. Cons: loses regression coverage if features resurrected.

## Recommendation
- Short term: keep NBMF test selection in CI (`pytest.ini` with explicit `test_memory_*` etc.).
- Mid term: decide whether to port legacy APIs onto NBMF-backed services or officially sunset them. If sunsetting, mark tests skipped with rationale to avoid recurring failures.
- Document decision in `Governance/NBMF_governance_sop.md` so ops understand why full `pytest` is scoped.

## Next Steps
- If restoration desired, plan migration scripts and stubbed service layer.
- Otherwise, add test markers and update developer docs to run legacy suites only when dependencies are available.
