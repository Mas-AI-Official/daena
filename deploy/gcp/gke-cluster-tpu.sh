#!/bin/bash
# GCP GKE Cluster Setup Script for Daena with TPU Support
# Creates a GKE cluster with TPU nodes

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
REGION="${GCP_REGION:-us-central1}"
ZONE="${GCP_ZONE:-us-central1-a}"
CLUSTER_NAME="${CLUSTER_NAME:-daena-tpu-cluster}"
MACHINE_TYPE="${MACHINE_TYPE:-n1-standard-4}"
NODE_COUNT="${NODE_COUNT:-3}"
TPU_NODE_COUNT="${TPU_NODE_COUNT:-1}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Daena GKE TPU Cluster Setup"
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
gcloud services enable tpu.googleapis.com
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

# Create TPU node pool
echo "🔷 Creating TPU node pool..."
gcloud container node-pools create tpu-pool \
  --cluster="$CLUSTER_NAME" \
  --zone="$ZONE" \
  --machine-type="ct4p-hightpu-4t" \
  --num-nodes="$TPU_NODE_COUNT" \
  --enable-autoscaling \
  --min-nodes=0 \
  --max-nodes=2 \
  --enable-autorepair \
  --enable-autoupgrade \
  --scopes=https://www.googleapis.com/auth/cloud-platform \
  || echo "⚠️ TPU node pool may already exist or quota exceeded"

# Create ConfigMap for Daena configuration
echo "📝 Creating ConfigMap..."
kubectl create configmap daena-config \
  --from-literal=gcp-project-id="$PROJECT_ID" \
  --from-literal=compute-prefer=tpu \
  --from-literal=compute-allow-tpu=true \
  --from-literal=compute-tpu-batch-factor=128 \
  --from-literal=tpu-name=daena-tpu \
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
echo "     kubectl apply -f deploy/gcp/gke-tpu-deployment.yaml"
echo ""
echo "  3. Check deployment status:"
echo "     kubectl get pods -l accelerator=tpu"
echo "     kubectl logs -l accelerator=tpu"
echo ""
echo "  4. Access Daena service:"
echo "     kubectl get service daena-tpu-service"
echo ""

