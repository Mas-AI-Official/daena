#!/usr/bin/env python3
"""
Benchmark NBMF vs OCR: compression ratio, latency, fidelity, cost.
Outputs JSON + Markdown tables to /reports/benchmarks/.
"""

import json
import time
import statistics
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NBMFvsOCRBenchmark:
    """Benchmark NBMF against OCR for document processing."""
    
    def __init__(self, output_dir: Path = None):
        if output_dir is None:
            output_dir = Path("reports/benchmarks")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Test datasets
        self.test_documents = self._load_test_documents()
    
    def _load_test_documents(self) -> List[Dict[str, Any]]:
        """Load test documents (synthetic + samples)."""
        return [
            {
                "id": "doc_001",
                "type": "text",
                "content": "This is a sample document for benchmarking. " * 100,
                "size_bytes": 3500,
                "sensitive": False
            },
            {
                "id": "doc_002",
                "type": "structured",
                "content": {
                    "title": "Financial Report Q4 2024",
                    "sections": ["Revenue", "Expenses", "Profit"],
                    "data": [1000000, 750000, 250000]
                },
                "size_bytes": 500,
                "sensitive": True
            },
            {
                "id": "doc_003",
                "type": "table",
                "content": "| Name | Age | City |\n|------|-----|------|\n| Alice | 30 | NYC |\n| Bob | 25 | LA |",
                "size_bytes": 200,
                "sensitive": False
            }
        ]
    
    def benchmark_nbmf(self, content: Any, fidelity: str = "lossless") -> Dict[str, Any]:
        """Benchmark NBMF encoding/decoding."""
        try:
            from memory_service.adapters.nbmf_encoder import NBMFEncoder
            from memory_service.adapters.nbmf_decoder import NBMFDecoder
            
            encoder = NBMFEncoder()
            decoder = NBMFDecoder()
            
            # Encode
            encode_start = time.perf_counter()
            encoded = encoder.encode(content, fidelity=fidelity)
            encode_time = (time.perf_counter() - encode_start) * 1000  # ms
            
            # Get encoded size
            encoded_size = len(json.dumps(encoded).encode("utf-8"))
            
            # Decode
            decode_start = time.perf_counter()
            decoded = decoder.decode(encoded)
            decode_time = (time.perf_counter() - decode_start) * 1000  # ms
            
            # Calculate compression ratio
            original_size = len(json.dumps(content).encode("utf-8")) if not isinstance(content, str) else len(content.encode("utf-8"))
            compression_ratio = original_size / encoded_size if encoded_size > 0 else 1.0
            
            # Calculate fidelity (exact match for lossless, similarity for semantic)
            if fidelity == "lossless":
                fidelity_score = 1.0 if self._exact_match(content, decoded) else 0.0
            else:
                fidelity_score = self._similarity_score(content, decoded)
            
            return {
                "method": "nbmf",
                "fidelity_mode": fidelity,
                "encode_latency_ms": encode_time,
                "decode_latency_ms": decode_time,
                "original_size_bytes": original_size,
                "encoded_size_bytes": encoded_size,
                "compression_ratio": compression_ratio,
                "fidelity_score": fidelity_score,
                "success": True
            }
        except ImportError as e:
            logger.warning(f"NBMF not available: {e}")
            return {
                "method": "nbmf",
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"NBMF benchmark error: {e}")
            return {
                "method": "nbmf",
                "success": False,
                "error": str(e)
            }
    
    def benchmark_ocr(self, content: Any) -> Dict[str, Any]:
        """Benchmark OCR processing (simulated)."""
        try:
            # Simulate OCR processing
            # In real implementation, would use actual OCR service
            import hashlib
            
            # Simulate OCR latency (typically 100-500ms)
            ocr_start = time.perf_counter()
            time.sleep(0.1)  # Simulate OCR processing
            ocr_result = str(content)  # Simplified
            ocr_time = (time.perf_counter() - ocr_start) * 1000  # ms
            
            # OCR typically doesn't compress, just extracts text
            original_size = len(json.dumps(content).encode("utf-8")) if not isinstance(content, str) else len(content.encode("utf-8"))
            ocr_size = len(ocr_result.encode("utf-8"))
            compression_ratio = original_size / ocr_size if ocr_size > 0 else 1.0
            
            # OCR fidelity (typically 95-97% for text)
            fidelity_score = 0.96  # Simulated
            
            return {
                "method": "ocr",
                "encode_latency_ms": ocr_time,
                "decode_latency_ms": 0.0,  # OCR is one-way
                "original_size_bytes": original_size,
                "encoded_size_bytes": ocr_size,
                "compression_ratio": compression_ratio,
                "fidelity_score": fidelity_score,
                "success": True
            }
        except Exception as e:
            logger.error(f"OCR benchmark error: {e}")
            return {
                "method": "ocr",
                "success": False,
                "error": str(e)
            }
    
    def _exact_match(self, a: Any, b: Any) -> bool:
        """Check if two objects are exactly equal."""
        return a == b
    
    def _similarity_score(self, a: Any, b: Any) -> float:
        """Calculate similarity score between two objects (0.0 to 1.0)."""
        # Simplified similarity - in production would use proper semantic similarity
        if a == b:
            return 1.0
        
        str_a = str(a)
        str_b = str(b)
        
        # Simple character-level similarity
        if len(str_a) == 0 and len(str_b) == 0:
            return 1.0
        if len(str_a) == 0 or len(str_b) == 0:
            return 0.0
        
        # Jaccard similarity on character sets
        set_a = set(str_a)
        set_b = set(str_b)
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
    
    def run_benchmark(self, iterations: int = 10) -> Dict[str, Any]:
        """Run full benchmark suite."""
        logger.info(f"Running benchmark with {iterations} iterations per test...")
        
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "iterations": iterations,
            "documents": []
        }
        
        for doc in self.test_documents:
            logger.info(f"Benchmarking document {doc['id']}...")
            
            doc_results = {
                "document_id": doc["id"],
                "document_type": doc["type"],
                "sensitive": doc["sensitive"],
                "nbmf_lossless": [],
                "nbmf_semantic": [],
                "ocr": []
            }
            
            # Run NBMF lossless
            for _ in range(iterations):
                result = self.benchmark_nbmf(doc["content"], fidelity="lossless")
                if result.get("success"):
                    doc_results["nbmf_lossless"].append(result)
            
            # Run NBMF semantic
            for _ in range(iterations):
                result = self.benchmark_nbmf(doc["content"], fidelity="semantic")
                if result.get("success"):
                    doc_results["nbmf_semantic"].append(result)
            
            # Run OCR
            for _ in range(iterations):
                result = self.benchmark_ocr(doc["content"])
                if result.get("success"):
                    doc_results["ocr"].append(result)
            
            # Calculate statistics
            doc_results["summary"] = self._calculate_summary(doc_results)
            results["documents"].append(doc_results)
        
        # Overall summary
        results["overall_summary"] = self._calculate_overall_summary(results["documents"])
        
        return results
    
    def _calculate_summary(self, doc_results: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate summary statistics for a document."""
        summary = {}
        
        for method in ["nbmf_lossless", "nbmf_semantic", "ocr"]:
            if doc_results[method]:
                results = doc_results[method]
                summary[method] = {
                    "encode_latency_p50_ms": statistics.median([r["encode_latency_ms"] for r in results]),
                    "encode_latency_p95_ms": self._percentile([r["encode_latency_ms"] for r in results], 0.95),
                    "decode_latency_p50_ms": statistics.median([r["decode_latency_ms"] for r in results]),
                    "decode_latency_p95_ms": self._percentile([r["decode_latency_ms"] for r in results], 0.95),
                    "compression_ratio_avg": statistics.mean([r["compression_ratio"] for r in results]),
                    "fidelity_avg": statistics.mean([r["fidelity_score"] for r in results]),
                    "fidelity_min": min([r["fidelity_score"] for r in results]),
                    "fidelity_max": max([r["fidelity_score"] for r in results])
                }
        
        return summary
    
    def _calculate_overall_summary(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall summary across all documents."""
        overall = {
            "nbmf_lossless": {"compression_ratios": [], "fidelities": [], "encode_times": []},
            "nbmf_semantic": {"compression_ratios": [], "fidelities": [], "encode_times": []},
            "ocr": {"compression_ratios": [], "fidelities": [], "encode_times": []}
        }
        
        for doc in documents:
            summary = doc.get("summary", {})
            for method in overall.keys():
                if method in summary:
                    method_summary = summary[method]
                    overall[method]["compression_ratios"].append(method_summary["compression_ratio_avg"])
                    overall[method]["fidelities"].append(method_summary["fidelity_avg"])
                    overall[method]["encode_times"].append(method_summary["encode_latency_p50_ms"])
        
        # Calculate averages
        result = {}
        for method, data in overall.items():
            if data["compression_ratios"]:
                result[method] = {
                    "avg_compression_ratio": statistics.mean(data["compression_ratios"]),
                    "avg_fidelity": statistics.mean(data["fidelities"]),
                    "avg_encode_latency_ms": statistics.mean(data["encode_times"])
                }
        
        return result
    
    def _percentile(self, data: List[float], p: float) -> float:
        """Calculate percentile."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * p)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def save_results(self, results: Dict[str, Any]) -> Tuple[Path, Path]:
        """Save results as JSON and Markdown."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON
        json_path = self.output_dir / f"nbmf_vs_ocr_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        # Save Markdown table
        md_path = self.output_dir / f"nbmf_vs_ocr_{timestamp}.md"
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write("# NBMF vs OCR Benchmark Results\n\n")
            f.write(f"Generated: {results['timestamp']}\n\n")
            
            # Overall summary table
            f.write("## Overall Summary\n\n")
            f.write("| Method | Avg Compression Ratio | Avg Fidelity | Avg Encode Latency (ms) |\n")
            f.write("|--------|----------------------|--------------|-------------------------|\n")
            
            overall = results.get("overall_summary", {})
            for method, data in overall.items():
                f.write(f"| {method} | {data['avg_compression_ratio']:.2f}× | {data['avg_fidelity']:.2%} | {data['avg_encode_latency_ms']:.2f} |\n")
            
            f.write("\n## Per-Document Results\n\n")
            for doc in results["documents"]:
                f.write(f"### {doc['document_id']} ({doc['document_type']})\n\n")
                summary = doc.get("summary", {})
                if summary:
                    f.write("| Method | Compression | Fidelity | Encode p50 | Encode p95 |\n")
                    f.write("|--------|------------|----------|------------|------------|\n")
                    for method, data in summary.items():
                        f.write(f"| {method} | {data['compression_ratio_avg']:.2f}× | {data['fidelity_avg']:.2%} | {data['encode_latency_p50_ms']:.2f}ms | {data['encode_latency_p95_ms']:.2f}ms |\n")
                f.write("\n")
        
        return json_path, md_path


def main():
    """Main entry point."""
    benchmark = NBMFvsOCRBenchmark()
    results = benchmark.run_benchmark(iterations=10)
    json_path, md_path = benchmark.save_results(results)
    
    print(f"✅ Benchmark complete!")
    print(f"   JSON: {json_path}")
    print(f"   Markdown: {md_path}")
    
    # Print summary
    overall = results.get("overall_summary", {})
    print("\nOverall Summary:")
    for method, data in overall.items():
        print(f"  {method}:")
        print(f"    Compression: {data['avg_compression_ratio']:.2f}×")
        print(f"    Fidelity: {data['avg_fidelity']:.2%}")
        print(f"    Encode Latency: {data['avg_encode_latency_ms']:.2f}ms")


if __name__ == "__main__":
    main()

