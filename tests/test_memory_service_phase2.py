from __future__ import annotations

import json
import base64
import os
from pathlib import Path

import pytest

from memory_service import nbmf_decoder, nbmf_encoder
from memory_service.caching_cas import CAS
from memory_service import crypto as crypto_utils
from memory_service.delta_encoding import apply_text_diff, text_diff
from memory_service.emotion5d import pack as pack_emotion
from memory_service.expression_adapter import render as render_expression
from memory_service.llm_exchange import LLMExchangeStore
from memory_service.memory_bootstrap import run_bootstrap
from memory_service.quantized_latents import fp16_pack, int8_pack
from memory_service.router import MemoryRouter
from memory_service.trust_manager import TrustManager


def _temp_config(tmp_path: Path):
    return {
        "memory_policy": {
            "fidelity": {
                "legal": {"mode": "lossless"},
                "chat": {"mode": "semantic"},
            }
        },
        "flags": {
            "nbmf_enabled": True,
            "dual_write": True,
            "read_mode": "hybrid",
            "canary_percent": 100,
        },
    }


def test_nbmf_roundtrip_lossless():
    payload = {"hello": "world", "count": 3}
    encoded = nbmf_encoder.encode(payload, fidelity="lossless")
    assert encoded["meta"]["fidelity"] == "lossless"
    decoded = nbmf_decoder.decode(encoded)
    assert decoded == payload


def test_nbmf_semantic_preview():
    text = "This is a long sentence that should be normalized."
    encoded = nbmf_encoder.encode(text, fidelity="semantic")
    preview = nbmf_decoder.decode(encoded)
    assert "long sentence" in preview


def test_router_policy_and_storage(tmp_path: Path):
    router = MemoryRouter(config=_temp_config(tmp_path))
    router.write("item-1", "chat", {"note": "hello"})
    stored = router.l2.get_record("item-1", "chat")
    assert stored["note"] == "hello"


def test_cas_reuse(tmp_path: Path):
    cas = CAS(root=tmp_path / "cas")
    key = cas.key({"a": 1})
    path1 = cas.put(key, {"a": 1})
    path2 = cas.put(key, {"a": 1})
    assert path1 == path2
    loaded = cas.get(key)
    assert loaded == {"a": 1}


def test_ledger_records(tmp_path: Path):
    router = MemoryRouter()
    result = router.write("item-ledger", "legal", {"document": "content"}, policy_ctx={"role": "legal.officer"})
    assert result["txid"]


def test_delta_encoding_stub():
    diff = text_diff("hello", "hello world")
    assert diff
    restored = apply_text_diff("hello", diff)
    assert restored == "hello world"


def test_quantized_latents():
    vec = [0.1, -0.5, 0.75]
    fp16 = fp16_pack(vec)
    int8 = int8_pack(vec)
    assert fp16 == vec
    assert len(int8) == len(vec)


def test_trust_manager_should_promote():
    manager = TrustManager()
    assessment = manager.assess(
        "chat",
        "hello world",
        reference="hello world!",
        hallucination_scores=[0.0, 0.05],
        related_texts=["hello world", "hello world!"],
    )
    assert assessment.promote
    assert manager.should_promote(assessment)
    # Backwards compatibility with float trust value
    trust = manager.compute_trust(["hello world", "hello world!"], [0.0, 0.05])
    assert manager.should_promote(trust)


def test_emotion_and_expression():
    emotion = pack_emotion(0.2, 0.8, 0.4, 0.5, 0.3, 0.9, ["support"])
    assert emotion["intensity"] == pytest.approx(0.9)
    rendered = render_expression("We will handle this.", emotion)
    assert "I hear you" in rendered


def test_llm_exchange_store(tmp_path: Path):
    router = MemoryRouter()
    store = LLMExchangeStore(router=router, cas=CAS(root=tmp_path / "llm"))
    record = store.persist(
        model="gpt-5",
        version="2025-11-01",
        prompt="Summarize quarterly metrics.",
        params={"temperature": 0.2},
        response_json={"text": "Quarterly revenue increased."},
        response_text="Quarterly revenue increased.",
        tenant_id="tenant-1",
        agent_id="agent-research",
        latency_ms=1200,
        usd_cost=0.08,
    )
    assert record.request_signature
    cached = store.persist(
        model="gpt-5",
        version="2025-11-01",
        prompt="Summarize quarterly metrics.",
        params={"temperature": 0.2},
        response_json={"text": "Quarterly revenue increased."},
        response_text="Quarterly revenue increased.",
    )
    assert cached.request_signature == record.request_signature


def test_bootstrap_detects_modules():
    report = run_bootstrap()
    assert report.config_exists is True
    assert not report.missing_modules


def test_secure_store_encryption_and_metadata(tmp_path: Path, monkeypatch):
    key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    monkeypatch.setenv("DAENA_MEMORY_AES_KEY", key)
    crypto_utils.refresh()
    monkeypatch.chdir(tmp_path)
    router = MemoryRouter(config=_temp_config(tmp_path))
    payload = {"note": "classified"}
    emotion_meta = {"emotion": {"valence": 0.6}}
    router.write("secure-item", "chat", payload, emotion_meta=emotion_meta)
    record_files = list((Path(".l2_store") / "records").glob("secure-item__chat.json"))
    assert record_files, "encrypted record should be on disk"
    content = json.loads(record_files[0].read_text(encoding="utf-8"))
    assert "__encrypted__" in content
    restored = router.read_nbmf_only("secure-item", "chat")
    assert restored["note"] == "classified"
    assert restored["__meta__"]["emotion"]["valence"] == pytest.approx(0.6)
    monkeypatch.delenv("DAENA_MEMORY_AES_KEY", raising=False)
    crypto_utils.refresh()


def test_metadata_propagation_for_string_payload(tmp_path: Path):
    router = MemoryRouter(config=_temp_config(tmp_path))
    router.write("string-item", "chat", "greetings", emotion_meta={"emotion": {"tone": "warm"}})
    value = router.read_nbmf_only("string-item", "chat")
    assert value["value"] == "greetings"
    assert value["__meta__"]["emotion"]["tone"] == "warm"

