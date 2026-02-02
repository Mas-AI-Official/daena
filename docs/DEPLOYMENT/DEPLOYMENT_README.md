# Daena AI VP - Complete Deployment Guide

## 🚀 Quick Launch

### Windows
```bash
# Double-click or run:
LAUNCH_DAENA_COMPLETE.bat
```

### Linux/Mac
```bash
chmod +x launch.sh
./launch.sh
```

### Docker
```bash
docker-compose up -d
```

---

## 📋 Prerequisites

### Required
- Python 3.9+ (3.10 recommended)
- pip
- Git

### Optional (for full features)
- **GPU Support**: NVIDIA GPU with CUDA drivers
- **TPU Support**: JAX installed (`pip install jax jaxlib`)
- **Voice Support**: Audio drivers

---

## 🔧 Installation Steps

### 1. Clone Repository
```bash
git clone <your-private-repo-url> daena
cd daena
```

### 2. Environment Setup

**Windows:**
```bash
# Run the launcher - it will set up everything automatically
LAUNCH_DAENA_COMPLETE.bat
```

**Manual Setup:**
```bash
# Create virtual environment
python -m venv venv_daena_main_py310

# Activate (Windows)
venv_daena_main_py310\Scripts\activate

# Activate (Linux/Mac)
source venv_daena_main_py310/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

**Environment Variables:**
```bash
# Create .env file or set environment variables
COMPUTE_PREFER=auto          # auto, cpu, gpu, tpu
COMPUTE_ALLOW_TPU=true       # Enable TPU support
COMPUTE_TPU_BATCH_FACTOR=128 # TPU batch multiplier

# API Keys (required)
OPENAI_API_KEY=your-key-here
# OR
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_API_BASE=your-endpoint
AZURE_OPENAI_DEPLOYMENT_ID=your-deployment
```

**Configuration Files:**
- `config/production.env` - Production settings
- `.env_azure_openai` - Azure OpenAI config
- `.env` - Local overrides

### 4. Verify Installation

**Check Device Support:**
```bash
python Tools/daena_device_report.py
```

**Expected Output:**
- ✅ CPU detected
- ✅ GPU detected (if available)
- ✅ TPU detected (if JAX installed)

---

## 🐳 Docker Deployment

### Build and Run
```bash
# Build image
docker build -t daena-ai .

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f app
```

### Environment Variables in Docker
```bash
# Set in docker-compose.yml or .env file
COMPUTE_PREFER=auto
COMPUTE_ALLOW_TPU=true
COMPUTE_TPU_BATCH_FACTOR=128
```

### Access Services
- **Backend**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000
- **Prometheus**: http://localhost:9090

---

## ☁️ Cloud Deployment

### Google Cloud Platform (GCP)

**With TPU Support:**
```bash
# Set TPU environment variables
export TPU_NAME=your-tpu-name
export TPU_ZONE=us-central1-a

# Set compute preferences
export COMPUTE_PREFER=tpu
export COMPUTE_ALLOW_TPU=true

# Deploy
gcloud compute instances create daena-instance \
    --machine-type=n1-standard-4 \
    --accelerator=type=nvidia-tesla-t4,count=1 \
    --image-family=ubuntu-2004-lts \
    --image-project=ubuntu-os-cloud
```

### AWS

**EC2 with GPU:**
```bash
# Use GPU instance (g4dn.xlarge or larger)
# Install NVIDIA drivers and CUDA
# Set environment variables
export COMPUTE_PREFER=gpu
```

### Azure

**VM with GPU:**
```bash
# Use NC-series VM for GPU support
# Install NVIDIA drivers
# Configure Azure OpenAI endpoint
export AZURE_OPENAI_API_KEY=your-key
export AZURE_OPENAI_API_BASE=your-endpoint
```

---

## 🔍 Verification

### 1. Health Check
```bash
curl http://localhost:8000/api/v1/system/health
```

### 2. Device Report
```bash
python Tools/daena_device_report.py --verbose
```

### 3. System Summary
```bash
curl http://localhost:8000/api/v1/system/summary
```

### 4. Test Endpoints
- Health: `GET /api/v1/system/health`
- Summary: `GET /api/v1/system/summary`
- Device Info: `GET /api/v1/system/device-info` (if implemented)

---

## 🛠️ Troubleshooting

### Issue: Server won't start
**Solution:**
1. Check Python version: `python --version` (should be 3.9+)
2. Verify virtual environment is activated
3. Check port 8000 is not in use: `netstat -an | findstr 8000`
4. Review logs in `logs/` directory

### Issue: GPU not detected
**Solution:**
1. Install NVIDIA drivers
2. Install PyTorch with CUDA: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`
3. Verify: `python -c "import torch; print(torch.cuda.is_available())"`

### Issue: TPU not detected
**Solution:**
1. Install JAX: `pip install jax jaxlib`
2. For Cloud TPU, set environment variables:
   - `TPU_NAME=your-tpu-name`
   - `TPU_ZONE=us-central1-a`
3. Verify: `python Tools/daena_device_report.py`

### Issue: Voice service not working
**Solution:**
1. Check audio drivers are installed
2. Verify voice environment: `venv_daena_voice_py310`
3. Check voice file exists: `Voice/daena_voice.wav`
4. Review voice service logs

### Issue: Import errors
**Solution:**
1. Reinstall requirements: `pip install -r requirements.txt --upgrade`
2. Verify PYTHONPATH includes project root
3. Check virtual environment is activated

---

## 📊 Performance Optimization

### TPU Configuration
```bash
# For large batch inference
export COMPUTE_PREFER=tpu
export COMPUTE_TPU_BATCH_FACTOR=256  # Increase for larger batches
```

### GPU Configuration
```bash
# For general ML workloads
export COMPUTE_PREFER=gpu
```

### CPU Configuration
```bash
# For small workloads or development
export COMPUTE_PREFER=cpu
```

---

## 🔐 Security

### Production Checklist
- [ ] Change default API keys
- [ ] Set secure passwords
- [ ] Enable HTTPS/TLS
- [ ] Configure firewall rules
- [ ] Set up monitoring and alerts
- [ ] Regular backups
- [ ] Update dependencies regularly

### Environment Variables
Never commit:
- API keys
- Passwords
- Private keys
- Database credentials

Use `.env` files (in `.gitignore`) or secure secret management.

---

## 📚 Additional Resources

- **Device Manager Docs**: `docs/TPU_GPU_IMPLEMENTATION_SUMMARY.md`
- **Architecture**: `docs/ARCHITECTURE_GROUND_TRUTH.md`
- **NBMF System**: `docs/NBMF_MEMORY_PATENT_MATERIAL.md`
- **API Documentation**: http://localhost:8000/docs

---

## 🆘 Support

For issues:
1. Check logs: `logs/` directory
2. Run diagnostics: `python Tools/daena_device_report.py`
3. Review documentation: `docs/` directory
4. Check GitHub issues (if public repo)

---

## ✅ Launch Checklist

Before launching:
- [ ] Python 3.9+ installed
- [ ] Virtual environment created
- [ ] Requirements installed
- [ ] Environment variables configured
- [ ] API keys set
- [ ] Device support verified
- [ ] Health check passes
- [ ] All services running

---

**Last Updated**: 2025-01-XX  
**Version**: 2.0.0 with TPU/GPU Support


