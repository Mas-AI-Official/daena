"""Phase-4 Chunk-3 -- WorldSignal file-drop source adapter contract.

NEVER-7 forbids merging Daena and WorldSignal runtimes / DBs / queues.
This adapter is the whole allowed seam: WorldSignal writes a local JSON
file, Daena reads it via adapter only. These tests pin that the adapter
stays a passive, read-only, decoupled local-file reader.

Pins:
  1. Bare-list drop form yields one opportunity per valid entry.
  2. ``{"opportunities": [...]}`` wrapper form is accepted (Postel).
  3. Missing drop file -> [] (WorldSignal being down never aborts).
  4. Malformed JSON -> [] (no exception leaks).
  5. Non-list / non-wrapper payload -> [].
  6. Oversize file (> MAX_BYTES) -> [] (runaway producer can't OOM).
  7. Builder refuses a URL drop_path at BUILD time (no network path).
  8. Builder refuses empty drop_path.
  9. Builder refuses unknown default opportunity type.
 10. Builder refuses out-of-range max_items.
 11. Per-entry ``type`` overrides the builder default.
 12. Entry with an unknown explicit type is skipped, not mislabeled.
 13. Entry without a title is skipped.
 14. Result count is capped at max_items.
 15. Scalar fields are coerced + length-truncated.
 16. Emitted opportunities carry drop provenance in raw_metadata.
 17. Hard rule: adapter source imports no network / DB / queue / broker
     client and never imports WorldSignal code.
 18. Wiring: ``register_public_sources_from_config`` picks up a
     ``worldsignal_drops`` config entry, registers a working source,
     is idempotent, and silently skips malformed / unsafe entries.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.services.business_pipeline import sources as sources_mod
from app.services.business_pipeline.discoverer import (
    DiscoveredOpportunity,
    SOURCE_REGISTRY,
    _reset_for_tests,
)
from app.services.business_pipeline.sources import worldsignal_drop
from app.services.business_pipeline.sources.worldsignal_drop import (
    build_worldsignal_drop_source,
)


_SRC_FILE = (
    Path(__file__).parent.parent / "app" / "services"
    / "business_pipeline" / "sources" / "worldsignal_drop.py"
)


def _write(tmp_path: Path, payload) -> str:
    """Write a drop file and return its path string."""
    drop = tmp_path / "opportunity_drop.json"
    drop.write_text(
        json.dumps(payload) if not isinstance(payload, str) else payload,
        encoding="utf-8",
    )
    return str(drop)


# ────────────────────────────────────────────────────────────────────
# Builder validation (fail fast on bad config)
# ────────────────────────────────────────────────────────────────────


class TestBuilderValidation:
    def test_refuses_url_drop_path(self):
        with pytest.raises(ValueError, match="local file"):
            build_worldsignal_drop_source(
                drop_path="https://ws.example.com/drop.json",
                default_type="partnership", source_name="WS",
            )

    def test_refuses_empty_drop_path(self):
        with pytest.raises(ValueError, match="non-empty"):
            build_worldsignal_drop_source(
                drop_path="   ",
                default_type="partnership", source_name="WS",
            )

    def test_refuses_unknown_default_type(self):
        with pytest.raises(ValueError, match="opportunity type"):
            build_worldsignal_drop_source(
                drop_path="var/ws/drop.json",
                default_type="not_a_type", source_name="WS",
            )

    def test_refuses_bad_max_items(self):
        with pytest.raises(ValueError, match="max_items"):
            build_worldsignal_drop_source(
                drop_path="var/ws/drop.json",
                default_type="partnership", source_name="WS", max_items=0,
            )
        with pytest.raises(ValueError, match="max_items"):
            build_worldsignal_drop_source(
                drop_path="var/ws/drop.json",
                default_type="partnership", source_name="WS", max_items=999,
            )


# ────────────────────────────────────────────────────────────────────
# Drop payload reading + failure isolation
# ────────────────────────────────────────────────────────────────────


class TestDropReading:
    def test_bare_list_form(self, tmp_path):
        path = _write(tmp_path, [
            {"type": "partnership", "title": "Alpha co-sell"},
            {"type": "grant", "title": "Beta grant"},
        ])
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership",
            source_name="WorldSignal drop",
        )
        out = list(fn())
        assert len(out) == 2
        assert all(isinstance(o, DiscoveredOpportunity) for o in out)
        assert out[0].title == "Alpha co-sell"
        assert out[0].source_name == "WorldSignal drop"
        assert out[1].type == "grant"

    def test_wrapper_form(self, tmp_path):
        path = _write(tmp_path, {
            "schema": "worldsignal.opportunity_drop.v1",
            "opportunities": [{"type": "partnership", "title": "Wrapped"}],
        })
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership", source_name="WS",
        )
        out = list(fn())
        assert len(out) == 1
        assert out[0].title == "Wrapped"

    def test_missing_file_returns_empty(self, tmp_path):
        fn = build_worldsignal_drop_source(
            drop_path=str(tmp_path / "does-not-exist.json"),
            default_type="partnership", source_name="WS",
        )
        assert list(fn()) == []

    def test_malformed_json_returns_empty(self, tmp_path):
        path = _write(tmp_path, "not json {{{{")
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership", source_name="WS",
        )
        assert list(fn()) == []

    def test_non_collection_payload_returns_empty(self, tmp_path):
        path = _write(tmp_path, 123)
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership", source_name="WS",
        )
        assert list(fn()) == []

    def test_oversize_file_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(worldsignal_drop, "MAX_BYTES", 8)
        path = _write(tmp_path, [{"type": "partnership", "title": "Too big"}])
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership", source_name="WS",
        )
        assert list(fn()) == []


# ────────────────────────────────────────────────────────────────────
# Per-entry handling
# ────────────────────────────────────────────────────────────────────


class TestEntryHandling:
    def test_per_entry_type_overrides_default(self, tmp_path):
        path = _write(tmp_path, [{"type": "grant", "title": "Override"}])
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership", source_name="WS",
        )
        out = list(fn())
        assert out[0].type == "grant"

    def test_entry_uses_default_type_when_absent(self, tmp_path):
        path = _write(tmp_path, [{"title": "No type given"}])
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership", source_name="WS",
        )
        out = list(fn())
        assert len(out) == 1
        assert out[0].type == "partnership"

    def test_unknown_entry_type_skipped(self, tmp_path):
        path = _write(tmp_path, [
            {"type": "bogus_type", "title": "Skip me"},
            {"type": "partnership", "title": "Keep me"},
        ])
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership", source_name="WS",
        )
        out = list(fn())
        assert len(out) == 1
        assert out[0].title == "Keep me"

    def test_entry_without_title_skipped(self, tmp_path):
        path = _write(tmp_path, [
            {"type": "partnership"},
            {"type": "partnership", "title": "Has title"},
        ])
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership", source_name="WS",
        )
        out = list(fn())
        assert len(out) == 1
        assert out[0].title == "Has title"

    def test_caps_at_max_items(self, tmp_path):
        path = _write(tmp_path, [
            {"type": "partnership", "title": f"Item {i}"} for i in range(50)
        ])
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership",
            source_name="WS", max_items=5,
        )
        out = list(fn())
        assert len(out) == 5

    def test_field_coercion_and_truncation(self, tmp_path):
        path = _write(tmp_path, [{
            "type": "partnership",
            "title": "A" * 600,
            "description": "D" * 1200,
            "source_url": "s" * 2200,
            "deadline_at": "2026-08-01T00:00:00Z",
            "estimated_value_usd": "5000",
            "effort_hours": 8,
            "risk_label": "low",
            "next_action": "Reply to signal",
        }])
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership", source_name="WS",
        )
        out = list(fn())
        opp = out[0]
        assert len(opp.title) == 500
        assert len(opp.description) == 1000
        assert len(opp.source_url) == 2000
        assert opp.estimated_value_usd == 5000
        assert opp.effort_hours == 8
        assert isinstance(opp.deadline_at, datetime)
        assert opp.deadline_at.year == 2026

    def test_meta_carries_drop_provenance(self, tmp_path):
        path = _write(tmp_path, [{
            "type": "partnership", "title": "Traceable",
            "raw_metadata": {"signal_id": "ws-42"},
        }])
        fn = build_worldsignal_drop_source(
            drop_path=path, default_type="partnership", source_name="WS",
        )
        out = list(fn())
        meta = out[0].raw_metadata
        assert meta["signal_id"] == "ws-42"          # original preserved
        assert meta["drop_path"] == path             # provenance added
        assert "drop_mtime" in meta


# ────────────────────────────────────────────────────────────────────
# Hard rule: NEVER-7 boundary is structural, not just behavioral
# ────────────────────────────────────────────────────────────────────


class TestHardRules:
    # Network / DB / queue / broker clients that would breach the
    # "local file only" contract if imported into the adapter.
    FORBIDDEN_IMPORT_TOKENS = (
        "httpx", "requests", "aiohttp", "urllib", "http.client",
        "socket", "sqlalchemy", "psycopg", "asyncpg", "aiomysql",
        "redis", "celery", "kafka", "pika", "aio_pika", "zmq",
        "subprocess", "websocket", "grpc", "worldsignal",
    )

    def test_adapter_imports_no_network_or_db_client(self):
        import_lines = [
            line.strip()
            for line in _SRC_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        for line in import_lines:
            low = line.lower()
            for token in self.FORBIDDEN_IMPORT_TOKENS:
                assert token not in low, (
                    f"forbidden import token {token!r} in adapter: {line!r}"
                )

    def test_adapter_has_no_live_url_or_browser_automation(self):
        src = _SRC_FILE.read_text(encoding="utf-8").lower()
        for forbidden in (
            "http://", "https://", "ftp://",
            "playwright", "selenium",
            "/login", "/signin", "oauth",
        ):
            assert forbidden not in src, (
                f"adapter contains forbidden substring {forbidden!r}"
            )


# ────────────────────────────────────────────────────────────────────
# Config-driven registration through register_public_sources_from_config
# ────────────────────────────────────────────────────────────────────


class TestWiring:
    """The drop adapter is only useful once the registry loop wires it.

    These pin the ``worldsignal_drops`` branch in
    ``sources/__init__.py``: a valid entry registers a live source,
    re-registration is idempotent, and malformed / NEVER-7-unsafe
    entries are dropped without aborting discovery.
    """

    def _register(self, tmp_path, monkeypatch, config):
        cfg = tmp_path / ".opportunity_sources.json"
        cfg.write_text(json.dumps(config), encoding="utf-8")
        monkeypatch.setattr(sources_mod, "_CONFIG_FILE", cfg)
        _reset_for_tests()
        return sources_mod.register_public_sources_from_config()

    def test_registers_worldsignal_drop_from_config(self, tmp_path, monkeypatch):
        drop = _write(tmp_path, [
            {"type": "partnership", "title": "Co-sell from WorldSignal"},
        ])
        registered = self._register(tmp_path, monkeypatch, {
            "worldsignal_drops": [
                {"path": drop, "type": "partnership",
                 "source_name": "WorldSignal drop", "max_items": 20},
            ],
        })
        assert "WorldSignal drop" in registered
        assert "WorldSignal drop" in SOURCE_REGISTRY
        # the registered source actually reads the drop end-to-end
        out = list(SOURCE_REGISTRY["WorldSignal drop"]())
        assert len(out) == 1
        assert out[0].title == "Co-sell from WorldSignal"
        assert out[0].source_name == "WorldSignal drop"

    def test_registration_is_idempotent(self, tmp_path, monkeypatch):
        drop = _write(tmp_path, [{"type": "grant", "title": "Repeatable"}])
        config = {
            "worldsignal_drops": [
                {"path": drop, "type": "grant",
                 "source_name": "WS repeat", "max_items": 5},
            ],
        }
        first = self._register(tmp_path, monkeypatch, config)
        assert "WS repeat" in first
        # second pass must not raise "already registered" and must re-list it
        second = sources_mod.register_public_sources_from_config()
        assert "WS repeat" in second

    def test_skips_unsafe_and_malformed_entries(self, tmp_path, monkeypatch):
        registered = self._register(tmp_path, monkeypatch, {
            "worldsignal_drops": [
                # URL path -- builder rejects at BUILD time (NEVER-7)
                {"path": "https://ws.example.com/drop.json",
                 "type": "partnership", "source_name": "URL drop"},
                # unknown opportunity type -- builder rejects
                {"path": "var/ws/drop.json", "type": "not_a_type",
                 "source_name": "Bad type"},
                # missing source_name -- config-level skip
                {"path": "var/ws/drop.json", "type": "partnership"},
                # missing path -- config-level skip
                {"type": "partnership", "source_name": "No path"},
                # non-dict entry -- config-level skip
                "not-a-dict",
            ],
        })
        assert "URL drop" not in registered
        assert "Bad type" not in registered
        assert "No path" not in registered
        # a bad config never nukes the always-present fallback
        assert "manual_seed" in SOURCE_REGISTRY

    def test_absent_worldsignal_key_is_noop(self, tmp_path, monkeypatch):
        registered = self._register(tmp_path, monkeypatch, {
            "rss_feeds": [], "url_pages": [],
        })
        assert registered == []
        assert "manual_seed" in SOURCE_REGISTRY
