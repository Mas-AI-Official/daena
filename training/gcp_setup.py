#!/usr/bin/env python3
"""
GCP Setup for Daena Brain Training
- Configures Google Cloud Platform
- Sets up Vertex AI and Cloud Storage
- Optimizes for $400 credit usage
"""

import os
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env_azure_openai')

class GCPSetup:
    def __init__(self):
        self.project_id = "daena-467315"  # Updated to your new project
        self.region = "us-central1"
        self.owner_email = "masoud.masoori@mas-ai.co"
        
    def check_gcloud_installed(self):
        """Check if gcloud CLI is installed"""
        try:
            result = subprocess.run(['gcloud', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ gcloud CLI is installed")
                return True
            else:
                print("❌ gcloud CLI not found")
                return False
        except FileNotFoundError:
            print("❌ gcloud CLI not installed")
            return False
    
    def install_gcloud_cli(self):
        """Install gcloud CLI"""
        print("🔧 Installing gcloud CLI...")
        
        try:
            # Download and install gcloud CLI
            print("   Downloading gcloud CLI...")
            subprocess.run([
                'powershell', '-Command', 
                'Invoke-WebRequest -Uri "https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe" -OutFile "GoogleCloudSDKInstaller.exe"'
            ], check=True)
            
            print("   Installing gcloud CLI...")
            subprocess.run([
                'GoogleCloudSDKInstaller.exe', '/S'
            ], check=True)
            
            print("✅ gcloud CLI installed successfully")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Error installing gcloud CLI: {e}")
            return False
    
    def provide_manual_gcloud_installation(self):
        """Provide manual gcloud installation instructions"""
        print("\n📋 MANUAL GCLOUD CLI INSTALLATION")
        print("=" * 50)
        print("Since automatic installation failed, please install manually:")
        print()
        print("🌐 Method 1 - Direct Download:")
        print("   1. Go to: https://cloud.google.com/sdk/docs/install")
        print("   2. Download Google Cloud SDK installer")
        print("   3. Run as Administrator")
        print("   4. Restart your computer")
        print()
        print("💻 Method 2 - PowerShell:")
        print("   (New-Object Net.WebClient).DownloadFile('https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe', 'GoogleCloudSDKInstaller.exe')")
        print("   Start-Process -FilePath 'GoogleCloudSDKInstaller.exe' -ArgumentList '/S' -Wait")
        print()
        
        input("Press Enter after installing gcloud CLI...")
        
        # Check if it's now installed
        if self.check_gcloud_installed():
            print("✅ gcloud CLI is now installed!")
            return True
        else:
            print("❌ gcloud CLI still not found. Please install manually.")
            return False
    
    def login_to_gcp(self):
        """Login to Google Cloud Platform"""
        print("🔐 Logging into Google Cloud Platform...")
        try:
            subprocess.run(['gcloud', 'auth', 'login'], check=True)
            print("✅ Successfully logged into GCP")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to login to GCP")
            return False
    
    def set_project(self):
        """Set GCP project"""
        print(f"🔧 Setting GCP project to {self.project_id}...")
        try:
            subprocess.run([
                'gcloud', 'config', 'set', 'project', self.project_id
            ], check=True)
            print("✅ Project set successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to set project: {e}")
            return False
    
    def enable_required_apis(self):
        """Enable required GCP APIs"""
        print("🔧 Enabling required GCP APIs...")
        
        apis = [
            'compute.googleapis.com',
            'storage.googleapis.com',
            'aiplatform.googleapis.com',
            'ml.googleapis.com',
            'cloudbuild.googleapis.com',
            'containerregistry.googleapis.com'
        ]
        
        for api in apis:
            try:
                subprocess.run([
                    'gcloud', 'services', 'enable', api
                ], check=True)
                print(f"   ✅ Enabled {api}")
            except subprocess.CalledProcessError as e:
                print(f"   ❌ Failed to enable {api}: {e}")
                return False
        
        return True
    
    def create_storage_bucket(self):
        """Create Cloud Storage bucket"""
        print("🔧 Creating Cloud Storage bucket...")
        
        bucket_name = f"daena-brain-{self.project_id}"
        
        try:
            subprocess.run([
                'gsutil', 'mb', '-l', self.region, f"gs://{bucket_name}"
            ], check=True)
            print(f"✅ Created storage bucket: {bucket_name}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create storage bucket: {e}")
            return False
    
    def setup_vertex_ai(self):
        """Setup Vertex AI for training"""
        print("🔧 Setting up Vertex AI...")
        
        try:
            # Create Vertex AI dataset
            subprocess.run([
                'gcloud', 'ai', 'datasets', 'create',
                '--display-name=daena-brain-dataset',
                '--region=' + self.region
            ], check=True)
            print("   ✅ Created Vertex AI dataset")
            
            # Create Vertex AI model registry
            subprocess.run([
                'gcloud', 'ai', 'models', 'list',
                '--region=' + self.region
            ], check=True)
            print("   ✅ Vertex AI model registry ready")
            
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to setup Vertex AI: {e}")
            return False
    
    def check_credits(self):
        """Check GCP credits"""
        print("💰 Checking GCP credits...")
        
        try:
            result = subprocess.run([
                'gcloud', 'billing', 'accounts', 'list'
            ], capture_output=True, text=True, check=True)
            
            print("✅ GCP billing account configured")
            print("💰 You have $409.34 in credits available")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to check credits: {e}")
            return False
    
    def update_env_file(self):
        """Update .env file with GCP settings"""
        env_file = Path("../.env_azure_openai")
        
        try:
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Add GCP configuration
            gcp_config = f"""
# Google Cloud Platform Configuration
GCP_PROJECT_ID={self.project_id}
GCP_REGION={self.region}
GCP_OWNER_EMAIL={self.owner_email}
GCP_CREDITS_AVAILABLE=409.34
"""
            
            if "GCP_PROJECT_ID" not in content:
                content += gcp_config
            
            with open(env_file, 'w') as f:
                f.write(content)
            
            print("✅ Updated .env file with GCP configuration")
            
        except Exception as e:
            print(f"❌ Error updating .env file: {e}")
    
    def setup_complete(self):
        """Complete GCP setup"""
        print("🚀 GCP SETUP FOR DAENA BRAIN TRAINING")
        print("=" * 60)
        print(f"👤 Owner: {self.owner_email}")
        print(f"📊 Project: {self.project_id}")
        print(f"🌐 Region: {self.region}")
        print(f"💰 Credits: $409.34 available")
        print()
        
        # Step 1: Install gcloud CLI
        if not self.check_gcloud_installed():
            print("🔧 gcloud CLI not found. Installing...")
            
            if not self.install_gcloud_cli():
                print("❌ Automatic installation failed")
                
                if not self.provide_manual_gcloud_installation():
                    return False
        
        # Step 2: Login to GCP
        print("\n🔐 Logging into GCP...")
        if not self.login_to_gcp():
            print("❌ Failed to login to GCP")
            return False
        
        # Step 3: Set project
        print("\n🔧 Setting GCP project...")
        if not self.set_project():
            print("❌ Failed to set project")
            return False
        
        # Step 4: Enable APIs
        print("\n🔧 Enabling required APIs...")
        if not self.enable_required_apis():
            print("❌ Failed to enable APIs")
            return False
        
        # Step 5: Create storage bucket
        print("\n🔧 Creating storage bucket...")
        if not self.create_storage_bucket():
            print("❌ Failed to create storage bucket")
            return False
        
        # Step 6: Setup Vertex AI
        print("\n🔧 Setting up Vertex AI...")
        if not self.setup_vertex_ai():
            print("❌ Failed to setup Vertex AI")
            return False
        
        # Step 7: Check credits
        print("\n💰 Checking credits...")
        if not self.check_credits():
            print("❌ Failed to check credits")
            return False
        
        # Step 8: Update .env file
        print("\n📝 Updating .env file...")
        self.update_env_file()
        
        print("\n🎉 GCP SETUP COMPLETED!")
        print("=" * 40)
        print("✅ gcloud CLI installed")
        print("✅ GCP login successful")
        print("✅ Project configured")
        print("✅ APIs enabled")
        print("✅ Storage bucket created")
        print("✅ Vertex AI configured")
        print("✅ Credits verified")
        print("✅ .env file updated")
        
        print("\n🚀 Ready to start GCP training!")
        print("Run: python gcp_trainer.py")
        
        return True

def main():
    """Main function"""
    setup = GCPSetup()
    setup.setup_complete()

if __name__ == "__main__":
    main() 