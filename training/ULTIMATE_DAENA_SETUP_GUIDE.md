# 🧠 ULTIMATE DAENA BRAIN SETUP GUIDE

## 📋 Complete Requirements & Setup Instructions

### **🔧 System Requirements**

#### **1. Azure Setup Requirements:**
```
- Azure CLI installation
- Azure subscription with Contributor permissions
- Azure storage account creation
- Service principal setup
- Resource group: "daena-brain-rg"
- Storage account: "daenabrainstorage"
- Container: "model-cache"
```

#### **2. Local Storage Requirements:**
```
- D: drive with 140GB free space
- Directory: D:/DaenaBrain/
- Subdirectories: trained_models, temp, logs, checkpoints
- HuggingFace cache: D:/DaenaBrain/hf_cache
```

#### **3. Environment Variables (.env_azure_openai):**
```
AZURE_SUBSCRIPTION_ID=ec89df08-c2bf-47d8-9ffe-040eb738fa9e
AZURE_TENANT_ID=25fd38cf-9d51-4dcb-91d7-734cc3d27916
AZURE_CLIENT_ID=[needs real value from Azure]
AZURE_CLIENT_SECRET=[needs real value from Azure]
HUGGINGFACE_TOKEN=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
AZURE_STORAGE_CONNECTION_STRING=[needs real value from Azure]
```

#### **4. Python Environment Requirements:**
```
- Python 3.10+
- Virtual environment: venv_daena_main_py310
- Required packages: transformers, torch, datasets, wandb, azure-storage-blob
- Environment activation: .\venv_daena_main_py310\Scripts\Activate.ps1
```

#### **5. Model Requirements:**
```
- 9 models total: ~400GB
- DeepSeek R1 (67GB), Qwen 2.5 72B (72GB), Code Llama 70B (70GB)
- Vision models: Qwen 2.5 VL 72B (72GB)
- Audio models: Whisper Large V3 (3GB), Bark (4GB)
- Video models: Stable Video Diffusion (5GB)
- Math models: WizardMath 70B (70GB)
```

#### **6. Network Requirements:**
```
- Stable internet connection
- Access to HuggingFace API
- Access to Azure services
- No firewall blocking azure.com or huggingface.co
```

---

## 🚀 Setup Instructions

### **Step 1: Install Azure CLI**
```powershell
# Method 1 - PowerShell (as Administrator):
winget install Microsoft.AzureCLI

# Method 2 - Direct Download:
# Go to: https://aka.ms/installazurecliwindows
# Download and run as Administrator

# Method 3 - Chocolatey (if installed):
choco install azure-cli
```

### **Step 2: Create Required Directories**
```powershell
# Create main directory structure
New-Item -ItemType Directory -Path "D:/DaenaBrain" -Force
New-Item -ItemType Directory -Path "D:/DaenaBrain/trained_models" -Force
New-Item -ItemType Directory -Path "D:/DaenaBrain/temp" -Force
New-Item -ItemType Directory -Path "D:/DaenaBrain/logs" -Force
New-Item -ItemType Directory -Path "D:/DaenaBrain/checkpoints" -Force
New-Item -ItemType Directory -Path "D:/DaenaBrain/hf_cache" -Force

# Set HuggingFace cache location
$env:HF_HOME = "D:/DaenaBrain/hf_cache"
```

### **Step 3: Setup Python Environment**
```powershell
# Activate virtual environment
.\venv_daena_main_py310\Scripts\Activate.ps1

# Install required packages
pip install transformers torch datasets wandb azure-storage-blob python-dotenv
```

### **Step 4: Login to Azure**
```powershell
# Login to Azure (opens browser)
az login

# Check subscription
az account show
```

### **Step 5: Create Azure Resources**
```powershell
# Create resource group
az group create --name daena-brain-rg --location eastus2

# Create storage account
az storage account create --name daenabrainstorage --resource-group daena-brain-rg --location eastus2 --sku Standard_LRS --kind StorageV2

# Create container
az storage container create --name model-cache --account-name daenabrainstorage

# Get connection string
az storage account show-connection-string --name daenabrainstorage --resource-group daena-brain-rg
```

### **Step 6: Create Service Principal**
```powershell
# Create service principal
az ad sp create-for-rbac --name daena-brain-automation --role Contributor --scopes /subscriptions/ec89df08-c2bf-47d8-9ffe-040eb738fa9e
```

### **Step 7: Update .env File**
```bash
# Replace placeholder values with real ones from Azure
AZURE_CLIENT_ID=[from service principal output]
AZURE_CLIENT_SECRET=[from service principal output]
AZURE_STORAGE_CONNECTION_STRING=[from storage account]
```

---

## 🔍 Troubleshooting Checklist

### **Check Azure CLI Installation:**
```powershell
az --version
```

### **Check D: Drive Space:**
```powershell
Get-WmiObject -Class Win32_LogicalDisk | Where-Object {$_.DeviceID -eq "D:"} | Select-Object DeviceID, @{Name="FreeSpace(GB)";Expression={[math]::Round($_.FreeSpace/1GB,2)}}
```

### **Check Python Environment:**
```powershell
python --version
pip list | findstr transformers
```

### **Check Azure Login:**
```powershell
az account show
```

### **Check HuggingFace Token:**
```powershell
curl -H "Authorization: Bearer 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" https://huggingface.co/api/models/microsoft/phi-2
```

### **Check Network Connectivity:**
```powershell
# Test Azure connectivity
Test-NetConnection -ComputerName azure.com -Port 443

# Test HuggingFace connectivity
Test-NetConnection -ComputerName huggingface.co -Port 443
```

---

## 🎯 Common Issues & Solutions

### **Issue 1: Azure CLI Not Found**
**Solution:**
```powershell
# Install via winget
winget install Microsoft.AzureCLI

# Or download manually from Microsoft
# Restart computer after installation
```

### **Issue 2: D: Drive Space Insufficient**
**Solution:**
```powershell
# Check space
Get-WmiObject -Class Win32_LogicalDisk | Where-Object {$_.DeviceID -eq "D:"}

# Need at least 140GB free space
# Clean up D: drive if needed
```

### **Issue 3: Python Environment Not Activated**
**Solution:**
```powershell
# Activate environment
.\venv_daena_main_py310\Scripts\Activate.ps1

# Check if activated
echo $env:VIRTUAL_ENV
```

### **Issue 4: Azure Login Failed**
**Solution:**
```powershell
# Clear existing login
az logout

# Login again
az login
```

### **Issue 5: HuggingFace Token Invalid**
**Solution:**
```powershell
# Test token
curl -H "Authorization: Bearer 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" https://huggingface.co/api/models/microsoft/phi-2

# Get new token from: https://huggingface.co/settings/tokens
```

### **Issue 6: Network Connectivity Problems**
**Solution:**
```powershell
# Check firewall settings
# Ensure azure.com and huggingface.co are not blocked
# Try using VPN if corporate network blocks these sites
```

---

## 🚀 Final Launch Commands

### **After Setup is Complete:**
```powershell
# Navigate to training directory
cd training

# Launch ultimate training
python launch_ultimate_training.py

# Or use batch file
start_ultimate_training.bat
```

---

## 📊 Expected Results

### **Successful Setup Should Show:**
```
✅ Azure CLI installed
✅ Azure login successful
✅ Service principal created
✅ Resource group created
✅ Storage account created
✅ Storage container created
✅ .env file updated with real credentials
✅ Python environment activated
✅ All required packages installed
✅ D: drive has sufficient space
✅ Network connectivity confirmed
```

### **Training Progress:**
```
🧠 ULTIMATE AZURE DAENA BRAIN TRAINING
📊 Total models: 9
✅ Completed: X
❌ Failed: Y
📊 Success Rate: Z%
```

---

## 🎯 Ask ChatGPT to Help With:

1. **"Help me install Azure CLI on Windows and set up Azure resources"**
2. **"Help me create the required directories on D: drive"**
3. **"Help me set up the Python environment and install required packages"**
4. **"Help me get real Azure credentials and update the .env file"**
5. **"Help me troubleshoot network connectivity to HuggingFace and Azure"**
6. **"Help me check if all requirements are met before starting training"**

---

**🎯 Goal: Create the world's most comprehensive AI brain with unlimited Azure storage and processing power!** 