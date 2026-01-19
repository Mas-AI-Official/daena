#!/usr/bin/env python3
"""
Seed Enterprise-DNA for the default tenant so the UI doesn't show "DNA: not_configured".

Safe/idempotent: only writes if missing.
"""

from __future__ import annotations

from backend.services.enterprise_dna_service import EnterpriseDNAService
from backend.models.enterprise_dna import Epigenome


def main() -> int:
    service = EnterpriseDNAService()
    tenant_id = "default"

    existing = service.get_epigenome(tenant_id)
    if existing:
        print("DNA default tenant already configured.")
        return 0

    epi = Epigenome(
        tenant_id=tenant_id,
        jurisdictions=["local-dev"],
        feature_flags={
            "dna_enabled": True,
            "metrics_enabled": True,
            "realtime_updates": True,
        },
        retention_policy={
            "max_days": 30,
            "max_records": 5000,
        },
        slo={
            "p95_latency_ms": 250.0,
            "error_rate_max": 0.01,
        },
        sla={
            "uptime_target": 0.997,
        },
        abac_rules={
            "mode": "no-auth-dev",
            "allow_all": True,
        },
    )

    ok = service.save_epigenome(epi)
    if ok:
        print("DNA default tenant configured.")
        return 0
    print("Failed to configure DNA default tenant.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())











