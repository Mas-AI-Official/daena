from __future__ import annotations

from memory_service.trust_manager import TrustManager


def test_trust_manager_detects_text_divergence():
    manager = TrustManager()
    assessment = manager.assess("chat", "hello world", reference="goodbye world")
    assert assessment.divergence > 0.2
    assert not assessment.promote


def test_trust_manager_detects_structured_issues():
    manager = TrustManager()
    reference = {"amount": 100, "currency": "USD"}
    candidate = {"amount": 90, "currency": "EUR", "note": "adjusted"}
    assessment = manager.assess("finance", candidate, reference=reference)
    assert "value_shift:amount" in assessment.issues or "value_shift" in " ".join(assessment.issues)
    assert assessment.divergence > 0
    assert not manager.should_promote(assessment)


def test_trust_manager_critical_abort_threshold():
    manager = TrustManager()
    assessment = manager.assess("legal", "A", reference="B")
    assert manager.requires_abort("legal", assessment.divergence)

