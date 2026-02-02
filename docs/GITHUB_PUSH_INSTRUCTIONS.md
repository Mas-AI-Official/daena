# GitHub Push Instructions for Daena

## Prerequisites

1. **GitHub Account** with access to private repository
2. **Git** installed on your system
3. **SSH Key** or **Personal Access Token** configured

## Initial Setup

### 1. Initialize Git Repository (if not already done)

```bash
cd Daena
git init
```

### 2. Add Remote Repository

```bash
# Replace with your actual repository URL
git remote add origin git@github.com:YOUR_USERNAME/daena-private.git

# OR using HTTPS
git remote add origin https://github.com/YOUR_USERNAME/daena-private.git
```

### 3. Verify Remote

```bash
git remote -v
```

## Files to Commit

### Essential Files (Always Commit)
- `Core/` - Core system files including DeviceManager
- `backend/` - Backend services and API
- `memory_service/` - NBMF memory system
- `Agents/` - Agent implementations
- `Tools/` - Diagnostic and utility tools
- `docs/` - Documentation
- `requirements.txt` - Dependencies
- `Dockerfile` - Docker configuration
- `docker-compose.yml` - Docker Compose setup
- `LAUNCH_DAENA_COMPLETE.bat` - Launch script
- `DEPLOYMENT_README.md` - Deployment guide
- `.gitignore` - Git ignore rules

### Files to Exclude (Already in .gitignore)
- `venv*/` - Virtual environments
- `.env` - Environment variables
- `*.db` - Database files
- `logs/` - Log files
- `cache/` - Cache files
- `__pycache__/` - Python cache
- `*.key`, `*.pem` - Security keys

## Push to GitHub

### 1. Stage Files

```bash
# Add all tracked files
git add .

# OR add specific files
git add Core/ backend/ memory_service/ Tools/ docs/ requirements.txt Dockerfile docker-compose.yml LAUNCH_DAENA_COMPLETE.bat DEPLOYMENT_README.md .gitignore
```

### 2. Commit Changes

```bash
git commit -m "Add TPU/GPU device support with DeviceManager

- Implemented DeviceManager hardware abstraction layer
- Added CPU/GPU/TPU detection and automatic routing
- Updated NBMF encoder/decoder with device support
- Integrated council service with batch inference
- Created diagnostic CLI tool (daena_device_report.py)
- Updated Docker configuration
- Enhanced launch script
- Updated documentation
- Version 2.0.0 with multi-device support"
```

### 3. Push to GitHub

```bash
# First time push
git push -u origin main

# OR if using master branch
git push -u origin master

# Subsequent pushes
git push
```

## Branch Strategy

### Main Branch (Production)
```bash
git checkout -b main
git push -u origin main
```

### Development Branch
```bash
git checkout -b develop
git push -u origin develop
```

### Feature Branch
```bash
git checkout -b feature/tpu-gpu-support
# ... make changes ...
git push -u origin feature/tpu-gpu-support
```

## Authentication

### Using SSH (Recommended)

1. **Generate SSH Key** (if not exists):
```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
```

2. **Add to GitHub**:
   - Copy public key: `cat ~/.ssh/id_ed25519.pub`
   - Add to GitHub: Settings → SSH and GPG keys → New SSH key

3. **Test Connection**:
```bash
ssh -T git@github.com
```

### Using Personal Access Token (HTTPS)

1. **Create Token**:
   - GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
   - Generate new token with `repo` scope

2. **Use Token**:
```bash
git remote set-url origin https://YOUR_TOKEN@github.com/YOUR_USERNAME/daena-private.git
```

## Verification

### Check Repository Status
```bash
git status
```

### View Commit History
```bash
git log --oneline
```

### Verify Remote
```bash
git remote show origin
```

## Troubleshooting

### Issue: Permission Denied
**Solution**: Check SSH key or use Personal Access Token

### Issue: Large Files
**Solution**: Ensure `.gitignore` excludes large files (models, databases, etc.)

### Issue: Merge Conflicts
**Solution**: 
```bash
git pull origin main
# Resolve conflicts
git add .
git commit -m "Resolve merge conflicts"
git push
```

## Security Checklist

Before pushing:
- [ ] No API keys in code
- [ ] No passwords in files
- [ ] `.env` files in `.gitignore`
- [ ] Database files excluded
- [ ] Security keys excluded
- [ ] Private keys excluded

## Post-Push Verification

1. **Check GitHub Repository**:
   - Verify all files are present
   - Check file sizes are reasonable
   - Verify `.gitignore` is working

2. **Test Clone** (on different machine):
```bash
git clone git@github.com:YOUR_USERNAME/daena-private.git
cd daena-private
# Verify structure
```

## Cloud Deployment from GitHub

### Pull Latest Changes
```bash
git pull origin main
```

### Deploy
```bash
# Run launch script
./LAUNCH_DAENA_COMPLETE.bat  # Windows
# OR
./launch.sh  # Linux/Mac

# OR use Docker
docker-compose up -d
```

---

**Note**: Always review what you're committing before pushing. Use `git status` and `git diff` to verify changes.


