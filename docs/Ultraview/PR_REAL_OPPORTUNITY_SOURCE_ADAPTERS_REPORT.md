# PR-2 -- Real Opportunity Source Adapters

**Sprint:** DAENA-SPRINT-20-LIVE-BUSINESS-OPS-ACTIVATION
**PR:** 2 of 8
**Date:** 2026-05-06

## Goal

Replace the manual-seed-only opportunity surface with safe, public,
read-only source adapters the operator can opt into via a gitignored
config file. Sprint-19 shipped the orchestrator; Sprint-20 wires real
discovery into it without ever scraping behind a login wall.

## What ships

`backend/app/services/business_pipeline/sources/rss.py` (new):
* RSS 2.0 + Atom parsing on stdlib `xml.etree.ElementTree`. No
  feedparser dep, no JS, no link-following.
* `build_rss_atom_source(feed_url, default_type, source_name,
  max_items)` returns an async source fn the orchestrator can call.

`backend/app/services/business_pipeline/sources/url_list.py` (new):
* Single-page fetcher for accelerator / grant homepages without RSS.
* `parse_page_html` extracts `<title>` + `<meta name=description>`
  (or `og:description`). One URL = one DiscoveredOpportunity.

`backend/app/services/business_pipeline/sources/__init__.py` (new):
* Reads `backend/.opportunity_sources.json` (gitignored) and registers
  each declared feed/URL via the existing `register_source` API.
* Idempotent: re-registers safely (unregister-then-register).
* Missing config = no public sources, manual_seed remains.

`backend/app/services/business_pipeline/discoverer.py` (modified):
* `SourceFn` is now a union of sync and async callables.
* `call_source(fn)` resolves either transparently for the orchestrator.

`backend/app/services/business_pipeline/orchestrator.py` (modified):
* Source iteration awaits via `call_source`. Failures are still
  isolated -- one bad adapter never aborts discovery.

`backend/app/services/business_pipeline/__init__.py` (modified):
* Side-effect call to `register_public_sources_from_config()` on
  package import so adapters are wired before the first discovery run.

`backend/.gitignore` (modified):
* Adds `.opportunity_sources.json` to gitignore.

## Mythos design choices

**Per-source caps + timeouts are defense in depth.** A noisy feed
returning 5000 items can't dominate the top-N. A slow / hostile feed
times out at 8s. Body capped at 256 KiB. Per-source result cap is the
contract a feed cannot violate -- the budget is the budget.

**Builder validation fails fast.** Bad URL or bad opportunity type =
`ValueError` at registration, not at first run. The operator finds out
when they edit `.opportunity_sources.json`, not when they wonder why
no leads appeared.

**Stdlib XML, not feedparser.** One less dep, one less surface for
malicious feeds to exploit. The two RSS shapes Daena cares about are
trivial; they don't need a 2000-line library.

**`<title>` + `<meta description>` only.** No body parsing, no link
crawling. The operator follows `source_url` themselves. Daena's job is
discovery, not extraction.

**Codex-aligned cut.** HN public API was considered. Codex's review
flagged HN as noisy unless the operator has a clear "startup leads"
lane. Cut for now -- RSS + URL-list cover the high-signal sources
(grants, accelerators, partner programs) without that ambiguity. Easy
to add later via the same registration spine if the operator wants it.

**No User-Agent that pretends to be a browser.** `Daena-Discovery/1.0`
plus the public website URL. If a publisher blocks bots, they SHOULD
be able to block us cleanly.

**No cookies, no auth headers, no OAuth flow strings in source.**
Hard rule audit greps the source files for these patterns -- a
regression that adds them is a test failure.

**Source failures are silent and isolated.** Each adapter returns `[]`
on network error / bad status. The orchestrator already isolates
exceptions per source. The discovery cycle either runs to completion
or fails per-source -- never half-aborted.

## Locked invariants

| Invariant | Where |
|---|---|
| RSS 2.0 parsed including HTML in description | `TestRssParser::test_rss_2_0_payload` |
| Atom parsed | `test_atom_payload` |
| Malformed XML returns [] | `test_malformed_xml_returns_empty` |
| Items without title skipped | `test_skips_items_without_title` |
| `<title>` + `<meta description>` extracted | `TestUrlPageParser::test_extracts_title_and_description` |
| `og:description` fallback works | `test_extracts_og_description_fallback` |
| Builder refuses non-HTTP(S) | `TestBuilderValidation::test_rss_refuses_non_http`, `test_url_refuses_non_http` |
| Builder refuses unknown type | `test_rss_refuses_bad_type`, `test_url_refuses_bad_type` |
| RSS caps at max_items | `TestRssAdapterFetch::test_caps_at_max_items` |
| Network error -> [] | `test_network_error_returns_empty` (RSS + URL) |
| Bad HTTP status -> [] | `test_bad_status_returns_empty` |
| URL emits exactly one per page | `TestUrlAdapterFetch::test_emits_one_per_page` |
| Missing config = no-op | `TestRegisterFromConfig::test_missing_config_is_noop` |
| Re-registration is idempotent | `test_registers_rss_and_url` second call |
| Adapters carry no cookies / auth / oauth strings | `TestHardRules` |

## Hard rules audit

| Rule | Status |
|---|---|
| http/https public only | enforced -- builder rejects non-http(s) |
| no login / scraping behind auth | enforced -- adapters never send Authorization or cookies |
| no browser automation | enforced -- httpx only, no Playwright / Selenium import |
| cap results per source | enforced -- max_items, default 20 |
| timeout per source | enforced -- TIMEOUT_S=8.0 |
| size cap per source | enforced -- MAX_BYTES=256 KiB |
| source failure does not kill discovery | enforced -- adapter returns [], orchestrator catches |
| every opportunity has source_url + source_name | enforced -- adapters always set both |

## Tests

```
backend/tests/test_opportunity_public_sources.py   24 tests
backend/tests/test_business_pipeline.py            15 tests (regression)
```

39/39 pass.

## Files

```
modified:   backend/app/services/business_pipeline/discoverer.py
modified:   backend/app/services/business_pipeline/orchestrator.py
modified:   backend/app/services/business_pipeline/__init__.py
new:        backend/app/services/business_pipeline/sources/__init__.py
new:        backend/app/services/business_pipeline/sources/rss.py
new:        backend/app/services/business_pipeline/sources/url_list.py
new:        backend/tests/test_opportunity_public_sources.py
modified:   backend/.gitignore
new:        docs/Ultraview/PR_REAL_OPPORTUNITY_SOURCE_ADAPTERS_REPORT.md
```

## Next: PR-3 -- Opportunity-to-Workstream Completion
