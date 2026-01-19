"""
NBMF Benchmark Tool

Validates compression ratio (2-5×) and accuracy (99.5%+) claims.
Tests latency targets (L1 <25ms, L2 <120ms).

Usage:
    python bench/benchmark_nbmf.py [--samples N] [--output results.json]
"""

from __future__ import annotations

import argparse
import json
import time
import statistics
from pathlib import Path
from typing import Any, Dict, List, Tuple
from collections import defaultdict

# Import NBMF components
from memory_service.router import MemoryRouter
from memory_service.nbmf_encoder import encode, Fidelity
from memory_service.nbmf_decoder import decode


class BenchmarkRunner:
    """Runs comprehensive benchmarks on NBMF system."""
    
    def __init__(self, router: MemoryRouter | None = None):
        self.router = router or MemoryRouter()
        self.results: Dict[str, Any] = {
            "compression": {},
            "accuracy": {},
            "latency": {},
            "summary": {}
        }
    
    def generate_test_data(self, num_samples: int = 100) -> List[Dict[str, Any]]:
        """Generate diverse test data samples."""
        samples = []
        
        # Text samples (conversations, documents)
        for i in range(num_samples // 3):
            samples.append({
                "type": "text",
                "id": f"text_{i}",
                "data": f"This is a sample conversation text {i}. " * 50 + 
                       f"It contains multiple sentences and paragraphs. " * 20 +
                       f"Some technical terms: API, NBMF, compression, accuracy."
            })
        
        # Structured data (JSON objects)
        for i in range(num_samples // 3):
            samples.append({
                "type": "structured",
                "id": f"struct_{i}",
                "data": {
                    "user_id": f"user_{i}",
                    "timestamp": time.time() + i,
                    "metadata": {
                        "department": ["engineering", "product", "sales"][i % 3],
                        "priority": ["low", "medium", "high"][i % 3],
                        "tags": [f"tag_{j}" for j in range(5)],
                        "nested": {
                            "level1": {"level2": {"level3": f"value_{i}"}}
                        }
                    },
                    "content": f"Structured data sample {i} with nested objects."
                }
            })
        
        # Mixed/multimodal data
        for i in range(num_samples // 3):
            samples.append({
                "type": "mixed",
                "id": f"mixed_{i}",
                "data": {
                    "text": f"Mixed content sample {i}",
                    "metadata": {"source": "api", "version": "1.0"},
                    "binary_ref": f"file://path/to/binary_{i}.bin",
                    "structured": {"key": f"value_{i}", "count": i}
                }
            })
        
        return samples
    
    def measure_compression(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Measure compression ratios for lossless and semantic modes."""
        print("Measuring compression ratios...")
        
        results = {
            "lossless": {"ratios": [], "sizes": {"raw": [], "compressed": []}},
            "semantic": {"ratios": [], "sizes": {"raw": [], "compressed": []}}
        }
        
        for sample in samples:
            data = sample["data"]
            
            # Raw size
            raw_bytes = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
            
            # Lossless encoding
            encoded_lossless = encode(data, fidelity="lossless")
            lossless_size = len(encoded_lossless.get("code", "")) // 2  # hex string
            lossless_ratio = raw_bytes / lossless_size if lossless_size > 0 else 1.0
            
            results["lossless"]["ratios"].append(lossless_ratio)
            results["lossless"]["sizes"]["raw"].append(raw_bytes)
            results["lossless"]["sizes"]["compressed"].append(lossless_size)
            
            # Semantic encoding
            encoded_semantic = encode(data, fidelity="semantic")
            semantic_size = len(encoded_semantic.get("code", "")) // 2  # hex string
            semantic_ratio = raw_bytes / semantic_size if semantic_size > 0 else 1.0
            
            results["semantic"]["ratios"].append(semantic_ratio)
            results["semantic"]["sizes"]["raw"].append(raw_bytes)
            results["semantic"]["sizes"]["compressed"].append(semantic_size)
        
        # Calculate statistics
        for mode in ["lossless", "semantic"]:
            ratios = results[mode]["ratios"]
            if ratios:
                if ratios:
                    results[mode]["mean"] = statistics.mean(ratios)
                    results[mode]["median"] = statistics.median(ratios)
                    results[mode]["min"] = min(ratios)
                    results[mode]["max"] = max(ratios)
                    results[mode]["p95"] = sorted(ratios)[int(len(ratios) * 0.95)]
        
        return results
    
    def measure_accuracy(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Measure reconstruction accuracy."""
        print("Measuring accuracy...")
        
        results = {
            "lossless": {"exact_matches": 0, "total": 0, "errors": []},
            "semantic": {"similarities": [], "errors": []}
        }
        
        for sample in samples:
            data = sample["data"]
            
            # Lossless mode - should be 100% exact
            try:
                encoded = encode(data, fidelity="lossless")
                decoded = decode(encoded)
                
                # Compare exact match
                original_json = json.dumps(data, sort_keys=True, ensure_ascii=False)
                decoded_json = json.dumps(decoded, sort_keys=True, ensure_ascii=False)
                
                results["lossless"]["total"] += 1
                if original_json == decoded_json:
                    results["lossless"]["exact_matches"] += 1
                else:
                    results["lossless"]["errors"].append({
                        "id": sample["id"],
                        "type": "mismatch",
                        "original_len": len(original_json),
                        "decoded_len": len(decoded_json)
                    })
            except Exception as e:
                results["lossless"]["errors"].append({
                    "id": sample["id"],
                    "type": "exception",
                    "error": str(e)
                })
            
            # Semantic mode - measure similarity
            try:
                encoded = encode(data, fidelity="semantic")
                decoded = decode(encoded)
                
                # Simple similarity: compare string representations
                original_str = str(data)
                decoded_str = str(decoded)
                
                # Calculate similarity (simple character overlap)
                original_chars = set(original_str.lower())
                decoded_chars = set(decoded_str.lower())
                if original_chars:
                    similarity = len(original_chars & decoded_chars) / len(original_chars)
                    results["semantic"]["similarities"].append(similarity)
                else:
                    results["semantic"]["similarities"].append(1.0)
            except Exception as e:
                results["semantic"]["errors"].append({
                    "id": sample["id"],
                    "type": "exception",
                    "error": str(e)
                })
        
        # Calculate accuracy statistics
        if results["lossless"]["total"] > 0:
            results["lossless"]["accuracy"] = (
                results["lossless"]["exact_matches"] / results["lossless"]["total"]
            ) * 100.0
        
        if results["semantic"]["similarities"]:
            results["semantic"]["mean_accuracy"] = statistics.mean(
                results["semantic"]["similarities"]
            ) * 100.0
            results["semantic"]["min_accuracy"] = min(
                results["semantic"]["similarities"]
            ) * 100.0
            results["semantic"]["p95_accuracy"] = sorted(
                results["semantic"]["similarities"]
            )[int(len(results["semantic"]["similarities"]) * 0.95)] * 100.0
        
        return results
    
    def measure_latency(self, samples: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Measure write and read latency for L1/L2/L3."""
        print("Measuring latency...")
        
        results = {
            "write": {"l1": [], "l2": [], "l3": []},
            "read": {"l1": [], "l2": [], "l3": []}
        }
        
        # Write latency
        for sample in samples[:50]:  # Test with subset for speed
            data = sample["data"]
            item_id = sample["id"]
            cls = sample.get("type", "test")
            
            # Measure write
            start = time.perf_counter()
            try:
                self.router.write_nbmf_only(item_id, cls, data)
                write_time = (time.perf_counter() - start) * 1000  # ms
                
                # Determine which tier (simplified - actual routing is more complex)
                if self.router.l2.exists(item_id, cls):
                    results["write"]["l2"].append(write_time)
                elif hasattr(self.router, "l3") and self.router.l3.exists(item_id, cls):
                    results["write"]["l3"].append(write_time)
            except Exception as e:
                print(f"Write error for {item_id}: {e}")
            
            # Measure read
            start = time.perf_counter()
            try:
                read_data = self.router.read_nbmf_only(item_id, cls)
                read_time = (time.perf_counter() - start) * 1000  # ms
                
                if read_data:
                    # Determine tier (simplified)
                    if self.router.l2.exists(item_id, cls):
                        results["read"]["l2"].append(read_time)
                    elif hasattr(self.router, "l3") and self.router.l3.exists(item_id, cls):
                        results["read"]["l3"].append(read_time)
            except Exception as e:
                print(f"Read error for {item_id}: {e}")
        
        # Calculate statistics
        for operation in ["write", "read"]:
            for tier in ["l1", "l2", "l3"]:
                times = results[operation][tier]
                if times:
                    results[operation][tier] = {
                        "mean_ms": statistics.mean(times),
                        "p95_ms": sorted(times)[int(len(times) * 0.95)] if times else 0,
                        "p99_ms": sorted(times)[int(len(times) * 0.99)] if len(times) > 1 else times[0] if times else 0,
                        "min_ms": min(times),
                        "max_ms": max(times),
                        "samples": len(times)
                    }
                else:
                    results[operation][tier] = {"samples": 0}
        
        return results
    
    def run(self, num_samples: int = 100) -> Dict[str, Any]:
        """Run all benchmarks."""
        print(f"Running NBMF benchmarks with {num_samples} samples...")
        
        samples = self.generate_test_data(num_samples)
        
        # Run benchmarks
        self.results["compression"] = self.measure_compression(samples)
        self.results["accuracy"] = self.measure_accuracy(samples)
        self.results["latency"] = self.measure_latency(samples)
        
        # Generate summary
        self.results["summary"] = self._generate_summary()
        
        return self.results
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate summary of results."""
        summary = {
            "compression_claim": "2-5× compression",
            "accuracy_claim": "99.5%+ accuracy",
            "latency_claims": {
                "l1": "<25ms p95",
                "l2": "<120ms p95"
            }
        }
        
        # Compression validation
        comp = self.results["compression"]
        if "semantic" in comp and "mean" in comp["semantic"]:
            mean_ratio = comp["semantic"]["mean"]
            summary["compression_result"] = {
                "mean_ratio": round(mean_ratio, 2),
                "meets_claim": 2.0 <= mean_ratio <= 5.0,
                "status": "PASS" if 2.0 <= mean_ratio <= 5.0 else "FAIL"
            }
        
        # Accuracy validation
        acc = self.results["accuracy"]
        if "semantic" in acc and "mean_accuracy" in acc["semantic"]:
            mean_acc = acc["semantic"]["mean_accuracy"]
            summary["accuracy_result"] = {
                "mean_accuracy": round(mean_acc, 2),
                "meets_claim": mean_acc >= 99.5,
                "status": "PASS" if mean_acc >= 99.5 else "FAIL"
            }
        
        # Latency validation
        lat = self.results["latency"]
        summary["latency_results"] = {}
        for tier in ["l1", "l2"]:
            if tier in lat["read"] and "p95_ms" in lat["read"][tier]:
                p95 = lat["read"][tier]["p95_ms"]
                target = 25.0 if tier == "l1" else 120.0
                summary["latency_results"][tier] = {
                    "p95_ms": round(p95, 2),
                    "target_ms": target,
                    "meets_claim": p95 < target,
                    "status": "PASS" if p95 < target else "FAIL"
                }
        
        return summary
    
    def print_summary(self):
        """Print human-readable summary."""
        print("\n" + "="*60)
        print("NBMF BENCHMARK RESULTS")
        print("="*60)
        
        summary = self.results["summary"]
        
        # Compression
        if "compression_result" in summary:
            cr = summary["compression_result"]
            print(f"\n[COMPRESSION] Ratio: {cr['mean_ratio']}x {cr['status']}")
            print(f"   Claim: {summary['compression_claim']}")
        
        # Accuracy
        if "accuracy_result" in summary:
            ar = summary["accuracy_result"]
            print(f"\n[ACCURACY] {ar['mean_accuracy']:.2f}% {ar['status']}")
            print(f"   Claim: {summary['accuracy_claim']}")
        
        # Latency
        print(f"\n[LATENCY]:")
        for tier, result in summary.get("latency_results", {}).items():
            print(f"   {tier.upper()}: {result['p95_ms']:.2f}ms (target: <{result['target_ms']}ms) {result['status']}")
        
        print("\n" + "="*60)


def main():
    parser = argparse.ArgumentParser(description="NBMF Benchmark Tool")
    parser.add_argument("--samples", type=int, default=100, help="Number of test samples")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner()
    results = runner.run(num_samples=args.samples)
    
    runner.print_summary()
    
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    main()

