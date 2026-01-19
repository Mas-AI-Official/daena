#!/bin/bash
# GCP Compute Engine Setup Script for Daena with TPU Support
# Creates a VM instance with TPU access

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
ZONE="${GCP_ZONE:-us-central1-a}"
INSTANCE_NAME="${INSTANCE_NAME:-daena-tpu-vm}"
MACHINE_TYPE="${MACHINE_TYPE:-n1-standard-8}"
DISK_SIZE="${DISK_SIZE:-100GB}"
IMAGE_FAMILY="${IMAGE_FAMILY:-ubuntu-2204-lts}"
IMAGE_PROJECT="${IMAGE_PROJECT:-ubuntu-os-cloud}"

# TPU Configuration
TPU_NAME="${TPU_NAME:-daena-tpu}"
TPU_ZONE="${TPU_ZONE:-us-central1-a}"
TPU_TYPE="${TPU_TYPE:-v4-8}"  # TPU v4 Pod (8 chips)
TPU_VERSION="${TPU_VERSION:-tpu-vm-v4-base}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Daena GCP TPU Setup"
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
gcloud services enable tpu.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com

# Create TPU node
echo "🔷 Creating TPU node: $TPU_NAME"
gcloud compute tpus tpu-vm create "$TPU_NAME" \
  --zone="$TPU_ZONE" \
  --accelerator-type="$TPU_TYPE" \
  --version="$TPU_VERSION" \
  --network="default" \
  --preemptible || echo "⚠️ TPU may already exist or quota exceeded"

# Create VM instance
echo "🖥️ Creating VM instance: $INSTANCE_NAME"
gcloud compute instances create "$INSTANCE_NAME" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --boot-disk-size="$DISK_SIZE" \
  --image-family="$IMAGE_FAMILY" \
  --image-project="$IMAGE_PROJECT" \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --metadata="startup-script=# Daena Startup Script
#!/bin/bash
apt-get update
apt-get install -y python3 python3-pip git

# Clone Daena repository
git clone https://github.com/YOUR_ORG/daena.git /opt/daena
cd /opt/daena

# Install dependencies
pip3 install -r requirements.txt

# Install JAX for TPU support
pip3 install jax[tpu] -f https://storage.googleapis.com/jax-releases/libtpu_releases.html

# Set environment variables
echo 'export COMPUTE_PREFER=tpu' >> /etc/environment
echo 'export COMPUTE_ALLOW_TPU=true' >> /etc/environment
echo 'export COMPUTE_TPU_BATCH_FACTOR=128' >> /etc/environment
echo 'export TPU_NAME=$TPU_NAME' >> /etc/environment

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
echo "  2. Connect to TPU:"
echo "     export TPU_NAME=$TPU_NAME"
echo "     export TPU_ZONE=$TPU_ZONE"
echo ""
echo "  3. Start Daena:"
echo "     cd /opt/daena"
echo "     python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "  4. Verify TPU access:"
echo "     python3 Tools/daena_device_report.py"
echo ""

