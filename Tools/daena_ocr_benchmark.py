#!/usr/bin/env python3
"""
OCR Benchmark Tool

Comprehensive benchmark tool for OCR vs NBMF comparison.
Generates detailed reports with statistical analysis.

Usage:
    python Tools/daena_ocr_benchmark.py --directory path/to/images --iterations 20
    python Tools/daena_ocr_benchmark.py --image path/to/image.png --iterations 10
"""

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Dict, Any, List
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_service.ocr_service import OCRService, OCRProvider
from memory_service.router import MemoryRouter
from memory_service.nbmf_encoder_production import ProductionNBMFEncoder
from Tools.daena_ocr_comparison import compare_ocr_vs_nbmf


def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """Calculate statistical measures."""
    if not values:
        return {}
    
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "p95": sorted(values)[int(len(values) * 0.95)] if len(values) > 0 else 0.0,
        "p99": sorted(values)[int(len(values) * 0.99)] if len(values) > 0 else 0.0
    }


def run_benchmark(
    image_paths: List[Path],
    iterations: int = 20,
    ocr_provider: str = "tesseract"
) -> Dict[str, Any]:
    """
    Run comprehensive OCR vs NBMF benchmark.
    
    Returns:
        Detailed benchmark results with statistics
    """
    print("🚀 Starting OCR vs NBMF Benchmark")
    print(f"   Images: {len(image_paths)}")
    print(f"   Iterations: {iterations}")
    print(f"   OCR Provider: {ocr_provider}")
    print()
    
    # Initialize services
    provider = OCRProvider[ocr_provider.upper()] if hasattr(OCRProvider, ocr_provider.upper()) else OCRProvider.TESSERACT
    ocr_service = OCRService(provider=provider)
    router = MemoryRouter()
    encoder = ProductionNBMFEncoder()
    
    all_results = []
    nbmf_compressions = []
    ocr_compressions = []
    nbmf_latencies = []
    ocr_latencies = []
    accuracies = []
    
    start_time = time.time()
    
    for iteration in range(iterations):
        print(f"📊 Iteration {iteration + 1}/{iterations}")
        
        for image_path in image_paths:
            try:
                result = compare_ocr_vs_nbmf(
                    image_path=image_path,
                    ocr_service=ocr_service,
                    router=router,
                    encoder=encoder
                )
                all_results.append(result)
                
                # Collect metrics
                nbmf_compressions.append(result["nbmf"]["compression_ratio"])
                ocr_compressions.append(result["ocr"]["compression_ratio"])
                nbmf_latencies.append(result["nbmf"]["latency_ms"])
                ocr_latencies.append(result["ocr"]["latency_ms"])
                accuracies.append(result["nbmf"]["accuracy"])
                
                print(f"  ✅ {image_path.name}")
            except Exception as e:
                print(f"  ❌ Error processing {image_path}: {e}")
        
        print()
    
    total_time = time.time() - start_time
    
    # Calculate statistics
    nbmf_compression_stats = calculate_statistics(nbmf_compressions)
    ocr_compression_stats = calculate_statistics(ocr_compressions)
    nbmf_latency_stats = calculate_statistics(nbmf_latencies)
    ocr_latency_stats = calculate_statistics(ocr_latencies)
    accuracy_stats = calculate_statistics(accuracies)
    
    # Calculate advantages
    avg_compression_advantage = (
        nbmf_compression_stats["mean"] / ocr_compression_stats["mean"]
        if ocr_compression_stats["mean"] > 0 else nbmf_compression_stats["mean"]
    )
    avg_latency_advantage = (
        ocr_latency_stats["mean"] / nbmf_latency_stats["mean"]
        if nbmf_latency_stats["mean"] > 0 else 1.0
    )
    
    return {
        "benchmark_info": {
            "total_images": len(image_paths),
            "iterations": iterations,
            "total_comparisons": len(all_results),
            "ocr_provider": ocr_provider,
            "total_time_seconds": total_time,
            "avg_time_per_comparison": total_time / len(all_results) if all_results else 0
        },
        "nbmf_metrics": {
            "compression": nbmf_compression_stats,
            "latency_ms": nbmf_latency_stats,
            "accuracy": accuracy_stats
        },
        "ocr_metrics": {
            "compression": ocr_compression_stats,
            "latency_ms": ocr_latency_stats
        },
        "comparison": {
            "compression_advantage": {
                "mean": avg_compression_advantage,
                "min": min(nbmf_compressions) / max(ocr_compressions) if ocr_compressions else 0,
                "max": max(nbmf_compressions) / min(ocr_compressions) if ocr_compressions else 0
            },
            "latency_advantage": {
                "mean": avg_latency_advantage,
                "min": min(ocr_latencies) / max(nbmf_latencies) if nbmf_latencies else 0,
                "max": max(ocr_latencies) / min(nbmf_latencies) if nbmf_latencies else 0
            },
            "storage_savings_percent": {
                "mean": (1 - statistics.mean([r["nbmf"]["size_bytes"] / r["ocr"]["size_bytes"] 
                                               for r in all_results if r["ocr"]["size_bytes"] > 0])) * 100
            }
        },
        "results": all_results
    }


def print_benchmark_report(results: Dict[str, Any]) -> None:
    """Print formatted benchmark report."""
    print("=" * 80)
    print("📊 OCR vs NBMF BENCHMARK REPORT")
    print("=" * 80)
    print()
    
    info = results["benchmark_info"]
    print(f"Benchmark Configuration:")
    print(f"  Images: {info['total_images']}")
    print(f"  Iterations: {info['iterations']}")
    print(f"  Total Comparisons: {info['total_comparisons']}")
    print(f"  OCR Provider: {info['ocr_provider']}")
    print(f"  Total Time: {info['total_time_seconds']:.2f}s")
    print(f"  Avg Time per Comparison: {info['avg_time_per_comparison']:.2f}s")
    print()
    
    nbmf = results["nbmf_metrics"]
    ocr = results["ocr_metrics"]
    comp = results["comparison"]
    
    print("NBMF Performance:")
    print(f"  Compression Ratio: {nbmf['compression']['mean']:.2f}× (mean)")
    print(f"    Range: {nbmf['compression']['min']:.2f}× - {nbmf['compression']['max']:.2f}×")
    print(f"    p95: {nbmf['compression']['p95']:.2f}×")
    print(f"  Latency: {nbmf['latency_ms']['mean']:.2f}ms (mean)")
    print(f"    Range: {nbmf['latency_ms']['min']:.2f}ms - {nbmf['latency_ms']['max']:.2f}ms")
    print(f"    p95: {nbmf['latency_ms']['p95']:.2f}ms")
    print(f"  Accuracy: {nbmf['accuracy']['mean']:.1%} (mean)")
    print()
    
    print("OCR Performance:")
    print(f"  Compression Ratio: {ocr['compression']['mean']:.2f}× (mean)")
    print(f"    Range: {ocr['compression']['min']:.2f}× - {ocr['compression']['max']:.2f}×")
    print(f"  Latency: {ocr['latency_ms']['mean']:.2f}ms (mean)")
    print(f"    Range: {ocr['latency_ms']['min']:.2f}ms - {ocr['latency_ms']['max']:.2f}ms")
    print(f"    p95: {ocr['latency_ms']['p95']:.2f}ms")
    print()
    
    print("NBMF Advantages:")
    print(f"  Compression: {comp['compression_advantage']['mean']:.2f}× better (mean)")
    print(f"    Range: {comp['compression_advantage']['min']:.2f}× - {comp['compression_advantage']['max']:.2f}×")
    print(f"  Latency: {comp['latency_advantage']['mean']:.1f}× faster (mean)")
    print(f"    Range: {comp['latency_advantage']['min']:.1f}× - {comp['latency_advantage']['max']:.1f}×")
    print(f"  Storage Savings: {comp['storage_savings_percent']['mean']:.1f}%")
    print()
    
    print("=" * 80)
    print("✅ Benchmark Complete")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive OCR vs NBMF benchmark tool"
    )
    parser.add_argument(
        "--image",
        type=str,
        help="Single image file path"
    )
    parser.add_argument(
        "--directory",
        type=str,
        help="Directory containing images"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Number of iterations (default: 20)"
    )
    parser.add_argument(
        "--ocr-provider",
        type=str,
        default="tesseract",
        choices=["tesseract", "easyocr", "google_vision", "mock"],
        help="OCR provider to use (default: tesseract)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="ocr_benchmark_results.json",
        help="Output JSON file (default: ocr_benchmark_results.json)"
    )
    
    args = parser.parse_args()
    
    # Collect image paths
    image_paths = []
    
    if args.image:
        image_path = Path(args.image)
        if image_path.exists():
            image_paths.append(image_path)
        else:
            print(f"❌ Image not found: {args.image}")
            return 1
    
    elif args.directory:
        directory = Path(args.directory)
        if directory.exists():
            extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'}
            image_paths = [p for p in directory.iterdir() if p.suffix.lower() in extensions]
        else:
            print(f"❌ Directory not found: {args.directory}")
            return 1
    else:
        print("❌ Please provide --image or --directory")
        parser.print_help()
        return 1
    
    if not image_paths:
        print("❌ No images found")
        return 1
    
    # Run benchmark
    results = run_benchmark(
        image_paths=image_paths,
        iterations=args.iterations,
        ocr_provider=args.ocr_provider
    )
    
    # Save results
    output_path = Path(args.output)
    with output_path.open('w') as f:
        json.dump(results, f, indent=2)
    
    # Print report
    print_benchmark_report(results)
    
    print(f"\n✅ Results saved to: {output_path}")
    
    return 0


if __name__ == "__main__":
    exit(main())

