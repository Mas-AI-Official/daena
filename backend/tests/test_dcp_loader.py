"""Tests for DCP loader and Council/Quintessence restoration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.dcp_loader import DCPLoader

# ── Fixtures ──


@pytest.fixture
def sample_config(tmp_path: Path) -> Path:
    """Create a minimal DCP config for testing."""
    config = {
        "domains": {
            "ENGINEERING": {
                "scope": "Software architecture",
                "experts": [
                    {
                        "id": "ENG-01",
                        "archetype": "Systems Reliability Architect",
                        "prompt_directive": "You are a Systems Reliability Architect.",
                        "decision_priorities": ["availability", "fault_tolerance"],
                        "blind_spots": ["Over-engineers for reliability"],
                        "evaluation_criteria": ["Clear failure modes?"],
                    },
                    {
                        "id": "ENG-02",
                        "archetype": "Distributed Systems Engineer",
                        "prompt_directive": "You are a Distributed Systems Engineer.",
                        "decision_priorities": ["consistency", "partition_tolerance"],
                        "blind_spots": ["Defaults to strong consistency"],
                        "evaluation_criteria": ["Consistency guarantees stated?"],
                    },
                ],
            },
            "PRODUCT": {
                "scope": "Product strategy",
                "experts": [
                    {
                        "id": "PRD-01",
                        "archetype": "Product Strategist",
                        "prompt_directive": "You are a Product Strategist.",
                        "decision_priorities": ["user_problem_validation"],
                        "blind_spots": ["Over-indexes on frameworks"],
                        "evaluation_criteria": ["Problem validated?"],
                    },
                ],
            },
            "DESIGN": {
                "scope": "Visual design",
                "experts": [],
            },
        },
        "intent_to_domains": {
            "CODE_GENERATION": ["ENGINEERING", "DESIGN"],
            "ANALYSIS": ["PRODUCT", "ENGINEERING"],
            "AMBIGUOUS": ["ENGINEERING", "PRODUCT"],
        },
    }
    path = tmp_path / "dcps.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


@pytest.fixture
def loader(sample_config: Path) -> DCPLoader:
    """Create a DCPLoader with sample config."""
    ldr = DCPLoader(config_path=sample_config)
    ldr.load()
    return ldr


# ── Loading ──


class TestDCPLoading:
    def test_load_counts(self, loader: DCPLoader) -> None:
        assert loader.total_experts == 3

    def test_load_idempotent(self, loader: DCPLoader) -> None:
        loader.load()
        loader.load()
        assert loader.total_experts == 3

    def test_missing_config_file(self, tmp_path: Path) -> None:
        ldr = DCPLoader(config_path=tmp_path / "nonexistent.json")
        ldr.load()
        assert ldr.total_experts == 0

    def test_invalid_json(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("not json {{{", encoding="utf-8")
        ldr = DCPLoader(config_path=bad)
        ldr.load()
        assert ldr.total_experts == 0


# ── Domain lookups ──


class TestDomainLookups:
    def test_get_domain(self, loader: DCPLoader) -> None:
        domain = loader.get_domain("ENGINEERING")
        assert domain is not None
        assert domain.name == "ENGINEERING"
        assert len(domain.experts) == 2

    def test_get_domain_case_insensitive(self, loader: DCPLoader) -> None:
        domain = loader.get_domain("engineering")
        assert domain is not None

    def test_get_nonexistent_domain(self, loader: DCPLoader) -> None:
        assert loader.get_domain("NONEXISTENT") is None

    def test_empty_domain_has_no_experts(self, loader: DCPLoader) -> None:
        domain = loader.get_domain("DESIGN")
        assert domain is not None
        assert len(domain.experts) == 0

    def test_populated_domains(self, loader: DCPLoader) -> None:
        populated = loader.get_populated_domains()
        assert len(populated) == 2
        names = {d.name for d in populated}
        assert names == {"ENGINEERING", "PRODUCT"}

    def test_all_domains(self, loader: DCPLoader) -> None:
        all_domains = loader.get_all_domains()
        assert len(all_domains) == 3


# ── Expert lookups ──


class TestExpertLookups:
    def test_get_expert_by_id(self, loader: DCPLoader) -> None:
        expert = loader.get_expert("ENG-01")
        assert expert is not None
        assert expert.archetype == "Systems Reliability Architect"
        assert expert.domain == "ENGINEERING"

    def test_get_nonexistent_expert(self, loader: DCPLoader) -> None:
        assert loader.get_expert("FAKE-99") is None

    def test_expert_has_prompt_directive(self, loader: DCPLoader) -> None:
        expert = loader.get_expert("ENG-01")
        assert expert is not None
        assert "Systems Reliability Architect" in expert.prompt_directive

    def test_expert_has_blind_spots(self, loader: DCPLoader) -> None:
        expert = loader.get_expert("ENG-01")
        assert expert is not None
        assert len(expert.blind_spots) > 0

    def test_expert_frozen(self, loader: DCPLoader) -> None:
        expert = loader.get_expert("ENG-01")
        assert expert is not None
        with pytest.raises(AttributeError):
            expert.archetype = "Modified"  # type: ignore[misc]


# ── Intent mapping ──


class TestIntentMapping:
    def test_intent_to_domains(self, loader: DCPLoader) -> None:
        domains = loader.get_domains_for_intent("CODE_GENERATION")
        assert domains == ["ENGINEERING", "DESIGN"]

    def test_unknown_intent_defaults(self, loader: DCPLoader) -> None:
        domains = loader.get_domains_for_intent("UNKNOWN_INTENT")
        assert domains == ["ENGINEERING", "PRODUCT", "STRATEGY"]

    def test_experts_for_intent(self, loader: DCPLoader) -> None:
        experts = loader.get_experts_for_intent("ANALYSIS", count=3)
        # ANALYSIS maps to PRODUCT, ENGINEERING
        # Should get PRD-01 and ENG-01 (one per domain)
        assert len(experts) == 2
        ids = {e.id for e in experts}
        assert "PRD-01" in ids
        assert "ENG-01" in ids

    def test_experts_for_intent_respects_count(self, loader: DCPLoader) -> None:
        experts = loader.get_experts_for_intent("ANALYSIS", count=1)
        assert len(experts) == 1

    def test_experts_for_intent_with_empty_domain(self, loader: DCPLoader) -> None:
        # CODE_GENERATION maps to ENGINEERING, DESIGN
        # DESIGN has no experts, so should only get ENGINEERING experts
        experts = loader.get_experts_for_intent("CODE_GENERATION", count=3)
        assert len(experts) == 1
        assert experts[0].domain == "ENGINEERING"


# ── Real config file ──


class TestRealConfig:
    def test_real_config_loads(self) -> None:
        """Verify the actual dcps.json ships correctly."""
        ldr = DCPLoader()
        ldr.load()
        # Should have 25 experts (5 domains x 5 each)
        assert ldr.total_experts == 25

    def test_real_config_has_engineering(self) -> None:
        ldr = DCPLoader()
        ldr.load()
        domain = ldr.get_domain("ENGINEERING")
        assert domain is not None
        assert len(domain.experts) == 5

    def test_real_config_has_product(self) -> None:
        ldr = DCPLoader()
        ldr.load()
        domain = ldr.get_domain("PRODUCT")
        assert domain is not None
        assert len(domain.experts) == 5

    def test_real_config_has_design(self) -> None:
        ldr = DCPLoader()
        ldr.load()
        domain = ldr.get_domain("DESIGN")
        assert domain is not None
        assert len(domain.experts) == 5

    def test_real_config_has_security(self) -> None:
        ldr = DCPLoader()
        ldr.load()
        domain = ldr.get_domain("SECURITY")
        assert domain is not None
        assert len(domain.experts) == 5

    def test_real_config_has_strategy(self) -> None:
        ldr = DCPLoader()
        ldr.load()
        domain = ldr.get_domain("STRATEGY")
        assert domain is not None
        assert len(domain.experts) == 5

    def test_real_config_stub_domains_empty(self) -> None:
        ldr = DCPLoader()
        ldr.load()
        for stub in ["MARKETING", "FINANCE", "LEGAL", "SALES",
                      "OPERATIONS", "RESEARCH"]:
            domain = ldr.get_domain(stub)
            assert domain is not None, f"{stub} domain missing"
            assert len(domain.experts) == 0, f"{stub} should have 0 experts"

    def test_real_config_intent_mapping(self) -> None:
        ldr = DCPLoader()
        ldr.load()
        # CODE_GENERATION should map to ENGINEERING, DESIGN
        domains = ldr.get_domains_for_intent("CODE_GENERATION")
        assert "ENGINEERING" in domains
