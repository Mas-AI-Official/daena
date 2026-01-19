# Encoder Upgrade Roadmap

**Date**: 2025-01-XX  
**Purpose**: Step-by-step guide for upgrading NBMF encoder

---

## Overview

Upgrade the stub encoder (`memory_service/nbmf_encoder.py`) to a production neural encoder that achieves:
- **Compression**: 2-5× vs raw
- **Accuracy**: 99.5%+ reconstruction
- **Latency**: <120ms L2 (maintain current)

---

## Current Implementation

### Stub Encoder (`memory_service/nbmf_encoder.py`)
```python
# Lossless: zlib compression
# Semantic: Preview text only
```

**Limitations**:
- No neural encoding
- Basic compression only
- Semantic mode incomplete

---

## Target Implementation

### Production Encoder
```python
class ProductionNBMFEncoder:
    def encode(self, payload: Any, fidelity: Fidelity) -> Dict[str, Any]:
        # 1. Neural encoding to latent space
        # 2. Compression of latent representation
        # 3. Return encoded blob with metadata
        
    def decode(self, blob: Dict[str, Any]) -> Any:
        # 1. Decompress latent representation
        # 2. Neural decoding from latent space
        # 3. Return reconstructed payload
```

---

## Implementation Phases

### Phase 1: Design (Week 1)

#### 1.1 Architecture Selection
- [ ] Choose base model (transformer/CNN/hybrid)
- [ ] Design encoder architecture
- [ ] Design decoder architecture
- [ ] Design compression strategy

#### 1.2 Data Requirements
- [ ] Define training data format
- [ ] Estimate data requirements (10K-100K samples)
- [ ] Create data collection plan
- [ ] Set up data storage

#### 1.3 Training Pipeline
- [ ] Design training pipeline
- [ ] Select training framework (PyTorch/TensorFlow)
- [ ] Design loss functions
- [ ] Design validation metrics

**Deliverables**:
- Architecture specification document
- Data collection plan
- Training pipeline design

---

### Phase 2: Data Collection (Week 1-2)

#### 2.1 Data Sources
- [ ] Collect conversational data
- [ ] Collect document data
- [ ] Collect structured data
- [ ] Collect multimodal data (optional)

#### 2.2 Data Processing
- [ ] Preprocess data
- [ ] Clean and validate
- [ ] Create train/val/test splits
- [ ] Generate training pairs (original → compressed → reconstructed)

**Deliverables**:
- Training dataset (10K-100K samples)
- Validation dataset
- Test dataset

---

### Phase 3: Model Training (Week 2-3)

#### 3.1 Training Setup
- [ ] Set up training infrastructure
- [ ] Configure training parameters
- [ ] Initialize models
- [ ] Set up logging/monitoring

#### 3.2 Training Execution
- [ ] Train encoder model
- [ ] Train decoder model
- [ ] Monitor training progress
- [ ] Validate intermediate results

#### 3.3 Model Optimization
- [ ] Quantization (FP16/INT8)
- [ ] Model pruning
- [ ] Latency optimization
- [ ] Size optimization

**Deliverables**:
- Trained encoder model
- Trained decoder model
- Training metrics and logs

---

### Phase 4: Integration (Week 3-4)

#### 4.1 Code Integration
- [ ] Replace stub encoder
- [ ] Integrate with router
- [ ] Add version detection
- [ ] Implement backward compatibility

#### 4.2 Testing
- [ ] Unit tests for encoder/decoder
- [ ] Integration tests
- [ ] Performance tests
- [ ] Regression tests

**Deliverables**:
- Updated `memory_service/nbmf_encoder.py`
- Integration tests
- Performance benchmarks

---

### Phase 5: Validation (Week 4)

#### 5.1 Benchmark Validation
- [ ] Run compression benchmarks
- [ ] Run accuracy benchmarks
- [ ] Run latency benchmarks
- [ ] Validate all claims (2-5×, 99.5%+)

#### 5.2 Production Readiness
- [ ] Operational rehearsal
- [ ] Load testing
- [ ] Error handling validation
- [ ] Documentation update

**Deliverables**:
- Benchmark results report
- Production readiness report
- Updated documentation

---

## Technical Specifications

### Encoder Architecture

#### Option A: Transformer-Based (Recommended for Text)
```python
class TransformerNBMFEncoder:
    def __init__(self):
        self.encoder = TransformerEncoder(
            d_model=768,
            nhead=12,
            num_layers=6,
            dim_feedforward=3072
        )
        self.compressor = LatentCompressor(
            input_dim=768,
            latent_dim=128,  # 6× compression
            quantization="int8"
        )
```

#### Option B: CNN-Based (Recommended for Structured)
```python
class CNNNBMFEncoder:
    def __init__(self):
        self.encoder = CNNEncoder(
            input_channels=1,
            hidden_channels=[64, 128, 256],
            latent_dim=128
        )
        self.compressor = LatentCompressor(
            input_dim=256,
            latent_dim=64,  # 4× compression
            quantization="fp16"
        )
```

### Compression Strategy
1. **Neural Encoding**: Raw → Latent (dimensionality reduction)
2. **Quantization**: FP32 → FP16 or INT8
3. **Entropy Coding**: Additional compression (optional)

### Accuracy Strategy
1. **Reconstruction Loss**: L2 loss on latent space
2. **Semantic Loss**: BLEU/ROUGE on text
3. **Similarity Loss**: Cosine similarity on embeddings

---

## Training Data Format

### Input Format
```json
{
  "id": "sample_1",
  "domain": "general",
  "type": "text",
  "data": "Original text content here...",
  "metadata": {
    "source": "conversation",
    "length": 500
  }
}
```

### Training Pairs
```json
{
  "original": "Original text...",
  "compressed": "Compressed representation...",
  "reconstructed": "Reconstructed text...",
  "compression_ratio": 3.2,
  "similarity_score": 0.997
}
```

---

## Success Metrics

### Compression
- ✅ Mean: 2.0-5.0×
- ✅ P95: ≥2.0×
- ✅ Min: ≥1.5× (outliers acceptable)

### Accuracy
- ✅ Mean: ≥99.5%
- ✅ P95: ≥99.0%
- ✅ Min: ≥98.0%

### Latency
- ✅ Write: <120ms p95
- ✅ Read: <120ms p95
- ✅ No regression

---

## Migration Plan

### Backward Compatibility
1. **Version Detection**: Check `encoder_version` in metadata
2. **Fallback**: Use stub for legacy data
3. **Migration**: Optional script to re-encode existing data

### Rollout
1. **Staging**: Deploy with canary (10%)
2. **Validation**: Run benchmarks
3. **Gradual**: 50% → 100%
4. **Monitor**: Watch for issues

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|-------|------------|
| Model too large | Latency increase | Quantization, caching |
| Poor training data | Low accuracy | Data validation, augmentation |
| Domain mismatch | Poor generalization | Multi-domain training |
| Breaking changes | Compatibility issues | Version detection, fallback |

---

## Timeline

### Week 1: Design & Data Collection
- Architecture design
- Data collection start
- Training setup

### Week 2: Training
- Data collection complete
- Training started
- Initial validation

### Week 3: Integration
- Training complete
- Integration started
- Testing

### Week 4: Validation
- Integration complete
- Benchmarks run
- Production deployment

**Total**: 2-4 weeks

---

## Next Actions

### Immediate
1. Review encoder architecture options
2. Approve design approach
3. Start data collection

### This Week
1. Complete architecture design
2. Begin data collection
3. Set up training infrastructure

### Next Week
1. Complete data collection
2. Start model training
3. Initial validation

---

**Status**: ⏳ Planning Phase  
**Next**: Architecture review and approval  
**Timeline**: 2-4 weeks

