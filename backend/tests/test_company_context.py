"""Unit coverage for ``app.services.company_context``.

The runtime company-context store is the connector that carries the founder's
company brief into EVERY chat system prompt (``main.py`` hydrates it on
startup, the ``company_mode`` API set/get/clears it, and ``soul_engine``
renders it via ``to_soul_inject``). The module exists precisely because a
regression here is silent: the founder fills the Company Mode form, sees a
success toast, and then chats with a Daena that has no idea who its company
is. So the prompt projection, the store semantics, and the on-disk seed
parser (including its legacy-field back-compat) are all worth pinning.

These are pure-logic units: the store is in-memory, ``to_soul_inject`` is a
deterministic string build, and the only IO (``hydrate_from_disk`` /
``_parse_seed_file``) is exercised against ``tmp_path`` seed files this test
writes itself. No DB, no network, no async, no LLM. The real on-disk
``company_seed.md`` (founder IP) is never read -- every fixture here is
synthetic.
"""
from __future__ import annotations

import pytest

from app.services.company_context import (
    CompanyContext,
    CompanyContextStore,
    _parse_seed_file,
)


def _ctx(**overrides) -> CompanyContext:
    """A valid CompanyContext with all required fields filled, overridable."""
    base = dict(
        company_name="Acme Inc.",
        one_liner="We make X effortless.",
        target_customer="mid-market ops teams",
        pain="manual toil",
        promise="zero-touch automation",
    )
    base.update(overrides)
    return CompanyContext(**base)


def _write_seed(path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# CompanyContext.to_soul_inject -- the string the soul engine prepends
# ---------------------------------------------------------------------------

def test_to_soul_inject_renders_every_field():
    inject = _ctx(
        proof_points=["2 patents", "Google Startup Program"],
        channels=["LinkedIn", "direct"],
        tone="bold",
    ).to_soul_inject()
    assert "## Company Context (founder mode)" in inject
    assert "Company: Acme Inc." in inject
    assert "Mission: We make X effortless." in inject
    assert "Target customer: mid-market ops teams" in inject
    assert "Pain we solve: manual toil" in inject
    assert "Our promise: zero-touch automation" in inject
    # Proof points join with " | "; channels join with ", ".
    assert "Proof points: 2 patents | Google Startup Program" in inject
    assert "Channels: LinkedIn, direct" in inject
    assert "Tone: bold" in inject


def test_to_soul_inject_defaults_actor_to_the_founder():
    inject = _ctx().to_soul_inject()
    assert "When operating as the founder" in inject


def test_to_soul_inject_uses_department_as_actor():
    inject = _ctx().to_soul_inject(department="Marketing")
    assert "When operating as Marketing" in inject


def test_to_soul_inject_empty_proof_points_and_channels_use_placeholders():
    inject = _ctx(proof_points=[], channels=[]).to_soul_inject()
    assert "Proof points: (none yet)" in inject
    assert "Channels: (unset)" in inject


def test_to_soul_inject_tone_defaults_to_professional():
    # tone is not supplied -> model default.
    assert "Tone: professional" in _ctx().to_soul_inject()


# ---------------------------------------------------------------------------
# CompanyContextStore -- thread-safe per-tenant in-memory cache
# ---------------------------------------------------------------------------

def test_store_set_then_get_returns_same_context():
    store = CompanyContextStore()
    ctx = _ctx()
    store.set("tenant-a", ctx)
    assert store.get("tenant-a") is ctx


def test_store_get_unknown_tenant_is_none():
    assert CompanyContextStore().get("nobody") is None


def test_store_clear_removes_the_entry():
    store = CompanyContextStore()
    store.set("t", _ctx())
    store.clear("t")
    assert store.get("t") is None


def test_store_clear_unknown_tenant_is_a_silent_noop():
    # Clearing a tenant that was never set must not raise.
    CompanyContextStore().clear("never-set")


def test_store_set_overwrites_same_tenant():
    store = CompanyContextStore()
    store.set("t", _ctx(company_name="Old Co"))
    store.set("t", _ctx(company_name="New Co"))
    assert store.get("t").company_name == "New Co"


def test_store_tenants_are_isolated():
    store = CompanyContextStore()
    store.set("a", _ctx(company_name="A Co"))
    store.set("b", _ctx(company_name="B Co"))
    assert store.get("a").company_name == "A Co"
    assert store.get("b").company_name == "B Co"


# ---------------------------------------------------------------------------
# _parse_seed_file -- YAML-frontmatter parser with legacy back-compat
# ---------------------------------------------------------------------------

def test_parse_seed_file_reads_canonical_frontmatter(tmp_path):
    seed = tmp_path / "company_seed.md"
    _write_seed(
        seed,
        "---\n"
        "company_name: Canon Co\n"
        "one_liner: canonical mission\n"
        "target_customer: devs\n"
        "pain: yak shaving\n"
        "promise: less yak\n"
        "proof_points:\n  - p1\n  - p2\n"
        "channels:\n  - x\n"
        "tone: crisp\n"
        "---\nbody ignored\n",
    )
    ctx = _parse_seed_file(seed)
    assert ctx is not None
    assert ctx.company_name == "Canon Co"
    assert ctx.one_liner == "canonical mission"
    assert ctx.proof_points == ["p1", "p2"]
    assert ctx.channels == ["x"]
    assert ctx.tone == "crisp"


def test_parse_seed_file_remaps_legacy_field_names(tmp_path):
    # v0 seeds used company_one_liner / customer_pain / our_promise.
    seed = tmp_path / "company_seed.md"
    _write_seed(
        seed,
        "---\n"
        "company_name: Legacy Co\n"
        "company_one_liner: legacy mission\n"
        "target_customer: ops\n"
        "customer_pain: legacy pain\n"
        "our_promise: legacy promise\n"
        "---\n",
    )
    ctx = _parse_seed_file(seed)
    assert ctx is not None
    assert ctx.one_liner == "legacy mission"
    assert ctx.pain == "legacy pain"
    assert ctx.promise == "legacy promise"


def test_parse_seed_file_canonical_wins_over_legacy(tmp_path):
    # When both are present the canonical key takes precedence.
    seed = tmp_path / "company_seed.md"
    _write_seed(
        seed,
        "---\n"
        "company_name: Both Co\n"
        "one_liner: canonical\n"
        "company_one_liner: legacy\n"
        "target_customer: c\n"
        "pain: p\n"
        "promise: q\n"
        "---\n",
    )
    assert _parse_seed_file(seed).one_liner == "canonical"


def test_parse_seed_file_defaults_lists_and_tone(tmp_path):
    seed = tmp_path / "company_seed.md"
    _write_seed(
        seed,
        "---\n"
        "company_name: Min Co\n"
        "one_liner: m\n"
        "target_customer: c\n"
        "pain: p\n"
        "promise: q\n"
        "---\n",
    )
    ctx = _parse_seed_file(seed)
    assert ctx.proof_points == []
    assert ctx.channels == []
    assert ctx.tone == "professional"


def test_parse_seed_file_without_frontmatter_is_none(tmp_path):
    seed = tmp_path / "company_seed.md"
    _write_seed(seed, "just a plain note, no frontmatter\n")
    assert _parse_seed_file(seed) is None


def test_parse_seed_file_with_unclosed_frontmatter_is_none(tmp_path):
    # Starts with --- but never closes -> fewer than 3 split parts.
    seed = tmp_path / "company_seed.md"
    _write_seed(seed, "---\ncompany_name: Half Co\n")
    assert _parse_seed_file(seed) is None


def test_parse_seed_file_with_non_mapping_body_is_none(tmp_path):
    # A scalar frontmatter body is not a dict -> rejected, not crashed.
    seed = tmp_path / "company_seed.md"
    _write_seed(seed, "---\njust a scalar line\n---\n")
    assert _parse_seed_file(seed) is None


# ---------------------------------------------------------------------------
# CompanyContextStore.hydrate_from_disk -- startup restore from soul dir
# ---------------------------------------------------------------------------

def _founder_seed(soul_root, company_name: str = "Hydrated Co") -> None:
    _write_seed(
        soul_root / "company_seed.md",
        f"---\n"
        f"company_name: {company_name}\n"
        f"one_liner: m\ntarget_customer: c\npain: p\npromise: q\n"
        f"---\n",
    )


def test_hydrate_loads_founder_seed_under_founder_key(tmp_path):
    _founder_seed(tmp_path)
    store = CompanyContextStore()
    assert store.hydrate_from_disk(tmp_path) == 1
    assert store.get("founder").company_name == "Hydrated Co"


def test_hydrate_returns_zero_when_no_seed_present(tmp_path):
    store = CompanyContextStore()
    assert store.hydrate_from_disk(tmp_path) == 0
    assert store.get("founder") is None


def test_hydrate_loads_per_tenant_seeds(tmp_path):
    tenants = tmp_path / "tenants"
    (tenants / "tenant-x").mkdir(parents=True)
    _write_seed(
        tenants / "tenant-x" / "company_seed.md",
        "---\ncompany_name: Tenant X Co\none_liner: m\n"
        "target_customer: c\npain: p\npromise: q\n---\n",
    )
    store = CompanyContextStore()
    assert store.hydrate_from_disk(tmp_path) == 1
    assert store.get("tenant-x").company_name == "Tenant X Co"


def test_hydrate_counts_founder_and_tenant_together(tmp_path):
    _founder_seed(tmp_path)
    tenants = tmp_path / "tenants"
    (tenants / "t1").mkdir(parents=True)
    _write_seed(
        tenants / "t1" / "company_seed.md",
        "---\ncompany_name: T1\none_liner: m\n"
        "target_customer: c\npain: p\npromise: q\n---\n",
    )
    store = CompanyContextStore()
    assert store.hydrate_from_disk(tmp_path) == 2


def test_hydrate_skips_malformed_seed(tmp_path):
    # A seed that fails to parse must not be stored and must not raise.
    _write_seed(tmp_path / "company_seed.md", "not frontmatter at all\n")
    store = CompanyContextStore()
    assert store.hydrate_from_disk(tmp_path) == 0
    assert store.get("founder") is None
