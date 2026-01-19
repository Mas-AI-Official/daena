#!/usr/bin/env python3
"""
OCR vs NBMF Comparison Tool

Compares OCR text extraction with NBMF encoding:
- Compression ratios (NBMF vs OCR text storage)
- Accuracy (hash comparison for lossless, similarity for semantic)
- Latency (encode/decode vs OCR extraction)
- Storage size comparison
- Token count estimation

Usage:
    python Tools/daena_ocr_comparison.py --image path/to/image.png
    python Tools/daena_ocr_comparison.py --image path/to/image.png --iterations 20 --output results.json
"""

import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_service.ocr_service import OCRService, OCRProvider, OCRResult
from memory_service.nbmf_encoder import encode as nbmf_encode, Fidelity
from memory_service.nbmf_decoder import decode as nbmf_decode


class OCRNBMFComparison:
    """Comprehensive comparison tool for OCR vs NBMF."""
    
    def __init__(self, ocr_provider: OCRProvider = OCRProvider.TESSERACT):
        """Initialize comparison tool."""
        self.ocr_service = OCRService(provider=ocr_provider)
        self.results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "image_path": None,
            "ocr": {},
            "nbmf": {
                "lossless": {},
                "semantic": {}
            },
            "comparison": {
                "lossless": {},
                "semantic": {}
            },
            "summary": {}
        }
    
    def extract_ocr_text(self, image_path: str) -> OCRResult:
        """Extract text from image using OCR."""
        print(f"📄 Extracting text from image using {self.ocr_service.provider.value}...")
        ocr_result = self.ocr_service.extract_text(image_path)
        print(f"   ✅ Extracted {len(ocr_result.text)} characters in {ocr_result.processing_time_ms:.1f}ms")
        print(f"   📊 Confidence: {ocr_result.confidence:.2%}")
        return ocr_result
    
    def encode_with_nbmf(
        self,
        text: str,
        fidelity: Fidelity,
        iterations: int = 10
    ) -> Dict[str, Any]:
        """Encode text with NBMF and measure metrics."""
        print(f"🔷 Encoding with NBMF ({fidelity} mode)...")
        
        encode_times = []
        decode_times = []
        encoded_sizes = []
        decoded_texts = []
        
        for i in range(iterations):
            # Encode
            start = time.perf_counter()
            encoded = nbmf_encode(text, fidelity=fidelity)
            encode_time = (time.perf_counter() - start) * 1000  # ms
            encode_times.append(encode_time)
            
            # Calculate encoded size
            encoded_json = json.dumps(encoded)
            encoded_size = len(encoded_json.encode('utf-8'))
            encoded_sizes.append(encoded_size)
            
            # Decode
            start = time.perf_counter()
            decoded = nbmf_decode(encoded)
            decode_time = (time.perf_counter() - start) * 1000  # ms
            decode_times.append(decode_time)
            
            # Store decoded text for accuracy check
            decoded_str = decoded if isinstance(decoded, str) else json.dumps(decoded)
            decoded_texts.append(decoded_str)
        
        # Calculate accuracy
        original_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
        exact_matches = sum(1 for dt in decoded_texts if dt == text)
        hash_matches = sum(
            1 for dt in decoded_texts
            if hashlib.sha256(dt.encode('utf-8')).hexdigest() == original_hash
        )
        
        # Calculate similarity for semantic mode
        if fidelity == "semantic":
            similarities = [
                self._calculate_similarity(text, dt) for dt in decoded_texts
            ]
            avg_similarity = statistics.mean(similarities) if similarities else 0.0
        else:
            avg_similarity = 1.0 if exact_matches == iterations else 0.0
        
        result = {
            "encode_latency_ms": {
                "mean": statistics.mean(encode_times),
                "median": statistics.median(encode_times),
                "p95": sorted(encode_times)[int(len(encode_times) * 0.95)] if encode_times else 0,
                "min": min(encode_times) if encode_times else 0,
                "max": max(encode_times) if encode_times else 0
            },
            "decode_latency_ms": {
                "mean": statistics.mean(decode_times),
                "median": statistics.median(decode_times),
                "p95": sorted(decode_times)[int(len(decode_times) * 0.95)] if decode_times else 0,
                "min": min(decode_times) if decode_times else 0,
                "max": max(decode_times) if decode_times else 0
            },
            "size_bytes": {
                "mean": statistics.mean(encoded_sizes),
                "median": statistics.median(encoded_sizes),
                "min": min(encoded_sizes) if encoded_sizes else 0,
                "max": max(encoded_sizes) if encoded_sizes else 0
            },
            "accuracy": {
                "exact_match_rate": exact_matches / iterations if iterations > 0 else 0,
                "hash_match_rate": hash_matches / iterations if iterations > 0 else 0,
                "similarity": avg_similarity
            },
            "iterations": iterations
        }
        
        print(f"   ✅ Encoded {iterations} times")
        print(f"   ⏱️  Encode: {result['encode_latency_ms']['mean']:.2f}ms (p95: {result['encode_latency_ms']['p95']:.2f}ms)")
        print(f"   ⏱️  Decode: {result['decode_latency_ms']['mean']:.2f}ms (p95: {result['decode_latency_ms']['p95']:.2f}ms)")
        print(f"   💾 Size: {result['size_bytes']['mean']:.0f} bytes")
        print(f"   ✅ Accuracy: {result['accuracy']['similarity']:.2%}")
        
        return result
    
    def _calculate_similarity(self, a: str, b: str) -> float:
        """Calculate character-level similarity between two strings."""
        if not a and not b:
            return 1.0
        if not a or not b:
            return 0.0
        
        # Character overlap (Jaccard similarity)
        set_a = set(a.lower())
        set_b = set(b.lower())
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0
    
    def compare(
        self,
        image_path: str,
        iterations: int = 10
    ) -> Dict[str, Any]:
        """Run full comparison between OCR and NBMF."""
        print("=" * 80)
        print("OCR vs NBMF COMPARISON")
        print("=" * 80)
        print()
        
        # Store image path
        self.results["image_path"] = str(image_path)
        
        # Get original image size
        image_path_obj = Path(image_path)
        if not image_path_obj.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        original_size = image_path_obj.stat().st_size
        print(f"📸 Image: {image_path}")
        print(f"   Size: {original_size:,} bytes")
        print()
        
        # Step 1: Extract OCR text
        ocr_result = self.extract_ocr_text(image_path)
        ocr_text = ocr_result.text
        ocr_text_size = len(ocr_text.encode('utf-8'))
        
        self.results["ocr"] = {
            "text_length": len(ocr_text),
            "text_size_bytes": ocr_text_size,
            "processing_time_ms": ocr_result.processing_time_ms,
            "confidence": ocr_result.confidence,
            "provider": ocr_result.provider,
            "word_count": ocr_result.metadata.get("word_count", 0),
            "char_count": ocr_result.metadata.get("char_count", 0)
        }
        print()
        
        # Step 2: Encode with NBMF (lossless)
        nbmf_lossless = self.encode_with_nbmf(ocr_text, fidelity="lossless", iterations=iterations)
        self.results["nbmf"]["lossless"] = nbmf_lossless
        print()
        
        # Step 3: Encode with NBMF (semantic)
        nbmf_semantic = self.encode_with_nbmf(ocr_text, fidelity="semantic", iterations=iterations)
        self.results["nbmf"]["semantic"] = nbmf_semantic
        print()
        
        # Step 4: Calculate comparisons
        print("📊 Calculating comparison metrics...")
        
        # Lossless comparison
        lossless_compression = ocr_text_size / nbmf_lossless["size_bytes"]["mean"] if nbmf_lossless["size_bytes"]["mean"] > 0 else 1.0
        lossless_storage_savings = (1 - nbmf_lossless["size_bytes"]["mean"] / ocr_text_size) * 100 if ocr_text_size > 0 else 0
        lossless_latency_advantage = ocr_result.processing_time_ms / nbmf_lossless["encode_latency_ms"]["mean"] if nbmf_lossless["encode_latency_ms"]["mean"] > 0 else 1.0
        
        self.results["comparison"]["lossless"] = {
            "compression_ratio": lossless_compression,
            "storage_savings_percent": lossless_storage_savings,
            "latency_advantage": lossless_latency_advantage,
            "nbmf_faster_by": f"{lossless_latency_advantage:.1f}x",
            "nbmf_smaller_by": f"{lossless_compression:.2f}x",
            "accuracy": nbmf_lossless["accuracy"]["similarity"]
        }
        
        # Semantic comparison
        semantic_compression = ocr_text_size / nbmf_semantic["size_bytes"]["mean"] if nbmf_semantic["size_bytes"]["mean"] > 0 else 1.0
        semantic_storage_savings = (1 - nbmf_semantic["size_bytes"]["mean"] / ocr_text_size) * 100 if ocr_text_size > 0 else 0
        semantic_latency_advantage = ocr_result.processing_time_ms / nbmf_semantic["encode_latency_ms"]["mean"] if nbmf_semantic["encode_latency_ms"]["mean"] > 0 else 1.0
        
        self.results["comparison"]["semantic"] = {
            "compression_ratio": semantic_compression,
            "storage_savings_percent": semantic_storage_savings,
            "latency_advantage": semantic_latency_advantage,
            "nbmf_faster_by": f"{semantic_latency_advantage:.1f}x",
            "nbmf_smaller_by": f"{semantic_compression:.2f}x",
            "accuracy": nbmf_semantic["accuracy"]["similarity"]
        }
        
        # Step 5: Estimate token counts
        # Rough estimate: 1 token ≈ 4 characters for English
        ocr_tokens = ocr_text_size / 4
        nbmf_lossless_tokens = nbmf_lossless["size_bytes"]["mean"] / 4
        nbmf_semantic_tokens = nbmf_semantic["size_bytes"]["mean"] / 4
        
        self.results["token_estimation"] = {
            "ocr_tokens": ocr_tokens,
            "nbmf_lossless_tokens": nbmf_lossless_tokens,
            "nbmf_semantic_tokens": nbmf_semantic_tokens,
            "lossless_reduction_percent": (1 - nbmf_lossless_tokens / ocr_tokens) * 100 if ocr_tokens > 0 else 0,
            "semantic_reduction_percent": (1 - nbmf_semantic_tokens / ocr_tokens) * 100 if ocr_tokens > 0 else 0
        }
        
        # Generate summary
        self.results["summary"] = {
            "ocr_text_size_bytes": ocr_text_size,
            "ocr_processing_time_ms": ocr_result.processing_time_ms,
            "nbmf_lossless_compression": lossless_compression,
            "nbmf_semantic_compression": semantic_compression,
            "nbmf_lossless_storage_savings": lossless_storage_savings,
            "nbmf_semantic_storage_savings": semantic_storage_savings,
            "nbmf_lossless_latency_advantage": lossless_latency_advantage,
            "nbmf_semantic_latency_advantage": semantic_latency_advantage,
            "nbmf_lossless_accuracy": nbmf_lossless["accuracy"]["similarity"],
            "nbmf_semantic_accuracy": nbmf_semantic["accuracy"]["similarity"]
        }
        
        print("✅ Comparison complete!")
        print()
        
        return self.results
    
    def print_summary(self):
        """Print human-readable summary."""
        s = self.results["summary"]
        comp_lossless = self.results["comparison"]["lossless"]
        comp_semantic = self.results["comparison"]["semantic"]
        
        print("=" * 80)
        print("COMPARISON SUMMARY")
        print("=" * 80)
        print()
        print("OCR EXTRACTION:")
        print(f"  Text Size:        {self.results['ocr']['text_size_bytes']:,} bytes")
        print(f"  Processing Time:  {self.results['ocr']['processing_time_ms']:.1f}ms")
        print(f"  Confidence:       {self.results['ocr']['confidence']:.2%}")
        print()
        print("NBMF LOSSLESS MODE:")
        print(f"  Compression:     {comp_lossless['compression_ratio']:.2f}x ({comp_lossless['storage_savings_percent']:.1f}% savings)")
        print(f"  Encode Latency:  {self.results['nbmf']['lossless']['encode_latency_ms']['mean']:.2f}ms")
        print(f"  Decode Latency:  {self.results['nbmf']['lossless']['decode_latency_ms']['mean']:.2f}ms")
        print(f"  Speed Advantage: {comp_lossless['nbmf_faster_by']}")
        print(f"  Accuracy:        {comp_lossless['accuracy']:.2%}")
        print()
        print("NBMF SEMANTIC MODE:")
        print(f"  Compression:     {comp_semantic['compression_ratio']:.2f}x ({comp_semantic['storage_savings_percent']:.1f}% savings)")
        print(f"  Encode Latency:  {self.results['nbmf']['semantic']['encode_latency_ms']['mean']:.2f}ms")
        print(f"  Decode Latency:  {self.results['nbmf']['semantic']['decode_latency_ms']['mean']:.2f}ms")
        print(f"  Speed Advantage: {comp_semantic['nbmf_faster_by']}")
        print(f"  Accuracy:        {comp_semantic['accuracy']:.2%}")
        print()
        print("TOKEN ESTIMATION:")
        tokens = self.results["token_estimation"]
        print(f"  OCR Tokens:              {tokens['ocr_tokens']:.0f}")
        print(f"  NBMF Lossless Tokens:    {tokens['nbmf_lossless_tokens']:.0f} ({tokens['lossless_reduction_percent']:.1f}% reduction)")
        print(f"  NBMF Semantic Tokens:    {tokens['nbmf_semantic_tokens']:.0f} ({tokens['semantic_reduction_percent']:.1f}% reduction)")
        print()
        print("=" * 80)
        print()
        print("KEY TAKEAWAYS:")
        print(f"  • NBMF Lossless is {comp_lossless['nbmf_smaller_by']} smaller than OCR text")
        print(f"  • NBMF Lossless is {comp_lossless['nbmf_faster_by']} faster than OCR extraction")
        print(f"  • NBMF Semantic is {comp_semantic['nbmf_smaller_by']} smaller than OCR text")
        print(f"  • NBMF Semantic is {comp_semantic['nbmf_faster_by']} faster than OCR extraction")
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
        description="OCR vs NBMF Comparison Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic comparison
  python Tools/daena_ocr_comparison.py --image test_image.png
  
  # With more iterations for better statistics
  python Tools/daena_ocr_comparison.py --image test_image.png --iterations 20
  
  # Save results to file
  python Tools/daena_ocr_comparison.py --image test_image.png --output results.json
  
  # Use EasyOCR instead of Tesseract
  python Tools/daena_ocr_comparison.py --image test_image.png --ocr-provider easyocr
        """
    )
    parser.add_argument(
        "--image",
        type=str,
        required=True,
        help="Path to image file for OCR extraction"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=10,
        help="Number of iterations for NBMF encoding (default: 10)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: ocr_comparison_results.json)"
    )
    parser.add_argument(
        "--ocr-provider",
        type=str,
        choices=["tesseract", "easyocr", "google_vision", "mock"],
        default="tesseract",
        help="OCR provider to use (default: tesseract)"
    )
    
    args = parser.parse_args()
    
    # Map provider string to enum
    provider_map = {
        "tesseract": OCRProvider.TESSERACT,
        "easyocr": OCRProvider.EASYOCR,
        "google_vision": OCRProvider.GOOGLE_VISION,
        "mock": OCRProvider.MOCK
    }
    provider = provider_map[args.ocr_provider]
    
    # Create comparison tool
    comparison = OCRNBMFComparison(ocr_provider=provider)
    
    # Run comparison
    try:
        results = comparison.compare(
            image_path=args.image,
            iterations=args.iterations
        )
        
        # Print summary
        comparison.print_summary()
        
        # Save results
        output_path = args.output or "ocr_comparison_results.json"
        comparison.save_results(output_path)
        
        return 0
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
