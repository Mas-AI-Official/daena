# NBMF Encoder Upgrade Plan

**Date**: 2025-01-XX  
**Status**: Planning Phase  
**Priority**: High (needed for benchmark validation)

---

## Current Status

### Stub Encoder
- **Location**: `memory_service/nbmf_encoder.py`
- **Status**: Baseline stub (zlib compression, preview text)
- **Limitations**:
  - No neural encoding
  - Basic compression only
  - Semantic mode returns preview (not full encoding)

### Benchmark Results (Stub)
- Compression: 1.14× (FAIL - needs 2-5×)
- Accuracy: 91.73% (FAIL - needs 99.5%+)
- Latency: 18.46ms L2 (PASS ✅)

---

## Target Requirements

### Compression
- **Target**: 2-5× compression ratio
- **Mode**: Semantic (meaning-preserving)
- **Method**: Neural encoder → latent representation → compression

### Accuracy
- **Target**: 99.5%+ accuracy
- **Mode**: Semantic (meaning preserved, phrasing may vary)
- **Method**: Neural decoder → reconstruction → similarity check

### Latency
- **Target**: Maintain current latency (<120ms L2)
- **Method**: Optimized encoding/decoding pipeline

---

## Upgrade Architecture

### Phase 1: Neural Encoder Design

#### 1.1 Encoder Architecture
```python
class NeuralNBMFEncoder:
    """
    Production neural encoder for NBMF.
    
    Architecture:
    - Input: Raw data (text, structured, multimodal)
    - Encoder: Domain-trained transformer/CNN
    - Latent: Compressed representation
    - Decoder: Reconstruction network
    """
    
    def __init__(self, domain: str = "general"):
        self.domain = domain
        self.encoder_model = self._load_encoder(domain)
        self.decoder_model = self._load_decoder(domain)
        self.compression_level = "semantic"  # or "lossless"
    
    def encode(self, payload: Any, fidelity: Fidelity) -> Dict[str, Any]:
        """Encode payload using neural encoder."""
        # 1. Preprocess payload
        # 2. Encode to latent space
        # 3. Compress latent representation
        # 4. Return encoded blob
        pass
    
    def decode(self, blob: Dict[str, Any]) -> Any:
        """Decode blob using neural decoder."""
        # 1. Decompress latent representation
        # 2. Decode from latent space
        # 3. Postprocess to original format
        # 4. Return reconstructed payload
        pass
```

#### 1.2 Domain-Specific Encoders
- **General**: Conversational data, general text
- **Financial**: Financial documents, transactions
- **Legal**: Legal documents, contracts
- **Technical**: Code, technical documentation

#### 1.3 Training Data Requirements
- **Size**: 10K-100K samples per domain
- **Format**: Text, structured JSON, mixed
- **Quality**: High-quality, diverse samples
- **Labeling**: Original → compressed → reconstructed pairs

---

### Phase 2: Implementation

#### 2.1 Encoder Implementation
**File**: `memory_service/nbmf_encoder.py` (replace stub)

**Components**:
1. Neural encoder model loading
2. Encoding pipeline (preprocess → encode → compress)
3. Decoding pipeline (decompress → decode → postprocess)
4. Domain routing (select encoder by class/domain)

#### 2.2 Integration Points
- `memory_service/router.py` - Write/read paths
- `memory_service/aging.py` - Compression policies
- `memory_service/metrics.py` - Encoding metrics

#### 2.3 Backward Compatibility
- Support legacy stub encoder (fallback)
- Version detection (stub vs. neural)
- Migration path for existing data

---

### Phase 3: Training & Validation

#### 3.1 Training Pipeline
```python
# Training script
python training/train_nbmf_encoder.py \
  --domain general \
  --data data/training/general/ \
  --epochs 50 \
  --batch_size 32 \
  --output models/nbmf_encoder_general.pt
```

#### 3.2 Validation
- Compression ratio validation (target: 2-5×)
- Accuracy validation (target: 99.5%+)
- Latency validation (target: <120ms L2)

#### 3.3 Benchmark Integration
```bash
# Run benchmarks with new encoder
python bench/benchmark_nbmf.py \
  --samples 200 \
  --encoder neural \
  --output bench/production_results.json
```

---

## Implementation Steps

### Step 1: Design & Architecture (Week 1)
- [ ] Design neural encoder architecture
- [ ] Select base model (transformer, CNN, etc.)
- [ ] Design training pipeline
- [ ] Create training data collection plan

### Step 2: Data Collection (Week 1-2)
- [ ] Collect training data (10K-100K samples)
- [ ] Preprocess and clean data
- [ ] Create train/val/test splits
- [ ] Validate data quality

### Step 3: Model Training (Week 2-3)
- [ ] Set up training infrastructure
- [ ] Train base encoder model
- [ ] Train decoder model
- [ ] Validate training progress

### Step 4: Integration (Week 3-4)
- [ ] Replace stub encoder
- [ ] Integrate with router
- [ ] Add version detection
- [ ] Implement backward compatibility

### Step 5: Validation (Week 4)
- [ ] Run benchmarks
- [ ] Validate compression (2-5×)
- [ ] Validate accuracy (99.5%+)
- [ ] Validate latency (<120ms)
- [ ] Update documentation

---

## Technical Requirements

### Model Architecture Options

#### Option 1: Transformer-Based
- **Pros**: State-of-the-art, good for text
- **Cons**: Larger model, more compute
- **Use Case**: General, conversational data

#### Option 2: CNN-Based
- **Pros**: Efficient, good for structured data
- **Cons**: Less flexible for variable-length
- **Use Case**: Structured, fixed-format data

#### Option 3: Hybrid
- **Pros**: Best of both worlds
- **Cons**: More complex
- **Use Case**: Mixed data types

### Compression Strategy
- **Latent Space**: Reduce dimensions (e.g., 768 → 128)
- **Quantization**: FP16 or INT8 quantization
- **Entropy Coding**: Additional compression on latent

### Accuracy Strategy
- **Loss Function**: Reconstruction loss + semantic similarity
- **Validation**: BLEU, ROUGE, semantic similarity
- **Threshold**: 99.5%+ similarity score

---

## Training Data Requirements

### General Domain
- **Conversations**: 50K samples
- **Documents**: 30K samples
- **Structured Data**: 20K samples

### Financial Domain
- **Transactions**: 20K samples
- **Reports**: 15K samples
- **Statements**: 15K samples

### Legal Domain
- **Contracts**: 20K samples
- **Legal Documents**: 15K samples
- **Compliance**: 15K samples

---

## Success Criteria

### Compression
- ✅ Mean ratio: 2.0-5.0×
- ✅ P95 ratio: ≥2.0×
- ✅ No samples <1.5× (outliers acceptable)

### Accuracy
- ✅ Mean accuracy: ≥99.5%
- ✅ P95 accuracy: ≥99.0%
- ✅ Min accuracy: ≥98.0%

### Latency
- ✅ L2 write: <120ms p95
- ✅ L2 read: <120ms p95
- ✅ No regression from current performance

---

## Migration Strategy

### Backward Compatibility
1. **Version Detection**: Check encoder version in metadata
2. **Fallback**: Use stub encoder for legacy data
3. **Migration**: Optional migration script for existing data

### Rollout Plan
1. **Staging**: Deploy with canary (10% traffic)
2. **Validation**: Run benchmarks, check metrics
3. **Gradual**: Increase to 50%, then 100%
4. **Monitor**: Watch for regressions

---

## Risk Mitigation

### Risks
1. **Model Size**: Large models may impact latency
   - **Mitigation**: Model quantization, caching
2. **Training Data**: Insufficient or poor quality
   - **Mitigation**: Data validation, augmentation
3. **Domain Mismatch**: Model doesn't generalize
   - **Mitigation**: Multi-domain training, fine-tuning
4. **Backward Compatibility**: Breaking changes
   - **Mitigation**: Version detection, fallback

---

## Timeline

### Estimated Duration: 2-4 Weeks

- **Week 1**: Design, data collection
- **Week 2**: Training setup, initial training
- **Week 3**: Training completion, integration
- **Week 4**: Validation, benchmarks, deployment

### Milestones
- [ ] Week 1: Architecture approved, data collected
- [ ] Week 2: Training started, initial results
- [ ] Week 3: Model trained, integrated
- [ ] Week 4: Benchmarks passing, deployed

---

## Resources Needed

### Infrastructure
- GPU cluster for training (optional, can use CPU)
- Storage for training data
- Model storage/versioning

### Data
- Training datasets (10K-100K samples per domain)
- Validation datasets
- Test datasets

### Tools
- Training framework (PyTorch, TensorFlow, etc.)
- Data preprocessing tools
- Model evaluation tools

---

## Next Actions

### Immediate (This Week)
1. Review and approve encoder architecture
2. Start data collection
3. Set up training infrastructure

### Short-Term (Next 2 Weeks)
1. Complete data collection
2. Begin model training
3. Initial validation

### Medium-Term (Next Month)
1. Complete training
2. Integration and testing
3. Benchmark validation
4. Production deployment

---

## Documentation

### Design Documents
- Encoder architecture specification
- Training pipeline documentation
- Integration guide

### Code Documentation
- Encoder API documentation
- Training script documentation
- Migration guide

### Results Documentation
- Benchmark results
- Performance metrics
- Accuracy measurements

---

**Status**: ⏳ Planning Phase  
**Next**: Review architecture, start data collection  
**Timeline**: 2-4 weeks

