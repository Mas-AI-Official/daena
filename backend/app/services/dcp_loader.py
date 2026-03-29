"""DCP Loader: loads Decision Constraint Profiles for Quintessence mode.

Reads the DCP configuration from app/config/dcps.json once at startup
and provides fast lookups by domain and intent.

DCPs define how expert archetypes reason about problems:
- prompt_directive: injected into the LLM system prompt
- decision_priorities: what the expert optimizes for
- blind_spots: known weaknesses (used by synthesis to compensate)
- evaluation_criteria: how to judge the answer

Usage::

    loader = DCPLoader()
    experts = loader.get_experts_for_intent("CODE_GENERATION", count=3)
    domains = loader.get_domains_for_intent("ANALYSIS")
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "dcps.json"


@dataclass(frozen=True, slots=True)
class DCPExpert:
    """A single Decision Constraint Profile expert."""

    id: str
    domain: str
    archetype: str
    prompt_directive: str
    decision_priorities: tuple[str, ...]
    blind_spots: tuple[str, ...]
    evaluation_criteria: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DCPDomain:
    """A domain containing up to 5 experts."""

    name: str
    scope: str
    experts: tuple[DCPExpert, ...]


class DCPLoader:
    """Loads and caches DCP definitions from the JSON config.

    Thread-safe: the config is loaded once and stored as frozen
    dataclasses. No mutation after initialization.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._path = config_path or _CONFIG_PATH
        self._domains: dict[str, DCPDomain] = {}
        self._experts: dict[str, DCPExpert] = {}
        self._intent_map: dict[str, list[str]] = {}
        self._loaded = False

    def load(self) -> None:
        """Load DCP config from disk. Idempotent."""
        if self._loaded:
            return

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning("dcp_loader.config_not_found", path=str(self._path))
            self._loaded = True
            return
        except json.JSONDecodeError as exc:
            logger.error("dcp_loader.invalid_json", path=str(self._path), error=str(exc))
            self._loaded = True
            return

        domains_raw = raw.get("domains", {})
        for domain_name, domain_data in domains_raw.items():
            experts = []
            for exp in domain_data.get("experts", []):
                expert = DCPExpert(
                    id=exp["id"],
                    domain=domain_name,
                    archetype=exp["archetype"],
                    prompt_directive=exp["prompt_directive"],
                    decision_priorities=tuple(exp.get("decision_priorities", [])),
                    blind_spots=tuple(exp.get("blind_spots", [])),
                    evaluation_criteria=tuple(exp.get("evaluation_criteria", [])),
                )
                experts.append(expert)
                self._experts[expert.id] = expert

            self._domains[domain_name] = DCPDomain(
                name=domain_name,
                scope=domain_data.get("scope", ""),
                experts=tuple(experts),
            )

        self._intent_map = raw.get("intent_to_domains", {})
        self._loaded = True

        total_experts = len(self._experts)
        total_domains = sum(1 for d in self._domains.values() if d.experts)
        logger.info(
            "dcp_loader.loaded",
            total_experts=total_experts,
            total_domains=total_domains,
            path=str(self._path),
        )

    def get_domain(self, name: str) -> DCPDomain | None:
        """Get a domain by name (case-insensitive)."""
        self.load()
        return self._domains.get(name.upper())

    def get_expert(self, expert_id: str) -> DCPExpert | None:
        """Get a single expert by ID (e.g. 'ENG-01')."""
        self.load()
        return self._experts.get(expert_id)

    def get_domains_for_intent(self, intent: str) -> list[str]:
        """Map a QueryUnderstanding intent to relevant domains."""
        self.load()
        return self._intent_map.get(intent.upper(), ["ENGINEERING", "PRODUCT", "STRATEGY"])

    def get_experts_for_intent(
        self,
        intent: str,
        count: int = 3,
    ) -> list[DCPExpert]:
        """Select experts for a given intent.

        Picks one expert per relevant domain (round-robin through
        domain experts). Ensures diverse perspectives.

        Args:
            intent: QueryUnderstanding intent string.
            count: Maximum number of experts to return.

        Returns:
            List of DCPExpert instances, one per domain, up to count.
        """
        self.load()
        domain_names = self.get_domains_for_intent(intent)
        selected: list[DCPExpert] = []

        for domain_name in domain_names:
            if len(selected) >= count:
                break
            domain = self._domains.get(domain_name)
            if domain and domain.experts:
                # Pick the first expert from each domain
                # (Phase 2: could use blind-spot complementarity scoring)
                selected.append(domain.experts[0])

        return selected

    def get_all_domains(self) -> list[DCPDomain]:
        """List all domains (including empty stubs)."""
        self.load()
        return list(self._domains.values())

    def get_populated_domains(self) -> list[DCPDomain]:
        """List only domains that have experts defined."""
        self.load()
        return [d for d in self._domains.values() if d.experts]

    @property
    def total_experts(self) -> int:
        """Count of all loaded experts."""
        self.load()
        return len(self._experts)


@lru_cache
def get_dcp_loader() -> DCPLoader:
    """Singleton DCP loader instance."""
    loader = DCPLoader()
    loader.load()
    return loader
