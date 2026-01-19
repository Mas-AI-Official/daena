#!/usr/bin/env python3
"""
GCP Daena Brain Training Launcher
- Sets up GCP CLI and resources first
- Then runs GCP training with all biggest models
"""

import os
import sys
from pathlib import Path

def setup_gcp_first():
    """Setup GCP CLI and resources first"""
    print("🔧 Setting up GCP CLI and resources...")
    
    try:
        from gcp_setup import GCPSetup
        setup = GCPSetup()
        success = setup.setup_complete()
        
        if success:
            print("✅ GCP setup completed!")
            return True
        else:
            print("❌ GCP setup failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error setting up GCP: {e}")
        return False

def run_gcp_training():
    """Run GCP training"""
    print("🚀 Starting GCP training...")
    
    try:
        from gcp_trainer import GCPDaenaTrainer
        trainer = GCPDaenaTrainer()
        trainer.train_all_models()
        
    except Exception as e:
        print(f"❌ Error running GCP training: {e}")

def main():
    """Main launcher function"""
    print("🧠 GCP DAENA BRAIN TRAINING LAUNCHER")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("../.env_azure_openai").exists():
        print("❌ .env_azure_openai not found in parent directory")
        return
    
    # Step 1: Setup GCP CLI and resources
    print("\n📦 STEP 1: Setting up GCP CLI and resources...")
    if not setup_gcp_first():
        print("❌ GCP setup failed. Please check your GCP credentials.")
        return
    
    # Step 2: Run GCP training
    print("\n🚀 STEP 2: Starting GCP training...")
    run_gcp_training()

if __name__ == "__main__":
    main() 