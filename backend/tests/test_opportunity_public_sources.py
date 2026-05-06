"""Sprint-20 PR-2 -- Public opportunity source adapters contract.

Pins:
  1. RSS 2.0 + Atom parsers extract title/link/description from
     well-formed payloads.
  2. Malformed XML returns [] (no exception leaks).
  3. URL-list parser extracts <title> + <meta description>.
  4. Builder refuses non-HTTP(S) URL.
  5. Builder refuses unknown opportunity type.
  6. RSS builder caps results at max_items.
  7. URL-list emits exactly one DiscoveredOpportunity per page.
  8. Adapter functions never raise on network error / bad status --
     they return [] and log.
  9. Adapter functions emit source_url + source_name for evidence.
 10. Config registry is idempotent (re-registers safely).
 11. Missing config file -> no public sources registered, manual_seed
     remains.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.business_pipeline.discoverer import (
    DiscoveredOpportunity,
    SOURCE_REGISTRY,
    _reset_for_tests,
)
from app.services.business_pipeline.sources.rss import (
    build_rss_atom_source,
    parse_feed_xml,
)
from app.services.business_pipeline.sources.url_list import (
    build_url_list_source,
    parse_page_html,
)


pytestmark = pytest.mark.asyncio


# ────────────────────────────────────────────────────────────────────
# RSS / Atom parser
# ────────────────────────────────────────────────────────────────────


class TestRssParser:
    async def test_rss_2_0_payload(self):
        xml = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Channel</title>
    <item>
      <title>Grant A</title>
      <link>https://example.com/a</link>
      <description>Some HTML <b>here</b></description>
      <pubDate>Tue, 06 May 2026 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Grant B</title>
      <link>https://example.com/b</link>
      <description>Other</description>
    </item>
  </channel>
</rss>"""
        items = parse_feed_xml(xml)
        assert len(items) == 2
        assert items[0]["title"] == "Grant A"
        assert items[0]["link"] == "https://example.com/a"
        assert items[0]["description"] == "Some HTML here"
        assert items[1]["title"] == "Grant B"

    async def test_atom_payload(self):
        xml = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>A feed</title>
  <entry>
    <title>Hack X</title>
    <link href="https://example.com/x" rel="alternate"/>
    <summary>Summary text</summary>
    <updated>2026-05-06T10:00:00Z</updated>
  </entry>
</feed>"""
        items = parse_feed_xml(xml)
        assert len(items) == 1
        assert items[0]["title"] == "Hack X"
        assert items[0]["link"] == "https://example.com/x"
        assert items[0]["description"] == "Summary text"

    async def test_malformed_xml_returns_empty(self):
        assert parse_feed_xml(b"not<<<<xml") == []
        assert parse_feed_xml(b"") == []

    async def test_skips_items_without_title(self):
        xml = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><link>https://example.com/no-title</link></item>
  <item><title>Has title</title></item>
</channel></rss>"""
        items = parse_feed_xml(xml)
        assert len(items) == 1
        assert items[0]["title"] == "Has title"


# ────────────────────────────────────────────────────────────────────
# URL-list parser
# ────────────────────────────────────────────────────────────────────


class TestUrlPageParser:
    async def test_extracts_title_and_description(self):
        html = (
            "<!DOCTYPE html><html><head>"
            "<title> Y Combinator   Programs </title>"
            "<meta name='description' content='Apply for our next batch.'/>"
            "</head><body>...</body></html>"
        )
        title, desc = parse_page_html(html)
        assert title == "Y Combinator Programs"
        assert desc == "Apply for our next batch."

    async def test_extracts_og_description_fallback(self):
        html = (
            "<html><head><title>Page</title>"
            '<meta property="og:description" content="OG fallback"/>'
            "</head></html>"
        )
        title, desc = parse_page_html(html)
        assert title == "Page"
        assert desc == "OG fallback"

    async def test_no_title_returns_none(self):
        html = "<html><body>No head</body></html>"
        title, desc = parse_page_html(html)
        assert title is None
        assert desc is None

    async def test_empty_returns_pair_of_none(self):
        title, desc = parse_page_html("")
        assert title is None and desc is None


# ────────────────────────────────────────────────────────────────────
# Builder validation
# ────────────────────────────────────────────────────────────────────


class TestBuilderValidation:
    async def test_rss_refuses_non_http(self):
        with pytest.raises(ValueError, match="http/https"):
            build_rss_atom_source(
                feed_url="ftp://example.com/feed",
                default_type="grant", source_name="x",
            )

    async def test_rss_refuses_bad_type(self):
        with pytest.raises(ValueError, match="opportunity type"):
            build_rss_atom_source(
                feed_url="https://example.com",
                default_type="not_a_type", source_name="x",
            )

    async def test_rss_refuses_bad_max_items(self):
        with pytest.raises(ValueError, match="max_items"):
            build_rss_atom_source(
                feed_url="https://example.com",
                default_type="grant", source_name="x", max_items=0,
            )
        with pytest.raises(ValueError, match="max_items"):
            build_rss_atom_source(
                feed_url="https://example.com",
                default_type="grant", source_name="x", max_items=999,
            )

    async def test_url_refuses_non_http(self):
        with pytest.raises(ValueError, match="http/https"):
            build_url_list_source(
                page_url="javascript:alert(1)",
                default_type="grant", source_name="x",
            )

    async def test_url_refuses_bad_type(self):
        with pytest.raises(ValueError, match="opportunity type"):
            build_url_list_source(
                page_url="https://example.com",
                default_type="bogus", source_name="x",
            )


# ────────────────────────────────────────────────────────────────────
# Async source fetch behavior (mocked httpx)
# ────────────────────────────────────────────────────────────────────


class _FakeResp:
    def __init__(self, status_code: int = 200, content: bytes = b""):
        self.status_code = status_code
        self.content = content


class _FakeClient:
    def __init__(self, resp: _FakeResp | Exception):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, headers=None):
        if isinstance(self._resp, Exception):
            raise self._resp
        return self._resp


def _patch_httpx(monkeypatch, target_module: str, resp_or_exc):
    import httpx

    def factory(*a, **kw):
        return _FakeClient(resp_or_exc)

    monkeypatch.setattr(
        f"{target_module}.httpx.AsyncClient", factory,
    )


class TestRssAdapterFetch:
    async def test_caps_at_max_items(self, monkeypatch):
        items_xml = "".join(
            f"<item><title>Item {i}</title><link>https://example.com/{i}</link></item>"
            for i in range(50)
        )
        body = f"<rss><channel>{items_xml}</channel></rss>".encode()
        _patch_httpx(
            monkeypatch,
            "app.services.business_pipeline.sources.rss",
            _FakeResp(200, body),
        )
        fn = build_rss_atom_source(
            feed_url="https://example.com/feed",
            default_type="grant", source_name="X grants",
            max_items=5,
        )
        out = list(await fn())
        assert len(out) == 5
        assert all(isinstance(o, DiscoveredOpportunity) for o in out)
        assert all(o.source_name == "X grants" for o in out)
        assert all(o.source_url and o.source_url.startswith("https://") for o in out)

    async def test_network_error_returns_empty(self, monkeypatch):
        import httpx
        _patch_httpx(
            monkeypatch,
            "app.services.business_pipeline.sources.rss",
            httpx.RequestError("dns fail"),
        )
        fn = build_rss_atom_source(
            feed_url="https://example.com/feed",
            default_type="grant", source_name="X",
        )
        assert list(await fn()) == []

    async def test_bad_status_returns_empty(self, monkeypatch):
        _patch_httpx(
            monkeypatch,
            "app.services.business_pipeline.sources.rss",
            _FakeResp(403, b"forbidden"),
        )
        fn = build_rss_atom_source(
            feed_url="https://example.com/feed",
            default_type="grant", source_name="X",
        )
        assert list(await fn()) == []


class TestUrlAdapterFetch:
    async def test_emits_one_per_page(self, monkeypatch):
        body = b"<html><head><title>Cool Accelerator</title></head></html>"
        _patch_httpx(
            monkeypatch,
            "app.services.business_pipeline.sources.url_list",
            _FakeResp(200, body),
        )
        fn = build_url_list_source(
            page_url="https://example.com/programs",
            default_type="accelerator", source_name="Cool",
        )
        out = list(await fn())
        assert len(out) == 1
        assert out[0].title == "Cool Accelerator"
        assert out[0].source_name == "Cool"
        assert out[0].source_url == "https://example.com/programs"
        assert out[0].type == "accelerator"

    async def test_no_title_emits_zero(self, monkeypatch):
        _patch_httpx(
            monkeypatch,
            "app.services.business_pipeline.sources.url_list",
            _FakeResp(200, b"<html><body>only body</body></html>"),
        )
        fn = build_url_list_source(
            page_url="https://example.com/x",
            default_type="grant", source_name="X",
        )
        assert list(await fn()) == []

    async def test_network_error_returns_empty(self, monkeypatch):
        import httpx
        _patch_httpx(
            monkeypatch,
            "app.services.business_pipeline.sources.url_list",
            httpx.RequestError("boom"),
        )
        fn = build_url_list_source(
            page_url="https://example.com",
            default_type="grant", source_name="X",
        )
        assert list(await fn()) == []


# ────────────────────────────────────────────────────────────────────
# Config registry idempotency
# ────────────────────────────────────────────────────────────────────


class TestRegisterFromConfig:
    async def test_missing_config_is_noop(self, tmp_path, monkeypatch):
        from app.services.business_pipeline import sources as sources_mod
        monkeypatch.setattr(
            sources_mod, "_CONFIG_FILE", tmp_path / ".does-not-exist.json",
        )
        _reset_for_tests()
        registered = sources_mod.register_public_sources_from_config()
        assert registered == []
        assert "manual_seed" in SOURCE_REGISTRY

    async def test_registers_rss_and_url(self, tmp_path, monkeypatch):
        from app.services.business_pipeline import sources as sources_mod
        cfg = tmp_path / ".opportunity_sources.json"
        cfg.write_text(json.dumps({
            "rss_feeds": [
                {"url": "https://example.com/a.rss", "type": "grant",
                 "source_name": "Test RSS", "max_items": 10},
            ],
            "url_pages": [
                {"url": "https://example.com/page", "type": "accelerator",
                 "source_name": "Test URL"},
            ],
        }), encoding="utf-8")
        monkeypatch.setattr(sources_mod, "_CONFIG_FILE", cfg)
        _reset_for_tests()
        registered = sources_mod.register_public_sources_from_config()
        assert "Test RSS" in registered
        assert "Test URL" in registered
        # Double-register is idempotent (unregister-then-register)
        registered2 = sources_mod.register_public_sources_from_config()
        assert "Test RSS" in registered2

    async def test_skips_invalid_entries(self, tmp_path, monkeypatch):
        from app.services.business_pipeline import sources as sources_mod
        cfg = tmp_path / ".opportunity_sources.json"
        cfg.write_text(json.dumps({
            "rss_feeds": [
                {"url": "ftp://blocked.example.com", "type": "grant",
                 "source_name": "Blocked"},
                {"url": "https://example.com", "type": "not_a_type",
                 "source_name": "BadType"},
                {"url": "https://example.com", "type": "grant"},
            ],
        }), encoding="utf-8")
        monkeypatch.setattr(sources_mod, "_CONFIG_FILE", cfg)
        _reset_for_tests()
        registered = sources_mod.register_public_sources_from_config()
        # ftp + bad-type rejected at builder; missing source_name skipped at config layer
        assert "Blocked" not in registered
        assert "BadType" not in registered


# ────────────────────────────────────────────────────────────────────
# Hard-rule grep on source files
# ────────────────────────────────────────────────────────────────────


class TestHardRules:
    async def test_no_cookies_or_auth_headers_in_adapters(self):
        for path in (
            Path(__file__).parent.parent / "app" / "services"
            / "business_pipeline" / "sources" / "rss.py",
            Path(__file__).parent.parent / "app" / "services"
            / "business_pipeline" / "sources" / "url_list.py",
        ):
            src = path.read_text(encoding="utf-8")
            assert "cookies=" not in src.lower()
            assert "authorization" not in src.lower()
            assert "playwright" not in src.lower()
            assert "selenium" not in src.lower()

    async def test_adapters_do_not_call_login_endpoints(self):
        """Belt-and-suspenders: source code must not contain any
        substring that looks like a login URL or auth flow."""
        for path in (
            Path(__file__).parent.parent / "app" / "services"
            / "business_pipeline" / "sources" / "rss.py",
            Path(__file__).parent.parent / "app" / "services"
            / "business_pipeline" / "sources" / "url_list.py",
        ):
            src = path.read_text(encoding="utf-8").lower()
            for forbidden in ("/login", "/signin", "/auth/", "oauth"):
                assert forbidden not in src, (
                    f"{path.name} contains forbidden substring {forbidden!r}"
                )
