#!/bin/bash
# Daena Production Deployment Script
# Prepares and deploys the Daena system to production

echo "============================================================"
echo "  DAENA PRODUCTION DEPLOYMENT"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Pre-deployment checks
echo "📋 Step 1: Pre-deployment Checks"
echo "--------------------------------"

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "✅ Python version: $python_version"

# Check virtual environment
if [ -d "venv_daena_main_py310" ]; then
    echo "✅ Virtual environment found"
else
    echo "❌ Virtual environment not found - run: python -m venv venv_daena_main_py310"
    exit 1
fi

# Check database
if [ -f "daena.db" ]; then
    echo "✅ Database found: daena.db"
else
    echo "⚠️  No database found - will be created on first run"
fi

# Step 2: Install/Update dependencies
echo ""
echo "📦 Step 2: Installing Dependencies"
echo "-----------------------------------"
source venv_daena_main_py310/bin/activate 2>/dev/null || call venv_daena_main_py310\\Scripts\\activate.bat

pip install -r requirements.txt --quiet
echo "✅ Dependencies installed"

# Step 3: Run tests
echo ""
echo "🧪 Step 3: Running Production Tests"
echo "------------------------------------"
python scripts/test_production_ready.py
if [ $? -ne 0 ]; then
    echo "${RED}❌ Tests failed - deployment aborted${NC}"
    exit 1
fi
echo "✅ All tests passed"

# Step 4: Backup current system
echo ""
echo "💾 Step 4: Creating Backup"
echo "--------------------------"
timestamp=$(date +%Y%m%d_%H%M%S)
backup_dir="backups/pre_deployment_${timestamp}"
mkdir -p "$backup_dir"

# Backup database
if [ -f "daena.db" ]; then
    cp daena.db "$backup_dir/"
    echo "✅ Database backed up"
fi

# Backup config
if [ -f "backend/config/settings.py" ]; then
    cp backend/config/settings.py "$backup_dir/"
    echo "✅ Configuration backed up"
fi

echo "✅ Backup created: $backup_dir"

# Step 5: Environment configuration
echo ""
echo "⚙️  Step 5: Environment Configuration"
echo "-------------------------------------"

# Check .env file
if [ -f ".env" ]; then
    echo "✅ .env file found"
else
    echo "⚠️  Creating .env from template..."
    cat > .env << EOF
# Daena Production Configuration
ENVIRONMENT=production
DISABLE_AUTH=0
BACKEND_PORT=8000
AUDIO_PORT=5001
OLLAMA_HOST=http://127.0.0.1:11434
DEFAULT_MODEL=deepseek-r1:8b
DAENA_CREATOR=Masoud
ENABLE_LOCAL_ROUTER=true

# Database
DATABASE_URL=sqlite:///./daena.db

# Security (CHANGE THESE!)
SECRET_KEY=your-secret-key-here
JWT_SECRET=your-jwt-secret-here

# Optional: ElevenLabs API (for voice)
ELEVENLABS_API_KEY=
EOF
    echo "✅ .env template created - PLEASE UPDATE SECRET KEYS!"
fi

# Step 6: Database migrations
echo ""
echo "🗄️  Step 6: Database Migrations"
echo "-------------------------------"
python -c "from backend.database import init_db; init_db(); print('✅ Database initialized')" 2>/dev/null || echo "⚠️  Database already initialized or error occurred"

# Step 7: Start services
echo ""
echo "🚀 Step 7: Starting Services"
echo "----------------------------"
echo ""
echo "Starting Daena..."
echo ""
echo "Dashboard will be available at:"
echo "  → http://localhost:8000/ui/daena-office"
echo "  → API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the application
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level info

echo ""
echo "============================================================"
echo "  Deployment Complete!"
echo "============================================================"
