#!/bin/bash
# GCP GKE Cluster Setup Script for Daena with GPU Support
# Creates a GKE cluster with GPU nodes

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
ZONE="${GCP_ZONE:-us-central1-a}"
CLUSTER_NAME="${CLUSTER_NAME:-daena-gpu-cluster}"
MACHINE_TYPE="${MACHINE_TYPE:-n1-standard-4}"
NODE_COUNT="${NODE_COUNT:-3}"
GPU_TYPE="${GPU_TYPE:-nvidia-tesla-t4}"
GPU_COUNT="${GPU_COUNT:-1}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Daena GKE GPU Cluster Setup"
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
gcloud config set compute/region "$REGION"
gcloud config set compute/zone "$ZONE"

# Enable required APIs
echo "🔧 Enabling required GCP APIs..."
gcloud services enable container.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable aiplatform.googleapis.com

# Create GKE cluster
echo "🏗️ Creating GKE cluster: $CLUSTER_NAME"
gcloud container clusters create "$CLUSTER_NAME" \
  --zone="$ZONE" \
  --machine-type="$MACHINE_TYPE" \
  --num-nodes="$NODE_COUNT" \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=10 \
  --enable-autorepair \
  --enable-autoupgrade \
  --addons=HorizontalPodAutoscaling,HttpLoadBalancing \
  || echo "⚠️ Cluster may already exist"

# Get cluster credentials
echo "🔐 Getting cluster credentials..."
gcloud container clusters get-credentials "$CLUSTER_NAME" --zone="$ZONE"

# Install NVIDIA device plugin
echo "🔧 Installing NVIDIA device plugin..."
kubectl apply -f https://raw.githubusercontent.com/GoogleCloudPlatform/container-engine-accelerators/master/nvidia-driver-installer/cos/daemonset-preloaded.yaml

# Create GPU node pool
echo "🎮 Creating GPU node pool..."
gcloud container node-pools create gpu-pool \
  --cluster="$CLUSTER_NAME" \
  --zone="$ZONE" \
  --machine-type="n1-standard-8" \
  --accelerator="type=$GPU_TYPE,count=$GPU_COUNT" \
  --num-nodes=1 \
  --enable-autoscaling \
  --min-nodes=0 \
  --max-nodes=3 \
  --enable-autorepair \
  --enable-autoupgrade \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  --disk-size=100GB \
  || echo "⚠️ GPU node pool may already exist or quota exceeded"

# Create ConfigMap for Daena configuration
echo "📝 Creating ConfigMap..."
kubectl create configmap daena-config \
  --from-literal=gcp-project-id="$PROJECT_ID" \
  --from-literal=compute-prefer=gpu \
  --from-literal=compute-allow-tpu=false \
  --dry-run=client -o yaml | kubectl apply -f -

# Create Secrets placeholder (user must fill in actual values)
echo "🔒 Creating Secrets placeholder..."
kubectl create secret generic daena-secrets \
  --from-literal=aes-key="CHANGE_ME_IN_PRODUCTION" \
  --dry-run=client -o yaml | kubectl apply -f - || echo "⚠️ Secret may already exist"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Cluster Setup Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📋 Next Steps:"
echo "  1. Update Secrets with actual values:"
echo "     kubectl edit secret daena-secrets"
echo ""
echo "  2. Deploy Daena:"
echo "     kubectl apply -f deploy/gcp/gke-gpu-deployment.yaml"
echo ""
echo "  3. Check deployment status:"
echo "     kubectl get pods -l accelerator=gpu"
echo "     kubectl logs -l accelerator=gpu"
echo ""
echo "  4. Access Daena service:"
echo "     kubectl get service daena-gpu-service"
echo ""

