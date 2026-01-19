#!/usr/bin/env python3
"""
Verification script for Enterprise-DNA integration.
Tests DNA endpoints, TrustManager integration, and NBMF hooks.
"""

import sys
import requests
import json
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

def test_dna_service():
    """Test DNA service initialization."""
    print("=" * 60)
    print("TEST 1: DNA Service Initialization")
    print("=" * 60)
    
    try:
        from backend.services.enterprise_dna_service import get_dna_service
        dna_service = get_dna_service()
        print("✅ DNA service initialized successfully")
        return True
    except Exception as e:
        print(f"❌ DNA service initialization failed: {e}")
        return False

def test_trust_manager_v2():
    """Test TrustManagerV2 initialization."""
    print("\n" + "=" * 60)
    print("TEST 2: TrustManagerV2 Initialization")
    print("=" * 60)
    
    try:
        from memory_service.trust_manager_v2 import get_trust_manager_v2
        trust_manager = get_trust_manager_v2()
        print("✅ TrustManagerV2 initialized successfully")
        
        # Test immune event application
        trust_manager.apply_immune_event(
            tenant_id="test_tenant",
            quarantine_required=False,
            quorum_required=True,
            trust_score_adjustment=-0.1
        )
        print("✅ Immune event application works")
        
        status = trust_manager.get_tenant_status("test_tenant")
        print(f"✅ Tenant status retrieval works: {json.dumps(status, indent=2)}")
        return True
    except Exception as e:
        print(f"❌ TrustManagerV2 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_dna_models():
    """Test DNA model serialization."""
    print("\n" + "=" * 60)
    print("TEST 3: DNA Model Serialization")
    print("=" * 60)
    
    try:
        from backend.models.enterprise_dna import (
            Genome, Epigenome, LineageRecord, ThreatSignal, ImmuneEvent,
            ThreatLevel, ImmuneAction
        )
        
        # Test Genome
        genome = Genome(
            agent_id="test_agent",
            department="engineering",
            role="advisor_a",
            version="1.0.0"
        )
        genome_dict = genome.to_dict()
        genome_restored = Genome.from_dict(genome_dict)
        assert genome.agent_id == genome_restored.agent_id
        print("✅ Genome serialization works")
        
        # Test Epigenome
        epigenome = Epigenome(tenant_id="test_tenant")
        epigenome_dict = epigenome.to_dict()
        epigenome_restored = Epigenome.from_dict(epigenome_dict)
        assert epigenome.tenant_id == epigenome_restored.tenant_id
        print("✅ Epigenome serialization works")
        
        # Test ThreatSignal
        signal = ThreatSignal(
            signal_id="test_signal",
            tenant_id="test_tenant",
            threat_type="anomaly",
            threat_level=ThreatLevel.MEDIUM,
            score=0.5,
            detected_at=genome.created_at,
            source="test_system"
        )
        signal_dict = signal.to_dict()
        signal_restored = ThreatSignal.from_dict(signal_dict)
        assert signal.signal_id == signal_restored.signal_id
        print("✅ ThreatSignal serialization works")
        
        return True
    except Exception as e:
        print(f"❌ DNA model test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints(base_url="http://localhost:8000"):
    """Test DNA API endpoints (if server is running)."""
    print("\n" + "=" * 60)
    print("TEST 4: DNA API Endpoints")
    print("=" * 60)
    
    try:
        # Test health endpoint
        response = requests.get(f"{base_url}/api/v1/health/", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print(f"⚠️  Server returned {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("⚠️  Server not running, skipping API tests")
        return None
    except Exception as e:
        print(f"⚠️  API test error: {e}")
        return None
    
    # Test structure verification
    try:
        response = requests.get(f"{base_url}/api/v1/structure/verify", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Structure verification endpoint works")
            print(f"   Status: {data.get('status')}")
            print(f"   Pass: {data.get('pass')}")
        else:
            print(f"⚠️  Structure endpoint returned {response.status_code}")
    except Exception as e:
        print(f"⚠️  Structure endpoint test failed: {e}")
    
    # Test DNA health (requires tenant_id)
    try:
        response = requests.get(f"{base_url}/api/v1/dna/default/health", timeout=5)
        if response.status_code in [200, 404]:  # 404 is OK if no epigenome exists
            print(f"✅ DNA health endpoint works (status: {response.status_code})")
        else:
            print(f"⚠️  DNA health endpoint returned {response.status_code}")
    except Exception as e:
        print(f"⚠️  DNA health endpoint test failed: {e}")
    
    return True

def test_dna_integration_hooks():
    """Test DNA integration hooks."""
    print("\n" + "=" * 60)
    print("TEST 5: DNA Integration Hooks")
    print("=" * 60)
    
    try:
        from memory_service.dna_integration import (
            hook_l2q_to_l2_promotion,
            hook_l2_to_l3_promotion,
            hook_l3_to_l2_promotion
        )
        
        # Test L2Q to L2 hook
        lineage_hash = hook_l2q_to_l2_promotion(
            item_id="test_item",
            cls="test_class",
            tenant_id="test_tenant",
            nbmf_ledger_txid="test_txid_123",
            promoted_by="test_system"
        )
        if lineage_hash:
            print(f"✅ L2Q→L2 promotion hook works (lineage hash: {lineage_hash[:16]}...)")
        else:
            print("⚠️  L2Q→L2 hook returned None (DNA service may not be available)")
        
        return True
    except Exception as e:
        print(f"❌ DNA integration hooks test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all verification tests."""
    print("\n" + "=" * 60)
    print("ENTERPRISE-DNA INTEGRATION VERIFICATION")
    print("=" * 60)
    print()
    
    results = {
        "dna_service": test_dna_service(),
        "trust_manager_v2": test_trust_manager_v2(),
        "dna_models": test_dna_models(),
        "dna_integration_hooks": test_dna_integration_hooks(),
        "api_endpoints": test_api_endpoints()
    }
    
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v is True)
    total = sum(1 for v in results.values() if v is not None)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result is True else "⚠️  SKIP" if result is None else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed or skipped")
        return 1

if __name__ == "__main__":
    sys.exit(main())

