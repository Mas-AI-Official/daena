"""
Utilities for storing LLM request/response exchanges using NBMF tiers.
"""

from __future__ import annotations

import hashlib
import json
import time
import zlib
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from . import nbmf_encoder
from .caching_cas import CAS
from .ledger import log_event
from .metrics import incr, track_cost
from .router import MemoryRouter
from .simhash_neardup import hamming_distance, near_duplicate, simhash

# Optional tracing support
try:
    from backend.utils.tracing import get_tracing_service, trace_llm_exchange
    TRACING_AVAILABLE = True
except ImportError:
    TRACING_AVAILABLE = False
    def trace_llm_exchange(*args, **kwargs):
        pass


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _normalize_prompt(prompt: str) -> str:
    return " ".join(prompt.split())


@dataclass
class LLMExchangeRecord:
    request_signature: str
    model: str
    model_version: str
    params: Dict[str, Any]
    prompt: str
    response_artifact_key: str
    nbmf_key: str
    embedding_meta: Dict[str, Any]
    provenance: Dict[str, Any]
    ledger_txid: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LLMExchangeStore:
    """
    Stores LLM exchanges across the NBMF tiers while avoiding duplicates via CAS
    and near-duplicate detection via SimHash.
    """

    def __init__(self, router: MemoryRouter, cas: Optional[CAS] = None, simhash_threshold: int = 10):
        self.router = router
        self.cas = cas or CAS(root=".llm_cas")
        self.simhash_threshold = simhash_threshold
        self._simhash_index: Dict[int, str] = {}  # simhash -> signature mapping

    def _signature(self, model: str, version: str, prompt: str, params: Dict[str, Any]) -> str:
        canonical = json.dumps(
            {
                "model": model,
                "version": version,
                "prompt": _normalize_prompt(prompt),
                "params": params,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return _sha256(canonical)

    def _find_near_duplicate(self, prompt: str) -> Optional[str]:
        """Find a near-duplicate prompt using SimHash."""
        prompt_hash = simhash(prompt)
        for stored_hash, stored_sig in self._simhash_index.items():
            if hamming_distance(prompt_hash, stored_hash) <= self.simhash_threshold:
                cached = self.cas.get(stored_sig)
                if cached:
                    return stored_sig
        return None

    def persist(
        self,
        *,
        model: str,
        version: str,
        prompt: str,
        params: Dict[str, Any],
        response_json: Dict[str, Any],
        response_text: str,
        tenant_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        latency_ms: Optional[float] = None,
        usd_cost: Optional[float] = None,
    ) -> LLMExchangeRecord:
        signature = self._signature(model, version, prompt, params)
        cached = self.cas.get(signature)
        if cached:
            incr("llm_cas_hit")
            # Track cost savings from CAS reuse
            if usd_cost:
                track_cost("llm_api_saved", usd_cost)
            # Trace LLM exchange
            if TRACING_AVAILABLE:
                trace_llm_exchange(model, cas_hit=True, near_dup=False)
            log_event(
                action="llm_cas_hit",
                ref=signature,
                store="cas",
                route="exact_match",
                extra={"model": model, "version": version},
            )
            return LLMExchangeRecord(**cached)

        # Try near-duplicate detection
        near_dup_sig = self._find_near_duplicate(prompt)
        if near_dup_sig:
            incr("llm_near_dup_reuse")
            # Track cost savings from near-duplicate reuse
            if usd_cost:
                track_cost("llm_api_saved", usd_cost)
            # Trace LLM exchange
            if TRACING_AVAILABLE:
                trace_llm_exchange(model, cas_hit=False, near_dup=True)
            cached = self.cas.get(near_dup_sig)
            if cached:
                log_event(
                    action="llm_near_dup_reuse",
                    ref=signature,
                    store="cas",
                    route="simhash_match",
                    extra={"model": model, "version": version, "original_sig": near_dup_sig},
                )
                return LLMExchangeRecord(**cached)

        incr("llm_cas_miss")
        # Track actual cost for new LLM requests
        if usd_cost:
            track_cost("llm_api", usd_cost)
        # Trace LLM exchange
        if TRACING_AVAILABLE:
            trace_llm_exchange(model, cas_hit=False, near_dup=False)

        raw_key = self.router.store_raw_artifact(
            {
                "data": zlib.compress(json.dumps(response_json, ensure_ascii=False).encode("utf-8"), level=9).hex(),
                "schema": "zstd-json",
            }
        )

        nbmf = nbmf_encoder.encode(response_text, fidelity="semantic")
        provenance = {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "created_at": time.time(),
            "latency_ms": latency_ms,
            "usd_cost": usd_cost,
        }
        nbmf_payload = {
            "response_text": response_text,
            "nbmf": nbmf,
            "model": model,
            "model_version": version,
        }
        nbmf_result = self.router.write_nbmf_only(
            signature,
            "llm_exchange",
            nbmf_payload,
            {"params": params, "provenance": provenance},
        )
        nbmf_key = nbmf_result.get("txid", "")

        self.router.l1.index(signature, response_text, {"cls": "llm_exchange"})

        record = LLMExchangeRecord(
            request_signature=signature,
            model=model,
            model_version=version,
            params=params,
            prompt=_normalize_prompt(prompt),
            response_artifact_key=raw_key,
            nbmf_key=nbmf_key,
            embedding_meta={"signature": signature},
            provenance=provenance,
        )

        self.cas.put(signature, record.to_dict())
        # Index SimHash for future near-duplicate detection
        prompt_hash = simhash(prompt)
        self._simhash_index[prompt_hash] = signature
        return record

