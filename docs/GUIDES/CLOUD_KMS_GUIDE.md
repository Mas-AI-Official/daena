# Cloud KMS Integration Guide

**Status**: ✅ **PRODUCTION READY**  
**Date**: 2025-01-XX

## Overview

Daena supports integration with cloud Key Management Services (KMS) for enterprise-grade key management, automatic key rotation, and compliance with security standards (SOC 2, ISO 27001).

## Supported Providers

- **AWS KMS** - Amazon Web Services Key Management Service
- **Azure Key Vault** - Microsoft Azure Key Vault
- **GCP Secret Manager** - Google Cloud Platform Secret Manager

---

## Quick Start

### 1. Choose Your Provider

Set the provider via environment variable:

```bash
export DAENA_CLOUD_KMS_PROVIDER=aws    # or 'azure' or 'gcp'
```

### 2. Configure Provider-Specific Settings

See provider-specific sections below.

### 3. Verify Integration

```bash
python Tools/daena_key_rotate.py --test-cloud-kms
```

---

## AWS KMS Integration

### Prerequisites

1. **Install AWS SDK**:
```bash
pip install boto3
```

2. **Configure AWS Credentials**:
```bash
# Option 1: AWS CLI
aws configure

# Option 2: Environment variables
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1

# Option 3: IAM Role (for EC2/ECS/Lambda)
# No configuration needed - uses instance role
```

### Configuration

```bash
# Required
export DAENA_CLOUD_KMS_PROVIDER=aws
export AWS_REGION=us-east-1
export AWS_KMS_KEY_ID=arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012

# Optional
export AWS_PROFILE=production  # Use specific AWS profile
```

### Usage

```python
from memory_service.cloud_kms import AWSKMSAdapter

# Initialize adapter
adapter = AWSKMSAdapter(
    region="us-east-1",
    key_id="arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
)

# Get key
key = adapter.get_key("daena-encryption-key")

# Create new key
new_key = adapter.create_key("daena-encryption-key-v2")

# Rotate key
rotated_key = adapter.rotate_key("daena-encryption-key")
```

### IAM Permissions

Your AWS credentials need the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "kms:CreateKey",
        "kms:DescribeKey",
        "kms:GenerateDataKey",
        "kms:Decrypt",
        "kms:Encrypt",
        "kms:ScheduleKeyDeletion",
        "kms:ListKeys"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Azure Key Vault Integration

### Prerequisites

1. **Install Azure SDK**:
```bash
pip install azure-keyvault-secrets azure-identity
```

2. **Create Azure Key Vault**:
```bash
az keyvault create --name daena-kv --resource-group daena-rg --location eastus
```

### Configuration

```bash
# Required
export DAENA_CLOUD_KMS_PROVIDER=azure
export AZURE_KEY_VAULT_URL=https://daena-kv.vault.azure.net/
export AZURE_TENANT_ID=your-tenant-id
export AZURE_CLIENT_ID=your-client-id
export AZURE_CLIENT_SECRET=your-client-secret

# Optional: Use Managed Identity (for Azure VMs/App Service)
# No client_id/client_secret needed - uses system-assigned identity
```

### Usage

```python
from memory_service.cloud_kms import AzureKeyVaultAdapter

# Initialize adapter
adapter = AzureKeyVaultAdapter(
    vault_url="https://daena-kv.vault.azure.net/",
    tenant_id="your-tenant-id",
    client_id="your-client-id",
    client_secret="your-client-secret"
)

# Get key
key = adapter.get_key("daena-encryption-key")

# Create new key
new_key = adapter.create_key("daena-encryption-key-v2")

# Rotate key
rotated_key = adapter.rotate_key("daena-encryption-key")
```

### Azure RBAC Permissions

Your Azure service principal needs the following permissions:

```bash
# Grant "Key Vault Secrets Officer" role
az role assignment create \
  --role "Key Vault Secrets Officer" \
  --assignee <service-principal-id> \
  --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.KeyVault/vaults/<vault-name>
```

---

## GCP Secret Manager Integration

### Prerequisites

1. **Install GCP SDK**:
```bash
pip install google-cloud-secret-manager
```

2. **Enable Secret Manager API**:
```bash
gcloud services enable secretmanager.googleapis.com
```

3. **Create Service Account**:
```bash
gcloud iam service-accounts create daena-kms \
  --display-name="Daena KMS Service Account"

gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:daena-kms@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.admin"
```

### Configuration

```bash
# Required
export DAENA_CLOUD_KMS_PROVIDER=gcp
export GCP_PROJECT_ID=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Optional: Use Application Default Credentials (for GCP VMs/Cloud Run)
# No credentials file needed - uses metadata service
```

### Usage

```python
from memory_service.cloud_kms import GCPSecretManagerAdapter

# Initialize adapter
adapter = GCPSecretManagerAdapter(
    project_id="your-project-id",
    credentials_path="/path/to/service-account-key.json"
)

# Get key
key = adapter.get_key("daena-encryption-key")

# Create new key
new_key = adapter.create_key("daena-encryption-key-v2")

# Rotate key
rotated_key = adapter.rotate_key("daena-encryption-key")
```

### GCP IAM Permissions

Your service account needs the following roles:

- `roles/secretmanager.admin` - Full access to secrets
- Or `roles/secretmanager.secretAccessor` - Read-only access

---

## Integration with Daena KMS

### Automatic Integration

When cloud KMS is configured, Daena automatically:

1. **Stores keys in cloud KMS** during key rotation
2. **Retrieves keys from cloud KMS** when needed
3. **Maintains local manifest** for audit trail

### Manual Integration

```python
from memory_service.kms import KeyManagementService
from memory_service.cloud_kms import get_cloud_kms_adapter

# Initialize KMS with cloud adapter
cloud_adapter = get_cloud_kms_adapter("aws")  # or "azure" or "gcp"

kms = KeyManagementService(
    cloud_kms_provider="aws"  # Auto-initializes cloud adapter
)

# Record rotation (automatically stores in cloud KMS)
kms.record_rotation(
    key_material="new-encryption-key",
    key_id="daena-encryption-key",
    store_in_cloud=True  # Default: True
)

# Retrieve key from cloud KMS
key = kms.get_key_from_cloud("daena-encryption-key")
```

---

## Key Rotation Automation

### Scheduled Rotation

Set up automatic key rotation using cron or cloud scheduler:

```bash
# Cron example (rotate every 90 days)
0 0 1 */3 * /usr/bin/python Tools/daena_key_rotate.py --cloud-kms
```

### Cloud Scheduler (GCP)

```bash
gcloud scheduler jobs create http daena-key-rotation \
  --schedule="0 0 1 */3 *" \
  --uri="https://your-api-endpoint/rotate-keys" \
  --http-method=POST
```

### AWS EventBridge

```json
{
  "ScheduleExpression": "cron(0 0 1 */3 ? *)",
  "Target": {
    "Arn": "arn:aws:lambda:region:account:function:rotate-keys",
    "Id": "1"
  }
}
```

---

## Security Best Practices

### 1. Least Privilege

- Grant minimum required permissions
- Use service accounts/roles, not user accounts
- Rotate credentials regularly

### 2. Key Rotation

- Rotate keys every 90 days (or per compliance requirements)
- Test rotation in staging first
- Keep backup of previous keys for recovery

### 3. Monitoring

- Enable audit logging in cloud KMS
- Monitor key access patterns
- Alert on unusual activity

### 4. Backup

- Keep local manifest backups
- Export keys securely for disaster recovery
- Test restore procedures

---

## Troubleshooting

### AWS KMS

**Error**: `AccessDeniedException`

**Solution**:
- Verify IAM permissions
- Check key policy
- Ensure region matches

**Error**: `InvalidKeyUsageException`

**Solution**:
- Use symmetric keys (not asymmetric)
- Check key spec matches usage

### Azure Key Vault

**Error**: `Unauthorized`

**Solution**:
- Verify service principal permissions
- Check RBAC assignments
- Ensure vault URL is correct

**Error**: `SecretNotFound`

**Solution**:
- Verify secret name matches
- Check vault access permissions
- Ensure secret exists

### GCP Secret Manager

**Error**: `PermissionDenied`

**Solution**:
- Verify service account permissions
- Check IAM bindings
- Ensure project ID is correct

**Error**: `NotFound`

**Solution**:
- Verify secret name
- Check project ID
- Ensure secret exists

---

## Compliance & Audit

### SOC 2 Compliance

Cloud KMS integration helps meet:
- **CC6.1**: Logical and physical access controls
- **CC6.6**: Encryption of sensitive data
- **CC6.7**: Key management

### ISO 27001 Compliance

Helps meet:
- **A.10.1.1**: Cryptographic controls
- **A.10.1.2**: Key management

### Audit Trail

All key operations are logged:
- Local manifest (`.kms/manifests/`)
- Cloud KMS audit logs
- Application logs

---

## Migration Guide

### From Local KMS to Cloud KMS

1. **Backup existing keys**:
```bash
python Tools/daena_key_rotate.py --backup
```

2. **Configure cloud KMS** (see provider sections above)

3. **Test integration**:
```bash
python Tools/daena_key_rotate.py --test-cloud-kms
```

4. **Migrate keys**:
```bash
python Tools/daena_key_rotate.py --migrate-to-cloud
```

5. **Verify migration**:
```bash
python Tools/daena_key_rotate.py --verify-cloud-kms
```

---

## Cost Considerations

### AWS KMS

- **CMK**: $1/month per key
- **API calls**: $0.03 per 10,000 requests
- **Data keys**: Free (generated from CMK)

### Azure Key Vault

- **Standard tier**: $0.03 per 10,000 operations
- **Premium tier**: $0.15 per 10,000 operations
- **Storage**: Included

### GCP Secret Manager

- **Secrets**: $0.06 per secret per month
- **Access operations**: $0.03 per 10,000 operations
- **Versions**: $0.06 per version per month

---

## Related Documentation

- `memory_service/kms.py` - KMS service implementation
- `memory_service/cloud_kms.py` - Cloud KMS adapters
- `Tools/daena_key_rotate.py` - Key rotation tool
- `docs/SECURITY_HARDENING_REPORT.md` - Security overview

---

## Support

For issues or questions:
1. Check this guide
2. Review provider-specific documentation
3. Check application logs
4. Verify credentials and permissions

---

**Status**: ✅ **PRODUCTION READY**  
**Last Updated**: 2025-01-XX

