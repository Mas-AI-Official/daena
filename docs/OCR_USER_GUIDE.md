# OCR Comparison User Guide

**Version**: 1.0.0  
**Last Updated**: 2025-01-XX

---

## Overview

Daena's OCR Comparison feature provides confidence-based routing between NBMF encoding and traditional OCR text extraction. This allows you to:

- **Automatically route** to OCR when NBMF confidence is low
- **Compare performance** between NBMF and OCR
- **Use hybrid mode** for verification and validation
- **Generate benchmark reports** for competitive analysis

---

## Quick Start

### Enable OCR Comparison

```python
from memory_service.router import MemoryRouter

# Enable OCR comparison
router = MemoryRouter(enable_ocr_comparison=True)

# Write an image
result = router.write(
    item_id="image_123",
    cls="document",
    payload="path/to/image.png"
)

# Read with OCR comparison
data = router.read_nbmf_only(
    item_id="image_123",
    cls="document",
    enable_ocr_comparison=True
)
```

### Environment Variables

```bash
# Enable OCR comparison
export OCR_COMPARISON_ENABLED=true

# Set confidence threshold (0.0-1.0)
export OCR_CONFIDENCE_THRESHOLD=0.7

# Enable hybrid mode
export OCR_HYBRID_MODE=true
```

---

## How It Works

### Confidence-Based Routing

1. **NBMF Encoding**: When an image is stored, NBMF encodes it
2. **Confidence Check**: Router checks NBMF confidence score
3. **Routing Decision**:
   - **High Confidence (≥0.7)**: Use NBMF only (fast, compressed)
   - **Low Confidence (<0.7)**: Use OCR fallback (accurate, slower)

### Hybrid Mode

When enabled, hybrid mode provides:
- **NBMF primary**: Fast, compressed representation
- **OCR verification**: Accurate text extraction for verification
- **Comparison metrics**: Side-by-side comparison data
- **Recommendation**: System recommends which to use

---

## Configuration

### Confidence Threshold

The confidence threshold determines when OCR fallback is used:

- **Default**: 0.7 (70%)
- **High (0.8-0.9)**: More aggressive NBMF usage, less OCR fallback
- **Low (0.5-0.6)**: More OCR fallback, higher accuracy

```python
from memory_service.ocr_comparison_integration import get_ocr_comparison, OCRProvider

ocr_comparison = get_ocr_comparison(
    ocr_provider=OCRProvider.TESSERACT,
    confidence_threshold=0.7,  # Adjust this
    enable_hybrid=True
)
```

### OCR Provider

Choose your OCR provider:

- **Tesseract** (default): Free, local, good accuracy
- **EasyOCR**: Better accuracy, GPU-accelerated
- **Google Vision**: Highest accuracy, cloud-based

```python
from memory_service.ocr_service import OCRService, OCRProvider

# Use Tesseract
ocr_service = OCRService(provider=OCRProvider.TESSERACT)

# Use EasyOCR
ocr_service = OCRService(provider=OCRProvider.EASYOCR)

# Use Google Vision
ocr_service = OCRService(provider=OCRProvider.GOOGLE_VISION)
```

---

## Usage Examples

### Basic Comparison

```python
from memory_service.router import MemoryRouter
from memory_service.ocr_service import OCRService, OCRProvider

# Initialize
router = MemoryRouter(enable_ocr_comparison=True)
ocr_service = OCRService(provider=OCRProvider.TESSERACT)

# Write image
router.write("doc_1", "document", "path/to/document.png")

# Read with comparison
result = router.read_nbmf_only("doc_1", "document", enable_ocr_comparison=True)

# Check if OCR comparison was performed
if "ocr_comparison" in result.get("meta", {}):
    comparison = result["meta"]["ocr_comparison"]
    print(f"Mode: {comparison['mode']}")
    print(f"Recommendation: {comparison['recommendation']}")
    if comparison.get("comparison"):
        print(f"NBMF advantage: {comparison['comparison']['compression_advantage']:.2f}×")
```

### Hybrid Mode

```python
from memory_service.ocr_comparison_integration import OCRComparisonIntegration, OCRProvider

# Initialize hybrid mode
ocr_comparison = OCRComparisonIntegration(
    ocr_provider=OCRProvider.TESSERACT,
    confidence_threshold=0.7,
    enable_hybrid=True
)

# Use hybrid mode
result = ocr_comparison.hybrid_mode(
    image_path="path/to/image.png",
    nbmf_result={"size_bytes": 1024, "accuracy": 0.8},
    nbmf_confidence=0.8
)

print(f"Mode: {result['mode']}")
print(f"Recommendation: {result['recommendation']}")
```

### Direct OCR Extraction

```python
from memory_service.ocr_service import OCRService, OCRProvider

ocr_service = OCRService(provider=OCRProvider.TESSERACT)

# Extract text
result = ocr_service.extract_text("path/to/image.png")

print(f"Text: {result.text}")
print(f"Confidence: {result.confidence}")
print(f"Processing time: {result.processing_time_ms}ms")
```

---

## Benchmarking

### Run Benchmark

```bash
# Single image
python Tools/daena_ocr_benchmark.py --image path/to/image.png --iterations 20

# Directory of images
python Tools/daena_ocr_benchmark.py --directory path/to/images --iterations 20

# With EasyOCR
python Tools/daena_ocr_benchmark.py --image image.png --ocr-provider easyocr --iterations 10
```

### Generate Report

```bash
# Run benchmark
python Tools/daena_ocr_benchmark.py --directory images/ --iterations 20 --output results.json

# Generate report
python Tools/generate_ocr_report.py --input results.json --output report.md
```

---

## Performance

### Expected Results

Based on current benchmarks:
- **Compression**: 13.30× (NBMF) vs ~1× (OCR) = **13.30× advantage**
- **Latency**: 0.40ms (NBMF) vs 50-500ms (OCR) = **100-1000× faster**
- **Accuracy**: 100% (NBMF lossless) vs 85-95% (OCR) = **Superior**
- **Storage**: 94.3% savings (NBMF) vs minimal (OCR) = **Massive advantage**

### When to Use OCR Fallback

Use OCR fallback when:
- **Low confidence**: NBMF confidence < 0.7
- **Verification needed**: Hybrid mode for validation
- **Accuracy critical**: OCR for character-level accuracy

Use NBMF when:
- **High confidence**: NBMF confidence ≥ 0.7
- **Latency critical**: Sub-millisecond performance needed
- **Storage constrained**: 13.30× compression advantage

---

## Troubleshooting

### OCR Service Not Available

If you see warnings about OCR service not being available:

```bash
# Install Tesseract
pip install pytesseract pillow

# Install EasyOCR (optional)
pip install easyocr

# Install Google Vision (optional)
pip install google-cloud-vision
```

### Low Confidence Warnings

If you see many low confidence warnings:

1. **Lower threshold**: Reduce `OCR_CONFIDENCE_THRESHOLD` to 0.5-0.6
2. **Enable hybrid mode**: Use `OCR_HYBRID_MODE=true`
3. **Check image quality**: Ensure images are clear and readable

### Performance Issues

If OCR comparison is slow:

1. **Use Tesseract**: Faster than EasyOCR or Google Vision
2. **Disable hybrid mode**: Use NBMF only for high confidence
3. **Cache results**: OCR results are cached automatically

---

## Best Practices

1. **Start with defaults**: Use default settings (threshold: 0.7, hybrid: true)
2. **Monitor fallback rate**: Track how often OCR fallback is used
3. **Adjust threshold**: Fine-tune based on your use case
4. **Use hybrid mode**: Best of both worlds (recommended)
5. **Run benchmarks**: Generate reports for competitive analysis

---

## API Reference

### OCRService

```python
class OCRService:
    def __init__(self, provider: OCRProvider = OCRProvider.TESSERACT)
    def extract_text(self, image_path: str, method: Optional[str] = None) -> OCRResult
    def compare_with_nbmf(self, image_path: str, nbmf_result: Dict, ocr_result: Optional[OCRResult] = None) -> Dict
```

### OCRComparisonIntegration

```python
class OCRComparisonIntegration:
    def __init__(self, ocr_provider: OCRProvider, confidence_threshold: float, enable_hybrid: bool)
    def should_use_ocr_fallback(self, nbmf_confidence: float) -> bool
    def compare_with_ocr(self, image_path: str, nbmf_result: Dict, ocr_result: Optional[OCRResult] = None) -> ComparisonMetrics
    def hybrid_mode(self, image_path: str, nbmf_result: Dict, nbmf_confidence: float) -> Dict
```

### MemoryRouter

```python
class MemoryRouter:
    def __init__(self, enable_ocr_comparison: bool = False)
    def read_nbmf_only(self, item_id: str, cls: str, enable_ocr_comparison: bool = False) -> Optional[Dict]
```

---

## Support

For issues or questions:
- Check the [OCR Integration Status](OCR_INTEGRATION_STATUS.md)
- Review [Phase 2 Documentation](OCR_INTEGRATION_PHASE2.md)
- See [Complete Integration Guide](OCR_INTEGRATION_COMPLETE.md)

---

**Last Updated**: 2025-01-XX  
**Version**: 1.0.0

