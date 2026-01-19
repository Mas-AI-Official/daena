#!/usr/bin/env python3
"""
Ultimate Daena Brain Training Launcher
- Sets up Azure CLI and resources first
- Then runs ultimate training with all biggest models
"""

import os
import sys
from pathlib import Path

def setup_azure_first():
    """Setup Azure CLI and resources first"""
    print("🔧 Setting up Azure CLI and resources...")
    
    try:
        from azure_setup import UltimateAzureSetup
        setup = UltimateAzureSetup()
        success = setup.setup_complete()
        
        if success:
            print("✅ Azure setup completed!")
            return True
        else:
            print("❌ Azure setup failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up Azure: {e}")
        return False

def run_ultimate_training():
    """Run ultimate Azure training"""
    print("🚀 Starting Ultimate Azure training...")
    
    try:
        from azure_trainer import UltimateAzureTrainer
        trainer = UltimateAzureTrainer()
        trainer.train_all_models()
        
    except Exception as e:
        print(f"❌ Error running ultimate training: {e}")

def main():
    """Main launcher function"""
    print("🧠 ULTIMATE DAENA BRAIN TRAINING LAUNCHER")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("../.env_azure_openai").exists():
        print("❌ .env_azure_openai not found in parent directory")
        return
    
    # Step 1: Setup Azure CLI and resources
    print("\n📦 STEP 1: Setting up Azure CLI and resources...")
    if not setup_azure_first():
        print("❌ Azure setup failed. Please check your Azure credentials.")
        return
    
    # Step 2: Run ultimate training
    print("\n🚀 STEP 2: Starting Ultimate Azure training...")
    run_ultimate_training()

if __name__ == "__main__":
    main() 