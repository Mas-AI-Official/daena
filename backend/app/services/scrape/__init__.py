"""ScrapeGraphAI governed read-only worker.

PR-SCRAPEGRAPH-GOVERNED-READONLY-SKILL (Sprint-10 PR-2, 2026-05-05).

Public API:

  ``extract_from_url(url, goal, *, max_chars) -> ExtractResult``

The actual scrapegraphai code does NOT live in the backend's main
venv -- it lives in ``D:\\Ideas\\Daena\\venv_daena``. We spawn that
venv's Python as a subprocess, hand it a small JSON payload over
stdin, and parse the JSON result from stdout. This keeps the
backend's dependency tree small and lets us audit the worker
boundary independently of the rest of the import graph.

Hard rules enforced at this boundary:

  * URL safety: re-uses ``connection_v2.url_safety.is_public_url_safe``
    so loopback / RFC1918 / link-local / reserved IP / internal-DNS
    targets never reach the worker.
  * Cap on result bytes: the worker truncates and the parent
    truncates again as defense-in-depth.
  * Timeout: hard 60-second ceiling per call.
  * No login / form submission: the worker uses scrapegraphai's
    SmartScraperGraph (a pure GET-and-extract path). No
    SubmitterGraph, no login flow.
  * Audit: the API caller is responsible for writing an audit row.
    The service itself never logs the URL or extracted body to the
    application logger -- only summary metadata.
"""

from .service import (
    ExtractResult,
    ScrapeError,
    extract_from_url,
)

__all__ = ["ExtractResult", "ScrapeError", "extract_from_url"]
