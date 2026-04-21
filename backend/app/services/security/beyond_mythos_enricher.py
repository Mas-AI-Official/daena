"""BeyondMythos enrichment service for scan findings.

Single entrypoint that wraps the three BeyondMythos cognition classes
(ErrorOracle, AdversarialSimulator, CompositionalPlanner) and applies
them to raw scan findings produced by ScanWorkflow. The goal is to
make the BeyondMythos superpowers available everywhere scans happen
without threading hooks through every OODA-R phase of the engine.

Usage::

    from app.services.security.beyond_mythos_enricher import (
        BeyondMythosEnricher,
    )

    enricher = BeyondMythosEnricher()
    enriched = enricher.enrich_findings(raw_findings, target_defenses=[])

Each enriched finding gains:
    * ``error_intelligence``: ErrorIntelligence dict from any HTTP
      response context in the raw finding.
    * ``defender_prediction``: DefenderPrediction dict for the action
      that produced the finding (when action metadata is present).
    * ``compositional_plan``: CompositionalPlan steps if the finding
      is flagged as blocked / rate-limited / WAF-refused.

All three enrichers are fail-safe: any per-finding error falls back
to returning the finding unchanged plus a ``bm_error`` field so
downstream code can surface the partial failure.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.core.logging import get_logger
from app.services.cognition.beyond_mythos import (
    AdversarialSimulator,
    CompositionalPlanner,
    ErrorOracle,
)

logger = get_logger(__name__)


def _safe_asdict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass to dict, tolerating non-dataclasses."""
    try:
        return asdict(obj)
    except TypeError:
        return dict(obj) if hasattr(obj, "__iter__") else {"value": str(obj)}


class BeyondMythosEnricher:
    """Applies ErrorOracle + AdversarialSimulator + CompositionalPlanner
    to a list of raw scan findings in a single pass.

    Stateless: safe to share a singleton instance across the process.
    """

    def __init__(self) -> None:
        self._oracle = ErrorOracle()
        self._simulator = AdversarialSimulator()
        self._planner = CompositionalPlanner()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enrich_findings(
        self,
        findings: list[dict[str, Any]],
        *,
        target_defenses: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Enrich every finding in-place (returns a new list).

        ``findings`` is the raw list from ``ScanWorkflow._aggregate_findings``.
        Each finding can optionally carry:
            * ``http_response``: {status_code, headers, body,
              response_time_ms, url} -> ErrorOracle input
            * ``action``: {operation, params, request_count} ->
              AdversarialSimulator input
            * ``blocked_reason``: str -> CompositionalPlanner input

        Returns a new list. Original items are copied shallow before
        enrichment; nested dicts stay referenced. No mutation of the
        input list.
        """
        out: list[dict[str, Any]] = []
        for raw in findings:
            enriched = dict(raw)
            try:
                self._enrich_one(enriched, target_defenses or [])
            except Exception as exc:  # pragma: no cover - per-finding fail-safe
                enriched["bm_error"] = str(exc)
                logger.warning(
                    "beyond_mythos.enrich_finding_failed",
                    finding_id=raw.get("id"),
                    error=str(exc),
                )
            out.append(enriched)
        return out

    def compare_response_series(
        self, responses: list[dict[str, Any]]
    ) -> list[str]:
        """Expose ErrorOracle.compare_responses directly for scan phases
        that want cross-response intelligence (enumeration, timing
        anomaly, size variance).
        """
        return self._oracle.compare_responses(responses)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _enrich_one(
        self, finding: dict[str, Any], target_defenses: list[str],
    ) -> None:
        http_resp = finding.get("http_response") or {}
        if http_resp:
            intel = self._oracle.analyze_response(
                url=str(http_resp.get("url", finding.get("location", ""))),
                status_code=int(http_resp.get("status_code", 0) or 0),
                headers=dict(http_resp.get("headers") or {}),
                body=str(http_resp.get("body", "") or ""),
                response_time_ms=int(http_resp.get("response_time_ms", 0) or 0),
                expected_status=http_resp.get("expected_status"),
            )
            finding["error_intelligence"] = _safe_asdict(intel)

        action = finding.get("action") or {}
        if action.get("operation"):
            prediction = self._simulator.predict_detection(
                operation=str(action["operation"]),
                params=dict(action.get("params") or {}),
                target_defenses=target_defenses,
                request_count_so_far=int(action.get("request_count", 0) or 0),
            )
            finding["defender_prediction"] = _safe_asdict(prediction)

            # If the simulator flags detection risk, auto-adjust stealth
            # params so the caller knows the safer alternative.
            if prediction.risk_score >= 0.3:
                adjusted = self._simulator.adjust_for_stealth(
                    operation=str(action["operation"]),
                    params=dict(action.get("params") or {}),
                    prediction=prediction,
                )
                finding["stealth_adjusted_params"] = adjusted

        blocked_reason = finding.get("blocked_reason") or ""
        if blocked_reason:
            plan = self._planner.decompose_blocked_scan(
                scan_strategy_name=str(
                    finding.get("strategy", finding.get("title", "scan"))
                ),
                failure_reason=str(blocked_reason),
                target=str(finding.get("target", finding.get("location", ""))),
            )
            finding["compositional_plan"] = _safe_asdict(plan)
