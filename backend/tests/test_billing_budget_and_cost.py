"""Unit coverage for the billing spend-cap subsystem.

Two tightly coupled, previously-untested money modules:

  * ``app.services.billing.cost_tracker.UnifiedCostTracker`` -- the in-memory
    ledger every provider call logs through (per-day / per-month / per-provider
    / per-task-type / per-session aggregation).
  * ``app.services.billing.budget_manager.BudgetManager`` -- the pre-execution
    spend-cap decision tree (allow / warn / block / free_only) that READS the
    tracker.

A regression in either ships wrong customer invoices or a blown (or
over-zealous) spend cap on a paid tier, so the branching is worth pinning.

These are pure-logic units: no DB, no network, no async. Both classes are
process singletons, so the autouse fixture resets ``_instance`` before AND
after every test to stop state bleeding between cases.

Date handling: ``get_daily_cost`` keys on ``date.today()`` and
``get_monthly_cost`` sums every key sharing the current ``YYYY-MM`` prefix.
Tests that need a same-month-but-not-today cost seed a key derived from
``date.today()`` (never a hard-coded date) so they stay correct on any run day.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.billing.budget_manager import (
    PLAN_DEFAULTS,
    BudgetConfig,
    BudgetManager,
)
from app.services.billing.cost_tracker import UnifiedCostTracker


@pytest.fixture(autouse=True)
def _reset_billing_singletons():
    """Keep the two process singletons from leaking state across tests."""
    UnifiedCostTracker._instance = None
    BudgetManager._instance = None
    yield
    UnifiedCostTracker._instance = None
    BudgetManager._instance = None


def _other_day_key_this_month() -> str:
    """A 'YYYY-MM-DD' key in the current month that is never today.

    Day 28 exists in every month; if today happens to be the 28th we fall back
    to the 15th. Either way the key shares today's month prefix (so it counts
    toward the monthly total) but differs from today's key (so it does NOT
    count toward the daily total).
    """
    today = date.today()
    other = today.replace(day=28 if today.day != 28 else 15)
    return other.strftime("%Y-%m-%d")


def _seed_tracker_as_singleton(**daily_seed: float) -> UnifiedCostTracker:
    """Build a fresh tracker, optionally seed raw daily totals, install it as
    the singleton that ``BudgetManager`` will read."""
    tracker = UnifiedCostTracker()
    for day_key, amount in daily_seed.items():
        tracker._daily_totals[day_key] = amount
    UnifiedCostTracker._instance = tracker
    return tracker


# ---------------------------------------------------------------------------
# BudgetManager.get_user_defaults -- plan-tier lookup
# ---------------------------------------------------------------------------

def test_get_user_defaults_known_plan():
    pro = BudgetManager.get_user_defaults("PRO")
    assert pro["monthly_credit_usd"] == 10.00
    assert pro["max_tenant_share_pct"] == 50


def test_get_user_defaults_is_case_insensitive():
    assert BudgetManager.get_user_defaults("pro") == BudgetManager.get_user_defaults("PRO")
    assert BudgetManager.get_user_defaults("Enterprise")["overage_action"] == "allow_overage"


def test_get_user_defaults_unknown_plan_falls_back_to_free():
    fallback = BudgetManager.get_user_defaults("does-not-exist")
    assert fallback == PLAN_DEFAULTS["FREE"]
    # Config-drift tripwire: a silent change to the FREE tier price should
    # surface as a failing test, not ship quietly.
    assert fallback["monthly_credit_usd"] == 0.50


def test_get_user_defaults_returns_a_copy():
    defaults = BudgetManager.get_user_defaults("FREE")
    defaults["monthly_credit_usd"] = 999.0
    # Mutating the returned dict must not corrupt the shared PLAN_DEFAULTS table.
    assert PLAN_DEFAULTS["FREE"]["monthly_credit_usd"] == 0.50


# ---------------------------------------------------------------------------
# BudgetManager.check_before_execution -- the decision tree
# ---------------------------------------------------------------------------

def test_check_allows_when_well_under_every_limit():
    _seed_tracker_as_singleton()
    mgr = BudgetManager()
    assert mgr.check_before_execution(0.5) == {"decision": "allow"}


def test_per_task_limit_warns_first():
    # Per-task is checked before daily/monthly, so an empty tracker still warns.
    _seed_tracker_as_singleton()
    mgr = BudgetManager()
    result = mgr.check_before_execution(3.0)  # default per_task_limit is 2.0
    assert result["decision"] == "warn"
    assert "per-task" in result["reason"]


@pytest.mark.parametrize(
    "action,expected",
    [
        ("pause_tasks", "block"),
        ("free_models_only", "free_only"),
        ("warn_only", "warn"),
    ],
)
def test_daily_limit_branch_honors_over_budget_action(action, expected):
    today_key = date.today().strftime("%Y-%m-%d")
    _seed_tracker_as_singleton(**{today_key: 9.5})
    mgr = BudgetManager()
    mgr.config.over_budget_action = action
    # 9.5 used + 1.0 estimated = 10.5 > daily_limit 10.0; 1.0 < per_task 2.0.
    result = mgr.check_before_execution(1.0)
    assert result["decision"] == expected


@pytest.mark.parametrize(
    "action,expected",
    [
        ("pause_tasks", "block"),
        ("free_models_only", "free_only"),
        ("warn_only", "warn"),
    ],
)
def test_monthly_limit_branch_honors_over_budget_action(action, expected):
    # Seed a same-month-but-not-today cost so monthly is high while today's
    # daily stays at 0 -- this forces the decision past the daily branch and
    # into the monthly branch.
    _seed_tracker_as_singleton(**{_other_day_key_this_month(): 49.5})
    mgr = BudgetManager()
    mgr.config.over_budget_action = action
    # daily: 0 + 1.0 = 1.0 < 10 (passes). monthly: 49.5 + 1.0 = 50.5 > 50.
    result = mgr.check_before_execution(1.0)
    assert result["decision"] == expected


def test_alert_thresholds_fire_once_and_dedup():
    # monthly = 30 of 50 -> pct 0.6: crosses the 0.5 threshold only.
    _seed_tracker_as_singleton(**{_other_day_key_this_month(): 30.0})
    mgr = BudgetManager()
    assert mgr.check_before_execution(0.5) == {"decision": "allow"}
    assert 0.5 in mgr._alerts_sent
    assert 0.8 not in mgr._alerts_sent
    # A second call must not re-add or error -- the dedup set is the contract.
    assert mgr.check_before_execution(0.5) == {"decision": "allow"}
    assert mgr._alerts_sent == {0.5}


# ---------------------------------------------------------------------------
# BudgetManager.get_budget_status / update_config
# ---------------------------------------------------------------------------

def test_get_budget_status_reports_used_and_pct():
    today_key = date.today().strftime("%Y-%m-%d")
    _seed_tracker_as_singleton(**{today_key: 5.0})
    mgr = BudgetManager()
    status = mgr.get_budget_status()
    assert status["monthly_used"] == 5.0
    assert status["monthly_pct"] == 10.0  # 5 / 50 * 100
    assert status["daily_used"] == 5.0


def test_get_budget_status_guards_zero_monthly_limit():
    _seed_tracker_as_singleton()
    mgr = BudgetManager()
    mgr.config.monthly_limit = 0.0
    # The guard must return 0, not raise ZeroDivisionError.
    assert mgr.get_budget_status()["monthly_pct"] == 0


def test_update_config_sets_known_keys_and_ignores_unknown():
    mgr = BudgetManager()
    mgr.update_config(daily_limit=99.0, bogus_key="ignored")
    assert mgr.config.daily_limit == 99.0
    assert not hasattr(mgr.config, "bogus_key")


def test_budget_config_defaults_alert_thresholds():
    cfg = BudgetConfig()
    assert cfg.alert_thresholds == [0.5, 0.8, 1.0]


# ---------------------------------------------------------------------------
# UnifiedCostTracker -- the in-memory ledger
# ---------------------------------------------------------------------------

def test_log_usage_aggregates_every_axis():
    tracker = UnifiedCostTracker()
    tracker.log_usage(
        provider="anthropic",
        model="claude",
        input_tokens=100,
        output_tokens=50,
        cost_usd=1.5,
        task_type="code_gen",
        session_id="s1",
    )
    assert tracker.get_daily_cost() == 1.5
    assert tracker.get_session_cost("s1") == 1.5
    assert tracker.get_cost_by_task_type() == {"code_gen": 1.5}
    by_provider = tracker.get_cost_by_provider()
    assert by_provider["anthropic"]["cost_usd"] == 1.5
    assert by_provider["anthropic"]["total_tokens"] == 150
    assert by_provider["anthropic"]["call_count"] == 1


def test_get_daily_cost_unknown_day_is_zero():
    tracker = UnifiedCostTracker()
    assert tracker.get_daily_cost(date(2000, 1, 1)) == 0.0


def test_get_monthly_cost_sums_only_current_month():
    tracker = UnifiedCostTracker()
    tracker._daily_totals[_other_day_key_this_month()] = 4.0
    tracker._daily_totals[date.today().strftime("%Y-%m-%d")] = 1.0
    tracker._daily_totals["1999-01-15"] = 100.0  # a clearly different month
    assert tracker.get_monthly_cost() == 5.0


def test_get_cost_by_project_buckets_none_as_general():
    tracker = UnifiedCostTracker()
    tracker.log_usage(provider="p", model="m", cost_usd=1.0, project_id=None)
    tracker.log_usage(provider="p", model="m", cost_usd=2.0, project_id="proj-x")
    by_project = tracker.get_cost_by_project()
    assert by_project["general"]["cost_usd"] == 1.0
    assert by_project["general"]["task_count"] == 1
    assert by_project["proj-x"]["cost_usd"] == 2.0


def test_get_usage_history_is_chronological_and_windowed():
    tracker = UnifiedCostTracker()
    today_key = date.today().strftime("%Y-%m-%d")
    tracker._daily_totals[today_key] = 7.0
    history = tracker.get_usage_history(days=3)
    assert len(history) == 3
    # Reversed -> oldest first, today last.
    assert history[-1] == {"date": today_key, "cost_usd": 7.0}


def test_entries_are_capped_at_10k():
    tracker = UnifiedCostTracker()
    for _ in range(10_002):
        tracker.log_usage(provider="p", model="m", cost_usd=0.0)
    assert len(tracker._entries) == 10_000


def test_get_overview_composites_the_ledger():
    tracker = UnifiedCostTracker()
    tracker.log_usage(provider="p", model="m", cost_usd=2.0, session_id="sx")
    overview = tracker.get_overview(session_id="sx")
    assert overview["session_cost"] == 2.0
    assert overview["daily_cost"] == 2.0
    assert overview["monthly_cost"] == 2.0
    assert overview["total_entries"] == 1
