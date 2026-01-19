"""
Encoder Validation Script

Validates trained encoder against benchmark requirements.

Usage:
    python training/validate_encoder.py \
      --model models/nbmf_encoder_general.pt \
      --test-data data/training/general/test/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from memory_service.nbmf_encoder_production import ProductionNBMFEncoder


def validate_compression(
    encoder: ProductionNBMFEncoder,
    test_samples: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Validate compression ratio (target: 2-5×)."""
    ratios = []
    
    for sample in test_samples:
        data = sample["data"]
        
        # Encode
        encoded = encoder.encode(data, fidelity="semantic")
        
        # Calculate compression ratio
        original_size = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
        encoded_size = len(encoded.get("code", "")) // 2  # hex string
        
        if encoded_size > 0:
            ratio = original_size / encoded_size
            ratios.append(ratio)
    
    if not ratios:
        return {"error": "No valid compression ratios calculated"}
    
    return {
        "mean": sum(ratios) / len(ratios),
        "min": min(ratios),
        "max": max(ratios),
        "p95": sorted(ratios)[int(len(ratios) * 0.95)] if ratios else 0,
        "target_range": (2.0, 5.0),
        "meets_target": 2.0 <= (sum(ratios) / len(ratios)) <= 5.0
    }


def validate_accuracy(
    encoder: ProductionNBMFEncoder,
    test_samples: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Validate accuracy (target: 99.5%+)."""
    similarities = []
    
    for sample in test_samples:
        data = sample["data"]
        
        # Encode and decode
        encoded = encoder.encode(data, fidelity="semantic")
        decoded = encoder.decode(encoded)
        
        # Calculate similarity
        original_str = str(data)
        decoded_str = str(decoded)
        
        # Simple character overlap similarity
        original_chars = set(original_str.lower())
        decoded_chars = set(decoded_str.lower())
        
        if original_chars:
            similarity = len(original_chars & decoded_chars) / len(original_chars)
            similarities.append(similarity)
    
    if not similarities:
        return {"error": "No valid similarities calculated"}
    
    mean_similarity = sum(similarities) / len(similarities)
    
    return {
        "mean": mean_similarity * 100.0,
        "min": min(similarities) * 100.0,
        "p95": sorted(similarities)[int(len(similarities) * 0.95)] * 100.0 if similarities else 0,
        "target": 99.5,
        "meets_target": mean_similarity * 100.0 >= 99.5
    }


def main():
    parser = argparse.ArgumentParser(description="Validate trained encoder")
    parser.add_argument("--model", type=str, required=True, help="Path to trained model")
    parser.add_argument("--test-data", type=str, required=True, help="Test data directory")
    parser.add_argument("--domain", type=str, default="general", help="Domain name")
    
    args = parser.parse_args()
    
    # Load encoder
    encoder = ProductionNBMFEncoder(domain=args.domain, model_path=args.model)
    
    # Load test data
    test_dir = Path(args.test_data)
    test_file = test_dir / "test_samples.json"
    
    if not test_file.exists():
        print(f"Error: Test data not found: {test_file}")
        return 1
    
    with open(test_file) as f:
        test_samples = json.load(f)
    
    print(f"Validating encoder with {len(test_samples)} test samples...")
    
    # Validate compression
    print("\nValidating compression ratio...")
    compression_results = validate_compression(encoder, test_samples)
    if "error" not in compression_results:
        print(f"  Mean: {compression_results['mean']:.2f}×")
        print(f"  Range: {compression_results['min']:.2f}× - {compression_results['max']:.2f}×")
        print(f"  P95: {compression_results['p95']:.2f}×")
        print(f"  Target: {compression_results['target_range'][0]}-{compression_results['target_range'][1]}×")
        print(f"  Status: {'✅ PASS' if compression_results['meets_target'] else '❌ FAIL'}")
    
    # Validate accuracy
    print("\nValidating accuracy...")
    accuracy_results = validate_accuracy(encoder, test_samples)
    if "error" not in accuracy_results:
        print(f"  Mean: {accuracy_results['mean']:.2f}%")
        print(f"  Min: {accuracy_results['min']:.2f}%")
        print(f"  P95: {accuracy_results['p95']:.2f}%")
        print(f"  Target: {accuracy_results['target']}%")
        print(f"  Status: {'✅ PASS' if accuracy_results['meets_target'] else '❌ FAIL'}")
    
    # Summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    all_pass = (
        compression_results.get("meets_target", False) and
        accuracy_results.get("meets_target", False)
    )
    
    print(f"Overall: {'✅ PASS' if all_pass else '❌ FAIL'}")
    
    return 0 if all_pass else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())

