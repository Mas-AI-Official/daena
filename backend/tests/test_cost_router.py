"""Unit coverage for ``app.services.cost_router.CostAwareRouter``.

Cost-aware model selection: classify a message with zero-token keyword
matching, then pick which models serve the user's chosen reasoning mode. The
router NEVER changes the mode -- it only decides WHICH models run, and it does
so to control spend (routing a one-word greeting to a 30B model is real money
wasted; routing code to a weak model is real quality lost).

The class is pure logic with no DB / network / async / singleton state, so
every branch is a plain synchronous assertion. ``available_models`` items are
dicts shaped ``{"id": ..., "provider": ...}`` exactly as the router consumes
them.
"""
from __future__ import annotations

import pytest

from app.services.cost_router import CostAwareRouter


@pytest.fixture()
def router() -> CostAwareRouter:
    return CostAwareRouter()


def _ollama(*ids: str) -> list[dict]:
    return [{"id": i, "provider": "ollama"} for i in ids]


# ---------------------------------------------------------------------------
# classify_task -- zero-token keyword classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "message,expected",
    [
        ("hi", "SIMPLE"),                       # exact simple match
        ("hello there", "SIMPLE"),              # simple keyword + space prefix
        ("thanks, that helped", "SIMPLE"),      # simple keyword + comma prefix
        ("Fix this python bug", "CODE"),        # 3 code keywords
        ("Compare and analyze these", "RESEARCH"),  # 2 research keywords
        ("Tell me about the weather", "REASONING"),  # nothing matches -> default
    ],
)
def test_classify_task_buckets(router, message, expected):
    assert router.classify_task(message) == expected


def test_classify_requires_two_keywords_for_code(router):
    # A single code keyword is not enough -> falls through to REASONING.
    assert router.classify_task("write some code") == "REASONING"


def test_classify_code_takes_precedence_over_research(router):
    # Message carries >=2 research AND >=2 code keywords; CODE is checked first.
    assert router.classify_task("research and review the api code bug") == "CODE"


def test_classify_simple_short_circuits_before_code(router):
    # "help" is a SIMPLE keyword and is matched before the code scan, even
    # though "debug"/"code" follow it.
    assert router.classify_task("help me debug this code") == "SIMPLE"


# ---------------------------------------------------------------------------
# select_models_for_mode -- empty guard
# ---------------------------------------------------------------------------

def test_select_returns_empty_when_no_models(router):
    assert router.select_models_for_mode("STANDARD", "SIMPLE", []) == []


# ---------------------------------------------------------------------------
# select_models_for_mode -- STANDARD mode
# ---------------------------------------------------------------------------

def test_standard_simple_picks_cheapest_preferred(router):
    models = _ollama("llama3.1:8b", "mistral:7b")
    # mistral:7b is first in the cheapest-preference list.
    assert router.select_models_for_mode("STANDARD", "SIMPLE", models) == ["mistral:7b"]


def test_standard_simple_cheapest_falls_back_to_first_ollama(router):
    models = _ollama("some-other:13b", "another:7b")
    assert router.select_models_for_mode("STANDARD", "SIMPLE", models) == ["some-other:13b"]


def test_standard_simple_cheapest_falls_back_to_first_model_when_no_ollama(router):
    models = [{"id": "claude-sonnet", "provider": "claude_code"}]
    assert router.select_models_for_mode("STANDARD", "SIMPLE", models) == ["claude-sonnet"]


def test_standard_code_prefers_coder_model(router):
    models = _ollama("qwen2.5-coder:14b", "mistral:7b")
    assert router.select_models_for_mode("STANDARD", "CODE", models) == ["qwen2.5-coder:14b"]


def test_standard_code_falls_back_to_codex_cli(router):
    models = [
        {"id": "mistral:7b", "provider": "ollama"},
        {"id": "gpt-codex", "provider": "codex"},
    ]
    assert router.select_models_for_mode("STANDARD", "CODE", models) == ["gpt-codex"]


def test_standard_reasoning_honors_primary_mind(router):
    models = _ollama("deepseek-r1:14b") + [{"id": "claude-x", "provider": "claude_code"}]
    result = router.select_models_for_mode("STANDARD", "REASONING", models, primary_mind="claude-x")
    assert result == ["claude-x"]


def test_standard_reasoning_smartest_without_primary(router):
    models = _ollama("mistral:7b", "deepseek-r1:14b")
    # No primary_mind -> first preferred reasoning model wins.
    assert router.select_models_for_mode("STANDARD", "REASONING", models) == ["deepseek-r1:14b"]


# ---------------------------------------------------------------------------
# select_models_for_mode -- COUNCIL / QUINTESSENCE -> three diverse models
# ---------------------------------------------------------------------------

def test_council_picks_three_diverse_models(router):
    models = _ollama("deepseek-r1:14b", "qwen2.5-coder:14b", "mistral:7b")
    result = router.select_models_for_mode("COUNCIL", "REASONING", models)
    assert result == ["deepseek-r1:14b", "qwen2.5-coder:14b", "mistral:7b"]


def test_quintessence_uses_same_diverse_three(router):
    models = _ollama("deepseek-r1:14b", "qwen2.5-coder:14b", "mistral:7b")
    assert (
        router.select_models_for_mode("QUINTESSENCE", "REASONING", models)
        == router.select_models_for_mode("COUNCIL", "REASONING", models)
    )


def test_council_pads_when_only_one_model(router):
    # "single-model Council still works" -> padded to length 3.
    models = _ollama("solo:7b")
    assert router.select_models_for_mode("COUNCIL", "REASONING", models) == [
        "solo:7b",
        "solo:7b",
        "solo:7b",
    ]


# ---------------------------------------------------------------------------
# select_models_for_mode -- AUTO mode
# ---------------------------------------------------------------------------

def test_auto_simple_picks_cheapest(router):
    models = _ollama("mistral:7b", "deepseek-r1:14b")
    assert router.select_models_for_mode("AUTO", "SIMPLE", models) == ["mistral:7b"]


def test_auto_with_three_plus_models_goes_diverse(router):
    models = _ollama("deepseek-r1:14b", "qwen2.5-coder:14b", "mistral:7b")
    result = router.select_models_for_mode("AUTO", "REASONING", models)
    assert len(result) == 3


def test_auto_with_few_models_picks_smartest_single(router):
    models = _ollama("mistral:7b", "deepseek-r1:14b")
    result = router.select_models_for_mode("AUTO", "REASONING", models)
    assert result == ["deepseek-r1:14b"]


def test_unknown_mode_defaults_to_smartest_single(router):
    models = _ollama("deepseek-r1:14b", "mistral:7b")
    assert router.select_models_for_mode("WHATEVER", "REASONING", models) == ["deepseek-r1:14b"]


# ---------------------------------------------------------------------------
# get_auto_reasoning_mode
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "task_type,model_count,expected",
    [
        ("SIMPLE", 5, "STANDARD"),    # simple work is never a council
        ("REASONING", 5, "COUNCIL"),  # enough models -> council
        ("REASONING", 2, "STANDARD"),  # too few models -> standard
    ],
)
def test_get_auto_reasoning_mode(router, task_type, model_count, expected):
    assert router.get_auto_reasoning_mode(task_type, model_count) == expected
