#!/usr/bin/env python3
"""
Daena Performance Testing Tool

Comprehensive performance testing for Daena AI VP system:
- NBMF compression and latency benchmarks
- CAS hit rate testing
- System resource monitoring
- Workload simulation
- Performance regression detection

Usage:
    python Tools/daena_performance_test.py --test compression
    python Tools/daena_performance_test.py --test all --iterations 50
    python Tools/daena_performance_test.py --test latency --output results.json
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from memory_service.nbmf_encoder import encode as nbmf_encode, Fidelity
    from memory_service.nbmf_decoder import decode as nbmf_decode
    from memory_service.metrics import snapshot as memory_snapshot
    NBMF_AVAILABLE = True
except ImportError:
    NBMF_AVAILABLE = False
    print("⚠️ NBMF modules not available. Some tests will be skipped.")

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil not available. System metrics will be limited.")


class PerformanceTester:
    """Comprehensive performance testing suite for Daena."""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.utcnow().isoformat(),
            "tests": {},
            "system_info": self._get_system_info(),
            "summary": {}
        }
    
    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        info = {
            "platform": sys.platform,
            "python_version": sys.version.split()[0]
        }
        
        if PSUTIL_AVAILABLE:
            try:
                info.update({
                    "cpu_count": psutil.cpu_count(),
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_total_gb": psutil.virtual_memory().total / (1024**3),
                    "memory_available_gb": psutil.virtual_memory().available / (1024**3),
                    "disk_usage_percent": psutil.disk_usage('/').percent
                })
            except Exception:
                pass
        
        return info
    
    def generate_test_data(self, size_kb: int = 10) -> str:
        """Generate test data of specified size."""
        # Sample text for testing
        base_text = """
        This is a sample document for performance testing.
        It contains multiple paragraphs, technical terms, and structured information.
        The purpose is to test NBMF compression and latency performance.
        """
        
        # Repeat to reach target size
        target_size = size_kb * 1024
        repetitions = max(1, target_size // len(base_text))
        text = base_text * repetitions
        return text[:target_size]
    
    def test_compression(
        self,
        iterations: int = 20,
        sizes_kb: List[int] = [1, 10, 100]
    ) -> Dict[str, Any]:
        """Test NBMF compression performance."""
        print("📊 Testing NBMF Compression...")
        
        if not NBMF_AVAILABLE:
            return {"error": "NBMF modules not available"}
        
        results = {
            "lossless": {"ratios": [], "sizes": {"original": [], "compressed": []}},
            "semantic": {"ratios": [], "sizes": {"original": [], "compressed": []}}
        }
        
        for size_kb in sizes_kb:
            print(f"   Testing {size_kb}KB documents...")
            test_data = self.generate_test_data(size_kb)
            original_size = len(test_data.encode('utf-8'))
            
            # Test lossless
            for _ in range(iterations):
                encoded = nbmf_encode(test_data, fidelity="lossless")
                encoded_json = json.dumps(encoded)
                compressed_size = len(encoded_json.encode('utf-8'))
                ratio = original_size / compressed_size if compressed_size > 0 else 1.0
                
                results["lossless"]["ratios"].append(ratio)
                results["lossless"]["sizes"]["original"].append(original_size)
                results["lossless"]["sizes"]["compressed"].append(compressed_size)
            
            # Test semantic
            for _ in range(iterations):
                encoded = nbmf_encode(test_data, fidelity="semantic")
                encoded_json = json.dumps(encoded)
                compressed_size = len(encoded_json.encode('utf-8'))
                ratio = original_size / compressed_size if compressed_size > 0 else 1.0
                
                results["semantic"]["ratios"].append(ratio)
                results["semantic"]["sizes"]["original"].append(original_size)
                results["semantic"]["sizes"]["compressed"].append(compressed_size)
        
        # Calculate statistics
        def calc_stats(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"mean": 0, "median": 0, "min": 0, "max": 0, "std": 0, "p95": 0}
            sorted_vals = sorted(values)
            return {
                "mean": statistics.mean(values),
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0,
                "p95": sorted_vals[int(len(sorted_vals) * 0.95)] if sorted_vals else 0
            }
        
        return {
            "lossless": {
                "compression_ratio": calc_stats(results["lossless"]["ratios"]),
                "size_savings": {
                    "original_mean": statistics.mean(results["lossless"]["sizes"]["original"]),
                    "compressed_mean": statistics.mean(results["lossless"]["sizes"]["compressed"]),
                    "savings_percent": (1 - statistics.mean(results["lossless"]["sizes"]["compressed"]) /
                                       statistics.mean(results["lossless"]["sizes"]["original"])) * 100
                }
            },
            "semantic": {
                "compression_ratio": calc_stats(results["semantic"]["ratios"]),
                "size_savings": {
                    "original_mean": statistics.mean(results["semantic"]["sizes"]["original"]),
                    "compressed_mean": statistics.mean(results["semantic"]["sizes"]["compressed"]),
                    "savings_percent": (1 - statistics.mean(results["semantic"]["sizes"]["compressed"]) /
                                       statistics.mean(results["semantic"]["sizes"]["original"])) * 100
                }
            }
        }
    
    def test_latency(
        self,
        iterations: int = 50,
        sizes_kb: List[int] = [1, 10, 100]
    ) -> Dict[str, Any]:
        """Test NBMF encode/decode latency."""
        print("⏱️  Testing NBMF Latency...")
        
        if not NBMF_AVAILABLE:
            return {"error": "NBMF modules not available"}
        
        encode_times = {"lossless": [], "semantic": []}
        decode_times = {"lossless": [], "semantic": []}
        
        for size_kb in sizes_kb:
            print(f"   Testing {size_kb}KB documents...")
            test_data = self.generate_test_data(size_kb)
            
            for _ in range(iterations):
                # Lossless encode
                start = time.perf_counter()
                encoded = nbmf_encode(test_data, fidelity="lossless")
                encode_times["lossless"].append((time.perf_counter() - start) * 1000)  # ms
                
                # Lossless decode
                start = time.perf_counter()
                nbmf_decode(encoded)
                decode_times["lossless"].append((time.perf_counter() - start) * 1000)  # ms
                
                # Semantic encode
                start = time.perf_counter()
                encoded = nbmf_encode(test_data, fidelity="semantic")
                encode_times["semantic"].append((time.perf_counter() - start) * 1000)  # ms
                
                # Semantic decode
                start = time.perf_counter()
                nbmf_decode(encoded)
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
    
    def test_system_resources(self) -> Dict[str, Any]:
        """Test system resource usage."""
        print("💻 Testing System Resources...")
        
        if not PSUTIL_AVAILABLE:
            return {"error": "psutil not available"}
        
        # Monitor for 10 seconds
        cpu_samples = []
        memory_samples = []
        
        for _ in range(10):
            cpu_samples.append(psutil.cpu_percent(interval=1))
            memory_samples.append(psutil.virtual_memory().percent)
            time.sleep(0.1)
        
        return {
            "cpu": {
                "mean": statistics.mean(cpu_samples),
                "max": max(cpu_samples),
                "min": min(cpu_samples)
            },
            "memory": {
                "mean": statistics.mean(memory_samples),
                "max": max(memory_samples),
                "min": min(memory_samples),
                "total_gb": psutil.virtual_memory().total / (1024**3),
                "available_gb": psutil.virtual_memory().available / (1024**3)
            },
            "disk": {
                "usage_percent": psutil.disk_usage('/').percent,
                "free_gb": psutil.disk_usage('/').free / (1024**3)
            }
        }
    
    def test_memory_metrics(self) -> Dict[str, Any]:
        """Test memory system metrics."""
        print("🧠 Testing Memory Metrics...")
        
        try:
            snapshot = memory_snapshot()
            return {
                "nbmf_reads": snapshot.get("nbmf_reads", 0),
                "nbmf_writes": snapshot.get("nbmf_writes", 0),
                "l1_hits": snapshot.get("l1_hits", 0),
                "cas_hit_rate": snapshot.get("llm_cas_hit_rate", 0),
                "compression_ratio": snapshot.get("compression_ratio", 0)
            }
        except Exception as e:
            return {"error": str(e)}
    
    def run_all_tests(self, iterations: int = 20) -> Dict[str, Any]:
        """Run all performance tests."""
        print("🚀 Starting Comprehensive Performance Test Suite...")
        print(f"   Iterations: {iterations}")
        print()
        
        # Compression test
        self.results["tests"]["compression"] = self.test_compression(iterations=iterations)
        print()
        
        # Latency test
        self.results["tests"]["latency"] = self.test_latency(iterations=iterations)
        print()
        
        # System resources
        self.results["tests"]["system_resources"] = self.test_system_resources()
        print()
        
        # Memory metrics
        self.results["tests"]["memory_metrics"] = self.test_memory_metrics()
        print()
        
        # Generate summary
        self.results["summary"] = self._generate_summary()
        
        return self.results
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate executive summary."""
        summary = {}
        
        # Compression summary
        if "compression" in self.results["tests"]:
            comp = self.results["tests"]["compression"]
            if "lossless" in comp:
                summary["lossless_compression"] = comp["lossless"]["compression_ratio"]["mean"]
                summary["lossless_savings"] = comp["lossless"]["size_savings"]["savings_percent"]
            if "semantic" in comp:
                summary["semantic_compression"] = comp["semantic"]["compression_ratio"]["mean"]
                summary["semantic_savings"] = comp["semantic"]["size_savings"]["savings_percent"]
        
        # Latency summary
        if "latency" in self.results["tests"]:
            lat = self.results["tests"]["latency"]
            if "encode" in lat and "lossless" in lat["encode"]:
                summary["encode_latency_p95_ms"] = lat["encode"]["lossless"]["p95"]
            if "decode" in lat and "lossless" in lat["decode"]:
                summary["decode_latency_p95_ms"] = lat["decode"]["lossless"]["p95"]
        
        # System resources
        if "system_resources" in self.results["tests"]:
            sys_res = self.results["tests"]["system_resources"]
            if "cpu" in sys_res:
                summary["cpu_usage_percent"] = sys_res["cpu"]["mean"]
            if "memory" in sys_res:
                summary["memory_usage_percent"] = sys_res["memory"]["mean"]
        
        return summary
    
    def print_summary(self):
        """Print human-readable summary."""
        s = self.results["summary"]
        
        print("=" * 80)
        print("PERFORMANCE TEST SUMMARY")
        print("=" * 80)
        print()
        
        if "lossless_compression" in s:
            print(f"Lossless Compression: {s['lossless_compression']:.2f}x ({s.get('lossless_savings', 0):.1f}% savings)")
        if "semantic_compression" in s:
            print(f"Semantic Compression: {s['semantic_compression']:.2f}x ({s.get('semantic_savings', 0):.1f}% savings)")
        if "encode_latency_p95_ms" in s:
            print(f"Encode Latency (p95): {s['encode_latency_p95_ms']:.2f}ms")
        if "decode_latency_p95_ms" in s:
            print(f"Decode Latency (p95): {s['decode_latency_p95_ms']:.2f}ms")
        if "cpu_usage_percent" in s:
            print(f"CPU Usage: {s['cpu_usage_percent']:.1f}%")
        if "memory_usage_percent" in s:
            print(f"Memory Usage: {s['memory_usage_percent']:.1f}%")
        
        print()
        print("=" * 80)
    
    def save_results(self, output_path: str):
        """Save results to JSON file."""
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        
        with output.open('w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Results saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Daena Performance Testing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests
  python Tools/daena_performance_test.py --test all
  
  # Test compression only
  python Tools/daena_performance_test.py --test compression
  
  # Test with more iterations
  python Tools/daena_performance_test.py --test all --iterations 50
  
  # Save results to file
  python Tools/daena_performance_test.py --test all --output results.json
        """
    )
    parser.add_argument(
        "--test",
        type=str,
        choices=["all", "compression", "latency", "system", "memory"],
        default="all",
        help="Test to run (default: all)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Number of iterations per test (default: 20)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: performance_test_results.json)"
    )
    
    args = parser.parse_args()
    
    tester = PerformanceTester()
    
    try:
        if args.test == "all":
            results = tester.run_all_tests(iterations=args.iterations)
        elif args.test == "compression":
            tester.results["tests"]["compression"] = tester.test_compression(iterations=args.iterations)
            tester.results["summary"] = tester._generate_summary()
        elif args.test == "latency":
            tester.results["tests"]["latency"] = tester.test_latency(iterations=args.iterations)
            tester.results["summary"] = tester._generate_summary()
        elif args.test == "system":
            tester.results["tests"]["system_resources"] = tester.test_system_resources()
            tester.results["summary"] = tester._generate_summary()
        elif args.test == "memory":
            tester.results["tests"]["memory_metrics"] = tester.test_memory_metrics()
            tester.results["summary"] = tester._generate_summary()
        
        # Print summary
        tester.print_summary()
        
        # Save results
        output_path = args.output or "performance_test_results.json"
        tester.save_results(output_path)
        
        return 0
        
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

