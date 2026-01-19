from __future__ import annotations

import base64
import os
from pathlib import Path
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routes.monitoring import router as monitoring_router
from memory_service import crypto
from memory_service.crypto import write_secure_json
from memory_service.metrics import incr, observe
from Tools import daena_key_rotate, daena_key_validate


def _build_app() -> TestClient:
    app = FastAPI()
    app.include_router(monitoring_router, prefix="/monitoring")
    return TestClient(app)


def _seed_l2_record(root: Path, name: str, payload: dict, tenant: str = "acme") -> None:
    records = root / ".l2_store" / "records"
    records.mkdir(parents=True, exist_ok=True)
    write_secure_json(
        records / f"{name}__chat.json",
        {
            "payload": payload,
            "cls": "chat",
            "meta": {
                "tenant_id": tenant,
                "compression": {"profile": "default", "mode": "semantic", "settings": {}},
                "emotion5d": {"intensity": 0.9, "valence": 0.8, "dominance": 0.7, "certainty": 0.6},
            },
        },
    )


def test_memory_metrics_endpoint_exposes_snapshot(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    _seed_l2_record(tmp_path, "item", {"summary": "Key customer win"})

    incr("nbmf_reads", 3)
    observe("nbmf_read", 0.01)

    client = _build_app()

    resp = client.get("/monitoring/memory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nbmf_reads"] >= 3
    assert "nbmf_read_p95_ms" in data
    assert "divergence_rate" in data
    assert "storage_stats" in data
    assert "insight_sample" in data
    assert "by_tenant" in data["storage_stats"]["l2"]


def test_memory_stats_endpoint_reports_counts(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    _seed_l2_record(tmp_path, "item2", {"summary": "Retention risk"}, tenant="finance_global")

    client = _build_app()
    resp = client.get("/monitoring/memory/stats")
    assert resp.status_code == 200
    stats = resp.json()
    assert "l2" in stats
    assert stats["l2"]["records"] >= 1
    assert stats["l2"]["by_tenant"].get("finance_global") >= 1


def test_memory_insights_endpoint_returns_items(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    _seed_l2_record(tmp_path, "item3", {"summary": "Expansion opportunity"})

    client = _build_app()
    resp = client.get("/monitoring/memory/insights?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    if body["items"]:
        assert "key" in body["items"][0]
        assert "emotion5d" in body["items"][0]


def test_prometheus_endpoint_returns_text():
    incr("nbmf_writes", 2)
    observe("nbmf_write", 0.02)
    client = _build_app()

    resp = client.get("/monitoring/memory/prometheus")
    assert resp.status_code == 200
    body = resp.text
    assert "daena_memory_metric" in body
    assert 'name="nbmf_writes"' in body.replace(":", "_")


def test_key_rotation_cli_logs_to_kms(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    old_key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    monkeypatch.setenv("DAENA_MEMORY_AES_KEY", old_key)
    crypto.refresh()

    l2_records = tmp_path / ".l2_store" / "records"
    l2_records.mkdir(parents=True)
    write_secure_json(l2_records / "item__chat.json", {"payload": {"msg": "hi"}, "meta": {"cls": "chat"}})

    kms_log = tmp_path / "kms_log.jsonl"
    result = daena_key_rotate.main(
        [
            "--l2",
            str(tmp_path / ".l2_store"),
            "--l3",
            str(tmp_path / ".l3_store"),
            "--kms-log",
            str(kms_log),
            "--key-id",
            "test-key",
            "--manifest-dir",
            str(tmp_path / ".kms" / "manifests"),
        ]
    )
    assert result == 0
    assert kms_log.exists()
    log_content = kms_log.read_text(encoding="utf-8").strip().splitlines()
    assert log_content, "KMS log should contain entries"
    assert '"key_id": "test-key"' in log_content[-1]

    manifest_dir = tmp_path / ".kms" / "manifests"
    manifests = list(manifest_dir.glob("*.json"))
    assert manifests, "Rotation manifest should be created"
    validate_result = daena_key_validate.main(
        ["--manifest-dir", str(manifest_dir)]
    )
    assert validate_result == 0


def test_policy_summary_endpoint(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    policy_cfg = tmp_path / "policy.yaml"
    memory_cfg = tmp_path / "memory.yaml"

    policy_cfg.parent.mkdir(parents=True, exist_ok=True)
    policy_cfg.write_text(
        """
default:
  allow: true
classes:
  chat:
    allow_roles: [agent]
    deny_roles: []
    allow_tenants: [tenant-1]
""".strip(),
        encoding="utf-8",
    )
    memory_cfg.write_text(
        json.dumps(
            {
                "memory_policy": {
                    "fidelity": {
                        "chat": {"mode": "semantic"},
                        "legal": {"mode": "lossless"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("DAENA_POLICY_CONFIG", str(policy_cfg))
    monkeypatch.setenv("DAENA_MEMORY_CONFIG", str(memory_cfg))

    client = _build_app()
    resp = client.get("/monitoring/policy")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["default_allow"] is True
    assert summary["classes"]["chat"]["fidelity"] == "semantic"

    resp_single = client.get("/monitoring/policy", params={"cls": "legal"})
    assert resp_single.status_code == 200
    single = resp_single.json()
    assert "legal" in single["classes"]
    assert single["classes"]["legal"]["fidelity"] == "lossless"

