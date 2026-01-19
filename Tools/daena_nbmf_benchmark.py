#!/usr/bin/env python3
"""
NBMF Hard Evidence Benchmark Tool

Measures and validates all NBMF claims with hard numbers:
- Compression ratio vs OCR baseline
- Token counts (before/after)
- Latency measurements
- Accuracy/reversibility (hash comparison)
- Error bars and statistical confidence
"""

import json
import time
import hashlib
import statistics
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime
import argparse

# Import NBMF components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_service.nbmf_encoder import encode, Fidelity
from memory_service.nbmf_decoder import decode
from memory_service.nbmf_encoder_production import ProductionNBMFEncoder


class NBMFBenchmark:
    """Comprehensive benchmark suite for NBMF validation."""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "compression": {},
            "accuracy": {},
            "latency": {},
            "token_counts": {},
            "round_trip_tests": {}
        }
    
    def generate_test_corpus(self, sizes: List[int] = [100, 1000, 10000, 30000]) -> List[Dict[str, Any]]:
        """Generate test corpus of various sizes (simulating OCR output)."""
        corpus = []
        
        # Sample text (simulating OCR output)
        base_text = """
        This is a sample document that simulates OCR output from scanned documents.
        It contains multiple paragraphs, technical terms, and structured information.
        The purpose is to test NBMF compression against OCR baseline storage.
        """
        
        for size in sizes:
            # Repeat text to reach target size
            repetitions = max(1, size // len(base_text))
            text = base_text * repetitions
            text = text[:size]  # Trim to exact size
            
            corpus.append({
                "id": f"doc_{size}",
                "size_bytes": len(text.encode('utf-8')),
                "content": text,
                "type": "ocr_simulation"
            })
        
        return corpus
    
    def measure_compression_vs_ocr(self, corpus: List[Dict[str, Any]], iterations: int = 10) -> Dict[str, Any]:
        """Measure compression ratio vs OCR baseline with error bars."""
        print("📊 Measuring compression vs OCR baseline...")
        
        results = {
            "lossless": {"ratios": [], "sizes": {"ocr": [], "nbmf": []}},
            "semantic": {"ratios": [], "sizes": {"ocr": [], "nbmf": []}}
        }
        
        for doc in corpus:
            ocr_size = doc["size_bytes"]
            content = doc["content"]
            
            # Test lossless mode
            for _ in range(iterations):
                encoded = encode(content, fidelity="lossless")
                nbmf_size = len(json.dumps(encoded).encode('utf-8'))
                ratio = ocr_size / nbmf_size if nbmf_size > 0 else 1.0
                results["lossless"]["ratios"].append(ratio)
                results["lossless"]["sizes"]["ocr"].append(ocr_size)
                results["lossless"]["sizes"]["nbmf"].append(nbmf_size)
            
            # Test semantic mode
            for _ in range(iterations):
                encoded = encode(content, fidelity="semantic")
                nbmf_size = len(json.dumps(encoded).encode('utf-8'))
                ratio = ocr_size / nbmf_size if nbmf_size > 0 else 1.0
                results["semantic"]["ratios"].append(ratio)
                results["semantic"]["sizes"]["ocr"].append(ocr_size)
                results["semantic"]["sizes"]["nbmf"].append(nbmf_size)
        
        # Calculate statistics
        def calc_stats(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"mean": 0, "median": 0, "min": 0, "max": 0, "std": 0, "p95": 0, "p99": 0}
            sorted_vals = sorted(values)
            return {
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0,
                "p95": sorted_vals[int(len(sorted_vals) * 0.95)] if sorted_vals else 0,
                "p99": sorted_vals[int(len(sorted_vals) * 0.99)] if sorted_vals else 0
            }
        
        return {
            "lossless": {
                "ratios": calc_stats(results["lossless"]["ratios"]),
                "size_savings": {
                    "ocr_mean": statistics.mean(results["lossless"]["sizes"]["ocr"]),
                    "nbmf_mean": statistics.mean(results["lossless"]["sizes"]["nbmf"]),
                    "savings_percent": (1 - statistics.mean(results["lossless"]["sizes"]["nbmf"]) / 
                                       statistics.mean(results["lossless"]["sizes"]["ocr"])) * 100
                }
            },
            "semantic": {
                "ratios": calc_stats(results["semantic"]["ratios"]),
                "size_savings": {
                    "ocr_mean": statistics.mean(results["semantic"]["sizes"]["ocr"]),
                    "nbmf_mean": statistics.mean(results["semantic"]["sizes"]["nbmf"]),
                    "savings_percent": (1 - statistics.mean(results["semantic"]["sizes"]["nbmf"]) / 
                                       statistics.mean(results["semantic"]["sizes"]["ocr"])) * 100
                }
            }
        }
    
    def measure_accuracy_reversibility(self, corpus: List[Dict[str, Any]], iterations: int = 10) -> Dict[str, Any]:
        """Test round-trip accuracy: source → NBMF → decode → compare hash."""
        print("🔍 Testing accuracy and reversibility...")
        
        results = {
            "lossless": {"exact_matches": 0, "hash_matches": 0, "total": 0},
            "semantic": {"similarity_scores": [], "total": 0}
        }
        
        for doc in corpus:
            original = doc["content"]
            original_hash = hashlib.sha256(original.encode('utf-8')).hexdigest()
            
            for _ in range(iterations):
                # Lossless mode - should be 100% exact
                encoded = encode(original, fidelity="lossless")
                decoded = decode(encoded)
                decoded_str = decoded if isinstance(decoded, str) else json.dumps(decoded)
                decoded_hash = hashlib.sha256(decoded_str.encode('utf-8')).hexdigest()
                
                results["lossless"]["total"] += 1
                if original == decoded_str:
                    results["lossless"]["exact_matches"] += 1
                if original_hash == decoded_hash:
                    results["lossless"]["hash_matches"] += 1
                
                # Semantic mode - measure similarity
                encoded = encode(original, fidelity="semantic")
                decoded = decode(encoded)
                decoded_str = decoded if isinstance(decoded, str) else json.dumps(decoded)
                
                # Calculate similarity (character overlap)
                similarity = self._calculate_similarity(original, decoded_str)
                results["semantic"]["similarity_scores"].append(similarity)
                results["semantic"]["total"] += 1
        
        return {
            "lossless": {
                "exact_match_rate": results["lossless"]["exact_matches"] / results["lossless"]["total"] if results["lossless"]["total"] > 0 else 0,
                "hash_match_rate": results["lossless"]["hash_matches"] / results["lossless"]["total"] if results["lossless"]["total"] > 0 else 0,
                "total_tests": results["lossless"]["total"]
            },
            "semantic": {
                "mean_similarity": statistics.mean(results["semantic"]["similarity_scores"]) if results["semantic"]["similarity_scores"] else 0,
                "min_similarity": min(results["semantic"]["similarity_scores"]) if results["semantic"]["similarity_scores"] else 0,
                "p95_similarity": sorted(results["semantic"]["similarity_scores"])[int(len(results["semantic"]["similarity_scores"]) * 0.95)] if results["semantic"]["similarity_scores"] else 0,
                "total_tests": results["semantic"]["total"]
            }
        }
    
    def _calculate_similarity(self, a: str, b: str) -> float:
        """Calculate character-level similarity between two strings."""
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        
        # Character overlap
        set_a = set(a.lower())
        set_b = set(b.lower())
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
    
    def measure_latency(self, corpus: List[Dict[str, Any]], iterations: int = 50) -> Dict[str, Any]:
        """Measure encode/decode latency with percentiles."""
        print("⏱️  Measuring latency...")
        
        encode_times = {"lossless": [], "semantic": []}
        decode_times = {"lossless": [], "semantic": []}
        
        for doc in corpus:
            content = doc["content"]
            
            for _ in range(iterations):
                # Lossless encode
                start = time.perf_counter()
                encoded = encode(content, fidelity="lossless")
                encode_times["lossless"].append((time.perf_counter() - start) * 1000)  # ms
                
                # Lossless decode
                start = time.perf_counter()
                decode(encoded)
                decode_times["lossless"].append((time.perf_counter() - start) * 1000)  # ms
                
                # Semantic encode
                start = time.perf_counter()
                encoded = encode(content, fidelity="semantic")
                encode_times["semantic"].append((time.perf_counter() - start) * 1000)  # ms
                
                # Semantic decode
                start = time.perf_counter()
                decode(encoded)
                decode_times["semantic"].append((time.perf_counter() - start) * 1000)  # ms
        
        def calc_percentiles(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"mean": 0, "p50": 0, "p95": 0, "p99": 0, "min": 0, "max": 0}
            sorted_vals = sorted(values)
            return {
                "mean": statistics.mean(values),
                "p50": sorted_vals[int(len(sorted_vals) * 0.50)],
                "p95": sorted_vals[int(len(sorted_vals) * 0.95)],
                "p99": sorted_vals[int(len(sorted_vals) * 0.99)],
                "min": min(values),
                "max": max(values)
            }
        
        return {
            "encode": {
                "lossless": calc_percentiles(encode_times["lossless"]),
                "semantic": calc_percentiles(encode_times["semantic"])
            },
            "decode": {
                "lossless": calc_percentiles(decode_times["lossless"]),
                "semantic": calc_percentiles(decode_times["semantic"])
            }
        }
    
    def estimate_token_counts(self, corpus: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Estimate token counts before/after NBMF encoding."""
        print("🔢 Estimating token counts...")
        
        # Rough estimation: 1 token ≈ 4 characters for English
        results = {
            "ocr_tokens": [],
            "nbmf_tokens": {"lossless": [], "semantic": []}
        }
        
        for doc in corpus:
            content = doc["content"]
            ocr_tokens = len(content) / 4  # Rough estimate
            results["ocr_tokens"].append(ocr_tokens)
            
            # NBMF encoded size (approximate)
            encoded_lossless = encode(content, fidelity="lossless")
            encoded_semantic = encode(content, fidelity="semantic")
            
            nbmf_lossless_size = len(json.dumps(encoded_lossless))
            nbmf_semantic_size = len(json.dumps(encoded_semantic))
            
            results["nbmf_tokens"]["lossless"].append(nbmf_lossless_size / 4)
            results["nbmf_tokens"]["semantic"].append(nbmf_semantic_size / 4)
        
        return {
            "ocr": {
                "mean": statistics.mean(results["ocr_tokens"]),
                "total": sum(results["ocr_tokens"])
            },
            "nbmf_lossless": {
                "mean": statistics.mean(results["nbmf_tokens"]["lossless"]),
                "total": sum(results["nbmf_tokens"]["lossless"]),
                "reduction_percent": (1 - statistics.mean(results["nbmf_tokens"]["lossless"]) / 
                                     statistics.mean(results["ocr_tokens"])) * 100
            },
            "nbmf_semantic": {
                "mean": statistics.mean(results["nbmf_tokens"]["semantic"]),
                "total": sum(results["nbmf_tokens"]["semantic"]),
                "reduction_percent": (1 - statistics.mean(results["nbmf_tokens"]["semantic"]) / 
                                     statistics.mean(results["ocr_tokens"])) * 100
            }
        }
    
    def run_full_benchmark(self, iterations: int = 10) -> Dict[str, Any]:
        """Run complete benchmark suite."""
        print("🚀 Starting NBMF Hard Evidence Benchmark...")
        print(f"   Iterations per test: {iterations}")
        print()
        
        # Generate test corpus
        corpus = self.generate_test_corpus()
        print(f"✅ Generated test corpus: {len(corpus)} documents")
        print()
        
        # Run all tests
        self.results["compression"] = self.measure_compression_vs_ocr(corpus, iterations)
        print()
        
        self.results["accuracy"] = self.measure_accuracy_reversibility(corpus, iterations)
        print()
        
        self.results["latency"] = self.measure_latency(corpus, iterations=20)  # Fewer for latency
        print()
        
        self.results["token_counts"] = self.estimate_token_counts(corpus)
        print()
        
        # Generate summary
        self.results["summary"] = self._generate_summary()
        
        return self.results
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate executive summary of benchmark results."""
        comp = self.results["compression"]
        acc = self.results["accuracy"]
        lat = self.results["latency"]
        tokens = self.results["token_counts"]
        
        return {
            "compression_ratio_lossless": comp["lossless"]["ratios"]["mean"],
            "compression_ratio_semantic": comp["semantic"]["ratios"]["mean"],
            "storage_savings_lossless": comp["lossless"]["size_savings"]["savings_percent"],
            "storage_savings_semantic": comp["semantic"]["size_savings"]["savings_percent"],
            "accuracy_lossless": acc["lossless"]["exact_match_rate"] * 100,
            "accuracy_semantic": acc["semantic"]["mean_similarity"] * 100,
            "encode_latency_p95_lossless_ms": lat["encode"]["lossless"]["p95"],
            "encode_latency_p95_semantic_ms": lat["encode"]["semantic"]["p95"],
            "decode_latency_p95_lossless_ms": lat["decode"]["lossless"]["p95"],
            "decode_latency_p95_semantic_ms": lat["decode"]["semantic"]["p95"],
            "token_reduction_lossless_percent": tokens["nbmf_lossless"]["reduction_percent"],
            "token_reduction_semantic_percent": tokens["nbmf_semantic"]["reduction_percent"]
        }
    
    def save_results(self, output_path: str):
        """Save benchmark results to JSON file."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with output.open('w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"✅ Results saved to: {output_path}")
    
    def print_summary(self):
        """Print human-readable summary."""
        s = self.results["summary"]
        
        print("=" * 80)
        print("NBMF BENCHMARK SUMMARY")
        print("=" * 80)
        print()
        print("COMPRESSION vs OCR:")
        print(f"  Lossless:  {s['compression_ratio_lossless']:.2f}x ({s['storage_savings_lossless']:.1f}% savings)")
        print(f"  Semantic:  {s['compression_ratio_semantic']:.2f}x ({s['storage_savings_semantic']:.1f}% savings)")
        print()
        print("ACCURACY:")
        print(f"  Lossless:  {s['accuracy_lossless']:.2f}% exact match")
        print(f"  Semantic:  {s['accuracy_semantic']:.2f}% similarity")
        print()
        print("LATENCY (p95):")
        print(f"  Encode Lossless:  {s['encode_latency_p95_lossless_ms']:.2f}ms")
        print(f"  Encode Semantic: {s['encode_latency_p95_semantic_ms']:.2f}ms")
        print(f"  Decode Lossless:  {s['decode_latency_p95_lossless_ms']:.2f}ms")
        print(f"  Decode Semantic: {s['decode_latency_p95_semantic_ms']:.2f}ms")
        print()
        print("TOKEN REDUCTION:")
        print(f"  Lossless:  {s['token_reduction_lossless_percent']:.1f}%")
        print(f"  Semantic:  {s['token_reduction_semantic_percent']:.1f}%")
        print()
        print("=" * 80)


def compare_with_golden(results: Dict[str, Any], golden_path: str = "Governance/artifacts/benchmarks_golden.json") -> Dict[str, Any]:
    """Compare benchmark results against golden values and return validation status."""
    import json
    from pathlib import Path
    
    golden_file = Path(golden_path)
    if not golden_file.exists():
        print(f"⚠️ Golden values file not found: {golden_path}")
        return {"valid": False, "error": "Golden file not found"}
    
    with open(golden_file, 'r') as f:
        golden = json.load(f)
    
    tolerance = golden.get("tolerance_percent", 10) / 100
    golden_vals = golden["golden_values"]
    summary = results["summary"]
    
    validation = {
        "all_passed": True,
        "regressions": [],
        "improvements": [],
        "details": {}
    }
    
    # Check compression_lossless
    golden_ratio = golden_vals["compression_lossless"]["ratio"]
    actual_ratio = summary["compression_ratio_lossless"]
    min_acceptable = golden_vals["compression_lossless"].get("min_acceptable", golden_ratio * (1 - tolerance))
    
    if actual_ratio < min_acceptable:
        validation["all_passed"] = False
        regression = {
            "metric": "compression_lossless",
            "golden": golden_ratio,
            "actual": actual_ratio,
            "regression_percent": ((golden_ratio - actual_ratio) / golden_ratio) * 100,
            "threshold": min_acceptable
        }
        validation["regressions"].append(regression)
        validation["details"]["compression_lossless"] = "FAIL"
    else:
        validation["details"]["compression_lossless"] = "PASS"
        if actual_ratio > golden_ratio:
            validation["improvements"].append({
                "metric": "compression_lossless",
                "improvement_percent": ((actual_ratio - golden_ratio) / golden_ratio) * 100
            })
    
    # Check compression_semantic
    golden_sem = golden_vals["compression_semantic"]["ratio"]
    actual_sem = summary["compression_ratio_semantic"]
    min_acceptable_sem = golden_vals["compression_semantic"].get("min_acceptable", golden_sem * (1 - tolerance))
    
    if actual_sem < min_acceptable_sem:
        validation["all_passed"] = False
        validation["regressions"].append({
            "metric": "compression_semantic",
            "golden": golden_sem,
            "actual": actual_sem,
            "regression_percent": ((golden_sem - actual_sem) / golden_sem) * 100
        })
        validation["details"]["compression_semantic"] = "FAIL"
    else:
        validation["details"]["compression_semantic"] = "PASS"
    
    # Check encode_p95_ms (should be <= max_acceptable)
    golden_encode = golden_vals["encode_p95_ms"]["value"]
    actual_encode = summary["encode_latency_p95_lossless_ms"]
    max_acceptable = golden_vals["encode_p95_ms"].get("max_acceptable", golden_encode * (1 + tolerance))
    
    if actual_encode > max_acceptable:
        validation["all_passed"] = False
        validation["regressions"].append({
            "metric": "encode_p95_ms",
            "golden": golden_encode,
            "actual": actual_encode,
            "regression_percent": ((actual_encode - golden_encode) / golden_encode) * 100
        })
        validation["details"]["encode_p95_ms"] = "FAIL"
    else:
        validation["details"]["encode_p95_ms"] = "PASS"
    
    # Check decode_p95_ms
    golden_decode = golden_vals["decode_p95_ms"]["value"]
    actual_decode = summary["decode_latency_p95_lossless_ms"]
    max_acceptable_decode = golden_vals["decode_p95_ms"].get("max_acceptable", golden_decode * (1 + tolerance))
    
    if actual_decode > max_acceptable_decode:
        validation["all_passed"] = False
        validation["regressions"].append({
            "metric": "decode_p95_ms",
            "golden": golden_decode,
            "actual": actual_decode,
            "regression_percent": ((actual_decode - golden_decode) / golden_decode) * 100
        })
        validation["details"]["decode_p95_ms"] = "FAIL"
    else:
        validation["details"]["decode_p95_ms"] = "PASS"
    
    # Check exact_match_rate
    golden_accuracy = golden_vals["exact_match_rate"]["value"]
    actual_accuracy = summary["accuracy_lossless"] / 100.0  # Convert from percent
    min_acceptable_acc = golden_vals["exact_match_rate"].get("min_acceptable", golden_accuracy * (1 - tolerance))
    
    if actual_accuracy < min_acceptable_acc:
        validation["all_passed"] = False
        validation["regressions"].append({
            "metric": "exact_match_rate",
            "golden": golden_accuracy,
            "actual": actual_accuracy,
            "regression_percent": ((golden_accuracy - actual_accuracy) / golden_accuracy) * 100
        })
        validation["details"]["exact_match_rate"] = "FAIL"
    else:
        validation["details"]["exact_match_rate"] = "PASS"
    
    return validation


def save_csv(results: Dict[str, Any], output_path: str):
    """Save benchmark results as CSV for easy import."""
    import csv
    from pathlib import Path
    
    csv_path = Path(output_path.replace('.json', '.csv'))
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    
    summary = results["summary"]
    
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Metric", "Value", "Unit"])
        writer.writerow(["compression_ratio_lossless", summary["compression_ratio_lossless"], "multiplier"])
        writer.writerow(["compression_ratio_semantic", summary["compression_ratio_semantic"], "multiplier"])
        writer.writerow(["storage_savings_lossless", summary["storage_savings_lossless"], "percent"])
        writer.writerow(["storage_savings_semantic", summary["storage_savings_semantic"], "percent"])
        writer.writerow(["accuracy_lossless", summary["accuracy_lossless"], "percent"])
        writer.writerow(["accuracy_semantic", summary["accuracy_semantic"], "percent"])
        writer.writerow(["encode_latency_p95_lossless_ms", summary["encode_latency_p95_lossless_ms"], "milliseconds"])
        writer.writerow(["encode_latency_p95_semantic_ms", summary["encode_latency_p95_semantic_ms"], "milliseconds"])
        writer.writerow(["decode_latency_p95_lossless_ms", summary["decode_latency_p95_lossless_ms"], "milliseconds"])
        writer.writerow(["decode_latency_p95_semantic_ms", summary["decode_latency_p95_semantic_ms"], "milliseconds"])
        writer.writerow(["token_reduction_lossless_percent", summary["token_reduction_lossless_percent"], "percent"])
        writer.writerow(["token_reduction_semantic_percent", summary["token_reduction_semantic_percent"], "percent"])
    
    print(f"✅ CSV results saved to: {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="NBMF Hard Evidence Benchmark")
    parser.add_argument("--iterations", type=int, default=10, help="Iterations per test")
    parser.add_argument("--output", type=str, default="bench/nbmf_benchmark_results.json", help="Output file")
    parser.add_argument("--golden", type=str, default="Governance/artifacts/benchmarks_golden.json", help="Golden values file")
    parser.add_argument("--validate", action="store_true", help="Validate against golden values and exit with error if regressed")
    parser.add_argument("--csv", action="store_true", help="Also generate CSV output")
    args = parser.parse_args()
    
    benchmark = NBMFBenchmark()
    results = benchmark.run_full_benchmark(iterations=args.iterations)
    
    benchmark.print_summary()
    benchmark.save_results(args.output)
    
    # Generate CSV if requested
    if args.csv:
        save_csv(results, args.output)
    
    # Validate against golden values if requested
    if args.validate:
        validation = compare_with_golden(results, args.golden)
        
        print("\n" + "=" * 80)
        print("GOLDEN VALUE VALIDATION")
        print("=" * 80)
        
        if validation.get("all_passed"):
            print("✅ ALL METRICS PASSED - No regressions detected")
            for metric, status in validation["details"].items():
                print(f"  {metric}: {status}")
        else:
            print("❌ REGRESSIONS DETECTED:")
            for reg in validation["regressions"]:
                print(f"  {reg['metric']}: {reg['golden']} → {reg['actual']} ({reg['regression_percent']:.1f}% regression)")
            
            if validation.get("improvements"):
                print("\n✅ IMPROVEMENTS:")
                for imp in validation["improvements"]:
                    print(f"  {imp['metric']}: {imp['improvement_percent']:.1f}% improvement")
            
            print("\n" + "=" * 80)
            return 1  # Exit with error for CI
    
    return 0


if __name__ == "__main__":
    exit(main())

