#!/bin/bash
# GCP Compute Engine Setup Script for Daena with GPU Support
# Creates a VM instance with GPU accelerators

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
ZONE="${GCP_ZONE:-us-central1-a}"
INSTANCE_NAME="${INSTANCE_NAME:-daena-gpu-vm}"
MACHINE_TYPE="${MACHINE_TYPE:-n1-standard-8}"
DISK_SIZE="${DISK_SIZE:-100GB}"
GPU_TYPE="${GPU_TYPE:-nvidia-tesla-t4}"
GPU_COUNT="${GPU_COUNT:-1}"
IMAGE_FAMILY="${IMAGE_FAMILY:-ubuntu-2204-lts-gpu}"
IMAGE_PROJECT="${IMAGE_PROJECT:-ubuntu-os-cloud-gpu}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Daena GCP GPU Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Google Cloud SDK not found. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Set project
echo "📋 Setting GCP project to: $PROJECT_ID"
gcloud config set project "$PROJECT_ID"
gcloud config set compute/zone "$ZONE"

# Enable required APIs
echo "🔧 Enabling required GCP APIs..."
gcloud services enable compute.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com

# Create VM instance with GPU
echo "🖥️ Creating VM instance with GPU: $INSTANCE_NAME"
gcloud compute instances create "$INSTANCE_NAME" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --accelerator="type=$GPU_TYPE,count=$GPU_COUNT" \
  --maintenance-policy=TERMINATE \
  --boot-disk-size="$DISK_SIZE" \
  --image-family="$IMAGE_FAMILY" \
  --image-project="$IMAGE_PROJECT" \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --metadata="install-nvidia-driver=True" \
  --metadata="startup-script=# Daena Startup Script
#!/bin/bash
apt-get update
apt-get install -y python3 python3-pip git

# Install NVIDIA drivers (if not pre-installed)
if ! command -v nvidia-smi &> /dev/null; then
    curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/3bf863cc.pub | apt-key add -
    echo \"deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64 /\" > /etc/apt/sources.list.d/cuda.list
    apt-get update
    apt-get install -y cuda-toolkit-12-0
fi

# Clone Daena repository
git clone https://github.com/YOUR_ORG/daena.git /opt/daena
cd /opt/daena

# Install dependencies
pip3 install -r requirements.txt

# Install PyTorch with CUDA support
pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Set environment variables
echo 'export COMPUTE_PREFER=gpu' >> /etc/environment
echo 'export COMPUTE_ALLOW_TPU=false' >> /etc/environment
echo 'export CUDA_VISIBLE_DEVICES=0' >> /etc/environment

# Start Daena service
systemctl enable daena.service
systemctl start daena.service
" || echo "⚠️ VM may already exist"

# Create firewall rule for Daena (if needed)
echo "🔥 Configuring firewall rules..."
gcloud compute firewall-rules create allow-daena-http \
  --allow tcp:8000 \
  --source-ranges 0.0.0.0/0 \
  --description "Allow HTTP access to Daena" \
  || echo "⚠️ Firewall rule may already exist"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Next Steps:"
echo "  1. SSH into the VM:"
echo "     gcloud compute ssh $INSTANCE_NAME --zone=$ZONE"
echo ""
echo "  2. Verify GPU access:"
echo "     nvidia-smi"
echo "     python3 Tools/daena_device_report.py"
echo ""
echo "  3. Start Daena:"
echo "     cd /opt/daena"
echo "     python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
echo ""

