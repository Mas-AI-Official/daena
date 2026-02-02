# 🧠 Daena Ultimate Unified Brain V3.0

**The Most Advanced AI Brain Ever Created | All Best Models Integrated | API-First with Azure GPU Fallback**

## 🎯 Overview

The **Daena Ultimate Unified Brain V3.0** is the most advanced AI brain ever created, combining ALL the best open source models into one unified system. This brain includes R1, R2, V3 reasoning models, DeepSeek, Llama, Yi, Qwen, and many more, with an API-first approach and Azure GPU training capabilities.

## 🚀 Key Features

### 🧠 **Complete Model Integration**
- **R1, R2, V3 Reasoning Models**: Microsoft Phi-2, DialoGPT, Phi-3-mini-4k
- **Coding Models**: DeepSeek Coder 33B/6.7B, CodeLlama 34B, Wizard Coder 15B
- **Creative Models**: Mistral 7B, Qwen 2.5 7B, Llama 2 7B
- **Mathematics Models**: Qwen 2.5 Math 7B, Phi 3 Mini
- **General Models**: Yi 34B, Llama 2 70B, Gemma 2 27B
- **Specialized Models**: InternLM 2.5 20B, DeepSeek MoE 16B, Qwen 2.5 MoE

### 🌐 **API-First Approach**
- **Azure OpenAI Integration**: GPT-4 for advanced reasoning
- **Gemini Integration**: Multimodal understanding
- **Claude Integration**: Detailed analysis and ethical reasoning
- **HuggingFace API**: Direct model access when possible

### 🚀 **Azure GPU Training**
- **Automatic GPU Detection**: Uses Azure GPU VMs when available
- **Local Fallback**: Trains locally if Azure GPU unavailable
- **Space Management**: Downloads models one-by-one, trains, then deletes
- **Efficient Processing**: Optimized for minimal disk usage

### 💾 **Smart Brain Management**
- **Automatic Backups**: Always keeps brain backups
- **Model Prioritization**: Trains critical models first
- **Progress Monitoring**: Real-time training status
- **Error Recovery**: Handles failures gracefully

## 📋 Prerequisites

### 🔧 **System Requirements**
- **Python 3.10+**
- **16GB+ RAM** (32GB+ recommended)
- **100GB+ Free Disk Space**
- **CUDA-compatible GPU** (optional, for local training)

### 🌐 **API Keys Required**
```bash
# Required in .env_azure_openai
HUGGINGFACE_TOKEN=your_hf_token
AZURE_OPENAI_API_KEY=your_azure_key
AZURE_OPENAI_API_BASE=your_azure_endpoint
AZURE_OPENAI_DEPLOYMENT_ID=your_deployment

# Optional (for enhanced capabilities)
GEMINI_API_KEY=your_gemini_key
CLAUDE_API_KEY=your_claude_key
```

### 🚀 **Azure GPU Setup** (Optional)
```bash
# Azure GPU VM Configuration
AZURE_SUBSCRIPTION_ID=your_subscription
AZURE_TENANT_ID=your_tenant
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret
AZURE_RESOURCE_GROUP=daena-ultimate-gpu-rg
AZURE_GPU_VM_NAME=daena-ultimate-gpu-vm
AZURE_GPU_VM_SIZE=Standard_NC24rs_v3
```

## 🚀 Quick Start

### 1. **Installation**
```bash
# Clone the repository
git clone <repository-url>
cd Daena

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env_azure_openai.example .env_azure_openai
# Edit .env_azure_openai with your API keys
```

### 2. **Launch Unified Brain Training**
```bash
# Windows
run_unified_brain.bat

# Linux/Mac
python launch_unified_brain.py
```

### 3. **Select Training Option**
```
🎯 ULTIMATE UNIFIED BRAIN MENU
==================================================
1. 🧠 Train Ultimate Unified Brain (All Models)
2. 🌐 Test API Connections (Azure, Gemini, Claude)
3. 💾 Check Disk Space & Brain Status
4. 🧠 Daena Brain Management & Monitoring
5. 📊 View Ultimate Model Collection
6. 🚀 Azure GPU Status & Configuration
7. ❌ Exit
```

## 📊 Model Collection

### 🧠 **Critical Models (Priority 1-3)**
| Model | Type | Size | Description |
|-------|------|------|-------------|
| `r1_reasoning` | Reasoning | 2.7GB | R1 Advanced reasoning and logical thinking |
| `r2_analysis` | Reasoning | 1.5GB | R2 Deep analysis and strategic thinking |
| `r3_v3` | Reasoning | 3.8GB | R3 V3 Advanced reasoning and instruction following |

### 💻 **High Priority Models (Priority 4-7)**
| Model | Type | Size | Description |
|-------|------|------|-------------|
| `deepseek_coder_33b` | Coding | 66GB | DeepSeek Coder 33B - Advanced coding |
| `deepseek_coder_6b` | Coding | 13GB | DeepSeek Coder 6.7B - Efficient coding |
| `wizard_coder` | Coding | 30GB | Wizard Coder - Wizard-level coding |
| `codellama` | Coding | 68GB | Code Llama 34B - Comprehensive coding |

### 🎨 **Medium Priority Models (Priority 8-12)**
| Model | Type | Size | Description |
|-------|------|------|-------------|
| `mistral_creative` | Creative | 14GB | Mistral 7B - Creative content generation |
| `qwen_creative` | Creative | 14GB | Qwen 2.5 7B - Advanced creative writing |
| `llama_creative` | Creative | 14GB | Llama 2 7B - Creative and conversational |
| `qwen_math` | Mathematics | 14GB | Qwen 2.5 Math - Advanced mathematics |
| `phi_math` | Mathematics | 3.8GB | Phi 3 Mini - Mathematical analysis |

### 🌍 **General Models (Priority 13-15)**
| Model | Type | Size | Description |
|-------|------|------|-------------|
| `yi_34b` | General | 68GB | Yi 34B - Comprehensive general knowledge |
| `llama_70b` | General | 140GB | Llama 2 70B - Large-scale understanding |
| `gemma_27b` | General | 54GB | Gemma 2 27B - Google's advanced model |

### 🎯 **Specialized Models (Priority 16-18)**
| Model | Type | Size | Description |
|-------|------|------|-------------|
| `internlm_20b` | Specialized | 40GB | InternLM 2.5 20B - Specialized expertise |
| `deepseek_moe` | Specialized | 32GB | DeepSeek MoE 16B - Mixture of experts |
| `qwen_moe` | Specialized | 5.4GB | Qwen 2.5 MoE - Efficient specialization |

## 🔧 Advanced Configuration

### 🧠 **Custom Model Configuration**
Edit `unified_brain.py` to modify model configurations:

```python
self.ultimate_models = {
    'custom_model': {
        'name': 'your/model/name',
        'type': 'reasoning',  # reasoning, coding, creative, mathematics, general, specialized
        'category': 'critical',  # critical, high, medium, low
        'weight': 2.0,
        'priority': 1,
        'size_gb': 10.0,
        'api_available': False,
        'description': 'Your custom model description',
        'capabilities': ['capability1', 'capability2']
    }
}
```

### 🌐 **API Configuration**
Configure big model APIs in the trainer:

```python
self.big_model_apis = {
    'custom_api': {
        'client': your_client,
        'model': 'your_model_name',
        'capabilities': ['capability1', 'capability2'],
        'weight': 1.5
    }
}
```

### 🚀 **Azure GPU Configuration**
Set up Azure GPU VM for training:

```bash
# Create Azure GPU VM
az vm create \
  --resource-group daena-ultimate-gpu-rg \
  --name daena-ultimate-gpu-vm \
  --image Ubuntu2204 \
  --size Standard_NC24rs_v3 \
  --admin-username azureuser \
  --generate-ssh-keys

# Install CUDA and PyTorch
ssh azureuser@your-vm-ip
sudo apt update
sudo apt install nvidia-cuda-toolkit
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

## 📈 Training Process

### 🔄 **Training Flow**
1. **API-First Training**: Attempts to generate training data using big model APIs
2. **Local Model Training**: Downloads model if API training fails
3. **Azure GPU Training**: Uses Azure GPU VM if available
4. **Local GPU/CPU Training**: Falls back to local training
5. **Model Cleanup**: Removes downloaded models to save space
6. **Brain Integration**: Integrates trained models into unified brain

### 📊 **Training Progress**
```
🧠 Training r1_reasoning (R1 Advanced reasoning and logical thinking)
   📥 Downloading microsoft/phi-2...
   ✅ Model downloaded successfully
   🎯 Generating training data with APIs...
   ✅ Generated 50 training examples
   🚀 Training on local GPU...
   ✅ Training completed successfully
   🧹 Cleaning up temporary files...
   ✅ Model integrated into unified brain
```

### 💾 **Space Management**
- **One-by-One Processing**: Downloads and trains one model at a time
- **Automatic Cleanup**: Removes downloaded models after training
- **Backup System**: Always keeps brain backups
- **Disk Monitoring**: Checks available space before downloads

## 🧠 Brain Management

### 📊 **Brain Statistics**
```bash
# View brain statistics
python launch_unified_brain.py
# Select option 4 -> 1
```

### 🔄 **Backup and Restore**
```bash
# Create backup
python launch_unified_brain.py
# Select option 4 -> 2

# Restore from backup
python launch_unified_brain.py
# Select option 4 -> 5
```

### 🧹 **Cleanup Operations**
```bash
# Cleanup temporary files
python launch_unified_brain.py
# Select option 4 -> 4
```

## 🚀 Azure GPU Integration

### 🔧 **Azure Setup**
1. **Create Resource Group**:
   ```bash
   az group create --name daena-ultimate-gpu-rg --location eastus2
   ```

2. **Create GPU VM**:
   ```bash
   az vm create \
     --resource-group daena-ultimate-gpu-rg \
     --name daena-ultimate-gpu-vm \
     --image Ubuntu2204 \
     --size Standard_NC24rs_v3 \
     --admin-username azureuser \
     --generate-ssh-keys
   ```

3. **Install Dependencies**:
   ```bash
   ssh azureuser@your-vm-ip
   sudo apt update
   sudo apt install python3-pip nvidia-cuda-toolkit
   pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

### 🎯 **GPU Training Benefits**
- **Faster Training**: 10-50x faster than CPU
- **Larger Models**: Can train models up to 70B parameters
- **Better Quality**: Higher quality training with more epochs
- **Cost Effective**: Pay only for GPU usage time

## 🔍 Troubleshooting

### ❌ **Common Issues**

#### **API Connection Failures**
```bash
# Test API connections
python launch_unified_brain.py
# Select option 2
```

#### **Disk Space Issues**
```bash
# Check disk space
python launch_unified_brain.py
# Select option 3
```

#### **GPU Not Available**
```bash
# Check GPU status
python launch_unified_brain.py
# Select option 6
```

#### **Model Download Failures**
```bash
# Check HuggingFace token
python test_hf_token.py
```

### 🔧 **Solutions**

#### **Increase Disk Space**
- Clean up temporary files
- Remove old backups
- Use external storage

#### **Fix API Issues**
- Verify API keys in `.env_azure_openai`
- Check API quotas and limits
- Test network connectivity

#### **GPU Issues**
- Install CUDA drivers
- Update PyTorch with CUDA support
- Check GPU memory availability

## 📈 Performance Optimization

### 🚀 **Training Optimization**
- **Gradient Accumulation**: Reduces memory usage
- **Mixed Precision**: Faster training with less memory
- **Model Sharding**: Distributes large models across GPUs
- **Dynamic Batching**: Optimizes batch sizes automatically

### 💾 **Memory Optimization**
- **Model Offloading**: Moves unused model parts to CPU
- **Gradient Checkpointing**: Trades compute for memory
- **Quantization**: Reduces model precision for memory savings

### 🌐 **API Optimization**
- **Request Batching**: Groups API requests
- **Caching**: Caches API responses
- **Rate Limiting**: Respects API rate limits
- **Fallback Chains**: Multiple API fallbacks

## 🎯 Future Enhancements

### 🔮 **Planned Features**
- **Auto Model Discovery**: Automatically finds new best models
- **Dynamic Model Selection**: Selects best model for each task
- **Federated Learning**: Distributed training across multiple nodes
- **Model Compression**: Compresses models for deployment
- **Real-time Updates**: Live model updates and improvements

### 🚀 **Scaling Plans**
- **Multi-GPU Training**: Train on multiple GPUs simultaneously
- **Distributed Training**: Train across multiple machines
- **Cloud Integration**: Native cloud platform integration
- **Edge Deployment**: Deploy to edge devices

## 📞 Support

### 🆘 **Getting Help**
- **Documentation**: Check this README and code comments
- **Logs**: Check `./logs/` directory for detailed logs
- **Issues**: Report issues with detailed error messages
- **Community**: Join the Daena community for support

### 📧 **Contact**
- **Email**: masoud.masori@gmail.com
- **GitHub**: Report issues on GitHub
- **Discord**: Join our Discord community

## 📄 License

This project is licensed under a commercial license. See LICENSE file for details.

---

**🎉 Congratulations! You now have the most advanced AI brain ever created!**

The Daena Ultimate Unified Brain V3.0 combines ALL the best open source models with API integration and Azure GPU training capabilities. This is the future of AI - a unified brain that can handle any task with the combined power of the world's best models. 