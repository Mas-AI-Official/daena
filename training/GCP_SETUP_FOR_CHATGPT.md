# 🚀 GCP SETUP FOR DAENA BRAIN TRAINING

## 📋 Complete Setup Instructions for ChatGPT

**Please help me set up Google Cloud Platform for AI model training with the following specifications:**

---

## 🎯 PROJECT DETAILS

### **Project Information:**
- **Project ID:** `daena-467315`
- **Organization:** `mas-ai.co`
- **Region:** `us-central1`
- **Zone:** `us-central1-a`
- **Owner Email:** `masoud.masoori@mas-ai.co`

### **Available GPU Quotas (APPROVED):**
| GPU Type | Region | Quantity | VRAM | Cost/Hour | Status |
|----------|--------|----------|------|-----------|---------|
| **Preemptible A100 80GB** | us-central1 | 4 | 320GB total | $2-4 | ✅ **RECOMMENDED** |
| Preemptible A100 80GB | us-east1 | 2 | 160GB total | $2-4 | ✅ Approved |
| Preemptible A100 80GB | us-east4 | 2 | 160GB total | $2-4 | ✅ Approved |
| Preemptible A100 80GB | us-east5 | 2 | 160GB total | $2-4 | ✅ Approved |
| Preemptible A100 | us-east1 | 2 | 80GB total | $1-2 | ✅ Approved |
| Preemptible T4 GPUs | us-east1 | 2 | 32GB total | $0.5-1 | ✅ Approved |

---

## 🏆 RECOMMENDED CONFIGURATION

### **Primary Setup (Best for Daena Brain):**
```
Region: us-central1
GPU: 4x NVIDIA A100 80GB (Preemptible)
Machine Type: n1-standard-16 (16 vCPU, 60GB RAM)
Storage: 500GB SSD
Budget: $409.34 credits available
```

---

## 🔧 REQUIRED SETUP STEPS

### **Step 1: GCP Project Configuration**
```bash
# Set project
gcloud config set project daena-467315

# Set region
gcloud config set compute/region us-central1
gcloud config set compute/zone us-central1-a
```

### **Step 2: Enable Required APIs**
```bash
# Enable Compute Engine API
gcloud services enable compute.googleapis.com

# Enable Cloud Storage API
gcloud services enable storage.googleapis.com

# Enable Vertex AI API
gcloud services enable aiplatform.googleapis.com

# Enable ML API
gcloud services enable ml.googleapis.com

# Enable Cloud Build API
gcloud services enable cloudbuild.googleapis.com

# Enable Container Registry API
gcloud services enable containerregistry.googleapis.com
```

### **Step 3: Create Cloud Storage Bucket**
```bash
# Create storage bucket for models
gsutil mb -l us-central1 gs://daena-brain-daena-467315

# Set bucket permissions
gsutil iam ch allUsers:objectViewer gs://daena-brain-daena-467315
```

### **Step 4: Create Compute Engine Instance**
```bash
# Create VM with A100 80GB GPUs
gcloud compute instances create daena-brain-vm \
  --zone=us-central1-a \
  --machine-type=n1-standard-16 \
  --maintenance-policy=TERMINATE \
  --accelerator="type=nvidia-tesla-a100,count=4" \
  --image-family=debian-11-gpu \
  --image-project=debian-cloud \
  --boot-disk-size=500GB \
  --boot-disk-type=pd-ssd \
  --metadata="install-nvidia-driver=True" \
  --preemptible
```

### **Step 5: Install Python Environment**
```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Python 3.9+
sudo apt-get install python3.9 python3.9-pip python3.9-venv -y

# Create virtual environment
python3.9 -m venv daena_env
source daena_env/bin/activate

# Install CUDA 11.8
wget https://developer.download.nvidia.com/compute/cuda/11.8.0/local_installers/cuda_11.8.0_520.61.05_linux.run
sudo sh cuda_11.8.0_520.61.05_linux.run --silent --driver --toolkit --samples

# Install PyTorch with CUDA support
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# Install required packages
pip install transformers datasets accelerate bitsandbytes
pip install wandb huggingface_hub
pip install azure-storage-blob azure-identity
pip install python-dotenv requests
```

### **Step 6: Configure Environment Variables**
```bash
# Create .env file
cat > .env << EOF
# Daena Brain Configuration
DAENA_OWNER_NAME=Masoud
DAENA_OWNER_EMAIL=masoud.masoori@mas-ai.co

# HuggingFace Configuration
HUGGINGFACE_TOKEN=your_huggingface_token_here

# GCP Configuration
GCP_PROJECT_ID=daena-467315
GCP_REGION=us-central1
GCP_ZONE=us-central1-a

# Azure OpenAI (for inference)
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
AZURE_OPENAI_ENDPOINT=your_azure_endpoint_here

# WandB Configuration
WANDB_API_KEY=5e14c63c944ad1ce8b0b601820a9514172854639

# Storage Configuration
HF_HOME=/home/daena/hf_cache
TORCH_HOME=/home/daena/torch_cache
EOF
```

### **Step 7: Setup Storage Directories**
```bash
# Create directories
mkdir -p /home/daena/DaenaBrain/{trained_models,temp,logs,checkpoints}
mkdir -p /home/daena/hf_cache
mkdir -p /home/daena/torch_cache

# Set permissions
chmod 755 /home/daena/DaenaBrain
```

---

## 🧠 DAENA BRAIN TRAINING MODELS

### **Target Models (9 Total):**
1. **DeepSeek R1 67B** - Reasoning & Decision Making
2. **Qwen 2.5 72B** - Advanced Reasoning
3. **DeepSeek Coder 67B** - Coding & Development
4. **Code Llama 70B** - Comprehensive Coding
5. **Qwen 2.5 VL 72B** - Vision & Image Processing
6. **Whisper Large V3** - Speech Recognition
7. **Bark** - Voice Synthesis
8. **Stable Video Diffusion** - Video Generation
9. **WizardMath 70B** - Mathematics & Calculation

### **Total Storage Required:** ~400GB
### **Estimated Cost:** $180-360 (within $409 budget)

---

## 🚀 LAUNCH COMMANDS

### **Start Training:**
```bash
# Navigate to training directory
cd /home/daena/DaenaBrain/training

# Activate environment
source daena_env/bin/activate

# Launch GCP training
python launch_gcp_training.py
```

### **Monitor Training:**
```bash
# Check GPU usage
nvidia-smi

# Monitor logs
tail -f /home/daena/DaenaBrain/logs/gcp_training_*.log

# Check WandB dashboard
wandb login
```

---

## 📊 EXPECTED RESULTS

### **Training Timeline:**
- **Setup:** 30 minutes
- **Model Training:** 2-4 hours per model
- **Total Time:** 18-36 hours for all 9 models
- **Cost:** $180-360 (well within $409 budget)

### **Final Output:**
- **Local Storage:** `/home/daena/DaenaBrain/trained_models/`
- **GCP Storage:** `gs://daena-brain-daena-467315/trained_models/`
- **WandB Dashboard:** Training progress and metrics

---

## 🔍 TROUBLESHOOTING

### **Common Issues:**
1. **GPU not detected:** Install NVIDIA drivers
2. **Out of memory:** Reduce batch size
3. **API limits:** Use preemptible instances
4. **Storage full:** Clean up temp files

### **Useful Commands:**
```bash
# Check GPU status
nvidia-smi

# Check disk space
df -h

# Check memory usage
free -h

# Restart training from checkpoint
python gcp_trainer.py --resume
```

---

## 💰 COST OPTIMIZATION

### **Preemptible Instances:**
- **60-70% cheaper** than regular instances
- **Interruptible** but perfect for training
- **Auto-restart** capability

### **Storage Strategy:**
- **Local training** on SSD
- **GCP backup** for unlimited storage
- **Cleanup** after successful training

---

## 🎯 SUCCESS METRICS

### **Training Success:**
- ✅ All 9 models trained successfully
- ✅ Models saved locally and to GCP
- ✅ WandB tracking active
- ✅ Total cost under $409
- ✅ Daena brain ready for inference

### **Performance Targets:**
- **Training Speed:** 2-4 hours per model
- **Memory Usage:** Under 320GB VRAM
- **Cost Efficiency:** Under $40 per model
- **Reliability:** 95%+ success rate

---

**Please help me execute these setup steps and ensure everything is configured correctly for optimal Daena brain training! 🧠⚡** 