# GCP Deployment Guide for Daena

This directory contains deployment scripts and configurations for running Daena on Google Cloud Platform with CPU, GPU, and TPU support.

## 📋 Prerequisites

1. **Google Cloud SDK**: Install from [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)
2. **GCP Project**: Create a project at [https://console.cloud.google.com](https://console.cloud.google.com)
3. **Billing**: Enable billing for your GCP project
4. **APIs**: Enable required APIs (scripts will do this automatically)

## 🚀 Quick Start

### Option 1: Compute Engine (VM-based)

#### GPU Setup
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_ZONE="us-central1-a"
export GPU_TYPE="nvidia-tesla-t4"  # or nvidia-tesla-a100, nvidia-l4
export GPU_COUNT="1"

chmod +x deploy/gcp/compute-engine-gpu-setup.sh
./deploy/gcp/compute-engine-gpu-setup.sh
```

#### TPU Setup
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_ZONE="us-central1-a"
export TPU_NAME="daena-tpu"
export TPU_TYPE="v4-8"  # TPU v4 Pod (8 chips)

chmod +x deploy/gcp/compute-engine-tpu-setup.sh
./deploy/gcp/compute-engine-tpu-setup.sh
```

### Option 2: Google Kubernetes Engine (GKE)

#### GPU Cluster
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export GCP_ZONE="us-central1-a"
export GPU_TYPE="nvidia-tesla-t4"
export GPU_COUNT="1"

chmod +x deploy/gcp/gke-cluster-gpu.sh
./deploy/gcp/gke-cluster-gpu.sh

# Deploy Daena
kubectl apply -f deploy/gcp/gke-gpu-deployment.yaml
```

#### TPU Cluster
```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export GCP_ZONE="us-central1-a"

chmod +x deploy/gcp/gke-cluster-tpu.sh
./deploy/gcp/gke-cluster-tpu.sh

# Deploy Daena
kubectl apply -f deploy/gcp/gke-tpu-deployment.yaml
```

## ⚙️ Configuration

### Environment Variables

Set these environment variables before running setup scripts:

```bash
# Required
export GCP_PROJECT_ID="your-project-id"
export GCP_ZONE="us-central1-a"  # or your preferred zone

# Optional (for GPU)
export GPU_TYPE="nvidia-tesla-t4"  # or nvidia-tesla-a100, nvidia-l4
export GPU_COUNT="1"

# Optional (for TPU)
export TPU_NAME="daena-tpu"
export TPU_TYPE="v4-8"  # TPU v4 Pod (8 chips)
export TPU_ZONE="us-central1-a"

# Daena Configuration
export COMPUTE_PREFER="auto"  # auto, cpu, gpu, tpu
export COMPUTE_ALLOW_TPU="true"
export COMPUTE_TPU_BATCH_FACTOR="128"
export DAENA_MEMORY_AES_KEY="your-encryption-key"
```

### Device Selection

Daena automatically detects and uses available accelerators:

- **Auto**: Automatically selects best available device (TPU > GPU > CPU)
- **GPU**: Forces GPU usage, falls back to CPU if unavailable
- **TPU**: Forces TPU usage, falls back to GPU/CPU if unavailable
- **CPU**: Forces CPU usage only

## 📁 Files

- `compute-engine-gpu-setup.sh` - VM setup script for GPU
- `compute-engine-tpu-setup.sh` - VM setup script for TPU
- `gke-cluster-gpu.sh` - GKE cluster setup script for GPU
- `gke-cluster-tpu.sh` - GKE cluster setup script for TPU
- `gke-gpu-deployment.yaml` - Kubernetes deployment for GPU
- `gke-tpu-deployment.yaml` - Kubernetes deployment for TPU

## 🔧 Post-Deployment

### Verify Device Detection

```bash
# SSH into VM
gcloud compute ssh INSTANCE_NAME --zone=ZONE

# Run device report
python3 Tools/daena_device_report.py
```

Expected output:
```
Available Devices:
  - CPU: cpu:0 (8.0 GB)
  - GPU: gpu:0 (NVIDIA Tesla T4, 16.0 GB)  # if GPU available
  - TPU: tpu:0 (TPU v4, 32.0 GB)  # if TPU available

Selected Device: gpu:0
```

### Monitor Resource Usage

```bash
# For GPU
nvidia-smi

# For TPU
gcloud compute tpus describe TPU_NAME --zone=ZONE
```

## 💰 Cost Estimates

### GPU Costs (Approximate)
- **NVIDIA T4**: ~$0.35-0.70/hour
- **NVIDIA A100 40GB**: ~$3.00-4.00/hour
- **NVIDIA A100 80GB**: ~$4.00-6.00/hour
- **NVIDIA L4**: ~$0.50-1.00/hour

### TPU Costs (Approximate)
- **TPU v4-8**: ~$32.00/hour
- **TPU v4-32**: ~$128.00/hour
- **TPU v5e**: Pricing varies

### Cost Optimization Tips

1. **Use Preemptible Instances**: Save up to 80% on GPU/TPU costs
2. **Auto-scaling**: Scale down during low usage
3. **Reserved Instances**: Commit to 1-3 years for discounts
4. **Spot Instances**: Use GKE spot node pools

## 🔒 Security

### Secrets Management

1. **Create Secret in GKE**:
   ```bash
   kubectl create secret generic daena-secrets \
     --from-literal=aes-key="$(openssl rand -base64 32)"
   ```

2. **Use Secret Manager**:
   ```bash
   gcloud secrets create daena-aes-key --data-file=- < <(openssl rand -base64 32)
   ```

3. **Grant Access**:
   ```bash
   gcloud secrets add-iam-policy-binding daena-aes-key \
     --member="serviceAccount:YOUR_SA@PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

## 🐛 Troubleshooting

### GPU Not Detected

1. Check NVIDIA drivers:
   ```bash
   nvidia-smi
   ```

2. Verify GPU quota:
   ```bash
   gcloud compute project-info describe --project=PROJECT_ID
   ```

3. Check node labels (GKE):
   ```bash
   kubectl get nodes --show-labels | grep accelerator
   ```

### TPU Not Accessible

1. Check TPU status:
   ```bash
   gcloud compute tpus describe TPU_NAME --zone=ZONE
   ```

2. Verify JAX installation:
   ```bash
   pip install jax[tpu] -f https://storage.googleapis.com/jax-releases/libtpu_releases.html
   ```

3. Check network connectivity:
   ```bash
   ping TPU_IP_ADDRESS
   ```

### High Costs

1. **Stop unused resources**:
   ```bash
   gcloud compute instances stop INSTANCE_NAME --zone=ZONE
   gcloud compute tpus stop TPU_NAME --zone=ZONE
   ```

2. **Delete resources**:
   ```bash
   gcloud compute instances delete INSTANCE_NAME --zone=ZONE
   gcloud compute tpus delete TPU_NAME --zone=ZONE
   ```

## 📚 Additional Resources

- [GCP GPU Documentation](https://cloud.google.com/compute/docs/gpus)
- [GCP TPU Documentation](https://cloud.google.com/tpu/docs)
- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [DeviceManager Documentation](../docs/ARCHITECTURE_GROUND_TRUTH.md#devicemanager)

## 🆘 Support

For issues or questions:
- Check device report: `python3 Tools/daena_device_report.py`
- Review logs: `kubectl logs -l app=daena`
- Contact: masoud.masoori@mas-ai.co

