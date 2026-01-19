"""
Standalone script to run NBMF comparison tests and generate report.
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import test functions directly from file
import importlib.util
spec = importlib.util.spec_from_file_location("test_nbmf_comparison", project_root / "tests" / "test_nbmf_comparison.py")
test_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(test_module)

# Get test functions
test_storage_size_comparison = test_module.test_storage_size_comparison
test_large_document_compression = test_module.test_large_document_compression
test_ocr_fallback_pattern = test_module.test_ocr_fallback_pattern
test_semantic_vs_lossless = test_module.test_semantic_vs_lossless
test_cas_deduplication = test_module.test_cas_deduplication
test_retrieval_speed = test_module.test_retrieval_speed
test_innovation_summary = test_module.test_innovation_summary

if __name__ == "__main__":
    print("="*70)
    print("NBMF COMPARISON TEST SUITE")
    print("="*70)
    print()
    
    try:
        print("Running test_storage_size_comparison...")
        test_storage_size_comparison()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")
    
    try:
        print("Running test_large_document_compression...")
        test_large_document_compression()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")
    
    try:
        print("Running test_ocr_fallback_pattern...")
        test_ocr_fallback_pattern()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")
    
    try:
        print("Running test_semantic_vs_lossless...")
        test_semantic_vs_lossless()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")
    
    try:
        print("Running test_cas_deduplication...")
        test_cas_deduplication()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")
    
    try:
        print("Running test_retrieval_speed...")
        test_retrieval_speed()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")
    
    try:
        print("Running test_innovation_summary...")
        test_innovation_summary()
        print("PASSED\n")
    except Exception as e:
        print(f"FAILED: {e}\n")
    
    print("="*70)
    print("TEST SUITE COMPLETE")
    print("="*70)

