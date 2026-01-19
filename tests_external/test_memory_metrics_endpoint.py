from __future__ import annotations

import base64
import os
from pathlib import Path

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


def test_memory_metrics_endpoint_exposes_snapshot(monkeypatch):
    monkeypatch.setenv("DAENA_MONITORING_API_KEY", "test-key")
    incr("nbmf_reads", 3)
    observe("nbmf_read", 0.01)

    client = _build_app()

    resp = client.get("/monitoring/memory", headers={"X-DAENA-API-KEY": "test-key"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["nbmf_reads"] >= 3
    assert "nbmf_read_p95_ms" in data
    assert "divergence_rate" in data


def test_prometheus_endpoint_returns_text(monkeypatch):
    monkeypatch.setenv("DAENA_MONITORING_API_KEY", "test-key")
    incr("nbmf_writes", 2)
    observe("nbmf_write", 0.02)
    client = _build_app()

    resp = client.get("/monitoring/memory/prometheus", headers={"X-DAENA-API-KEY": "test-key"})
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
    write_secure_json(l2_records / "item__chat.json", {"payload": {"msg": "hi"}, "meta": {}})

    monkeypatch.setenv("DAENA_CLOUD_KMS_ENDPOINT", "https://fake-kms.local")
    monkeypatch.setenv("DAENA_CLOUD_KMS_TOKEN", "token")

    def fake_fetch(*args, **kwargs):
        return {"key_material": base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"), "key_version": "v1"}

    monkeypatch.setattr("memory_service.kms.KeyManagementService.fetch_cloud_key_material", lambda self: fake_fetch())

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
    assert '"key_version": "v1"' in log_content[-1]

    manifest_dir = tmp_path / ".kms" / "manifests"
    manifests = list(manifest_dir.glob("*.json"))
    assert manifests, "Rotation manifest should be created"
    validate_result = daena_key_validate.main(["--manifest-dir", str(manifest_dir)])
    assert validate_result == 0
