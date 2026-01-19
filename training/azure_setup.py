#!/usr/bin/env python3
"""
Ultimate Azure Setup for Daena Brain Training
- Installs Azure CLI automatically
- Creates Azure resources for unlimited model storage
- Sets up everything needed for training
"""

import os
import subprocess
import json
import sys
import urllib.request
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env_azure_openai')

class UltimateAzureSetup:
    def __init__(self):
        self.subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        self.tenant_id = os.getenv('AZURE_TENANT_ID')
        self.owner_email = os.getenv('DAENA_OWNER_EMAIL', 'masoud.masori@gmail.com')
        
    def check_azure_cli(self):
        """Check if Azure CLI is installed"""
        try:
            result = subprocess.run(['az', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Azure CLI is already installed")
                return True
            else:
                print("❌ Azure CLI not found")
                return False
        except FileNotFoundError:
            print("❌ Azure CLI not installed")
            return False
    
    def install_azure_cli_automatic(self):
        """Try automatic Azure CLI installation"""
        print("🔧 Installing Azure CLI automatically...")
        
        # Method 1: Try winget
        print("   Trying winget...")
        try:
            result = subprocess.run(['winget', 'install', 'Microsoft.AzureCLI'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Azure CLI installed via winget")
                return True
        except FileNotFoundError:
            print("   winget not available")
        
        # Method 2: Try chocolatey
        print("   Trying chocolatey...")
        try:
            result = subprocess.run(['choco', 'install', 'azure-cli', '-y'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ Azure CLI installed via chocolatey")
                return True
        except FileNotFoundError:
            print("   chocolatey not available")
        
        # Method 3: Direct download
        print("   Trying direct download...")
        return self.download_and_install_azure_cli()
    
    def download_and_install_azure_cli(self):
        """Download and install Azure CLI directly"""
        try:
            # Download Azure CLI installer
            installer_url = "https://aka.ms/installazurecliwindows"
            installer_path = "azure-cli-installer.msi"
            
            print("   Downloading from Microsoft...")
            urllib.request.urlretrieve(installer_url, installer_path)
            
            # Install silently
            print("   Installing Azure CLI...")
            result = subprocess.run(['msiexec', '/i', installer_path, '/quiet', '/norestart'], 
                                  capture_output=True, text=True)
            
            # Clean up installer
            try:
                os.remove(installer_path)
            except:
                pass
            
            if result.returncode == 0:
                print("✅ Azure CLI installed successfully")
                return True
            else:
                print("❌ Failed to install Azure CLI")
                return False
                
        except Exception as e:
            print(f"❌ Error downloading Azure CLI: {e}")
            return False
    
    def provide_manual_installation(self):
        """Provide manual installation instructions"""
        print("\n📋 MANUAL AZURE CLI INSTALLATION")
        print("=" * 50)
        print("Since automatic installation failed, please install manually:")
        print()
        print("🌐 Method 1 - Direct Download:")
        print("   1. Go to: https://aka.ms/installazurecliwindows")
        print("   2. Download the MSI installer")
        print("   3. Run as Administrator")
        print("   4. Restart your computer")
        print()
        print("💻 Method 2 - PowerShell (as Administrator):")
        print("   winget install Microsoft.AzureCLI")
        print()
        print("🍫 Method 3 - Chocolatey (if installed):")
        print("   choco install azure-cli")
        print()
        
        input("Press Enter after installing Azure CLI...")
        
        # Check if it's now installed
        if self.check_azure_cli():
            print("✅ Azure CLI is now installed!")
            return True
        else:
            print("❌ Azure CLI still not found. Please install manually.")
            return False
    
    def login_to_azure(self):
        """Login to Azure"""
        print("🔐 Logging into Azure...")
        try:
            subprocess.run(['az', 'login'], check=True)
            print("✅ Successfully logged into Azure")
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to login to Azure")
            return False
    
    def create_service_principal(self):
        """Create service principal for automation"""
        print("🔑 Creating Azure service principal...")
        
        try:
            result = subprocess.run([
                'az', 'ad', 'sp', 'create-for-rbac',
                '--name', 'daena-brain-automation',
                '--role', 'Contributor',
                '--scopes', f'/subscriptions/{self.subscription_id}'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                sp_info = json.loads(result.stdout)
                print("✅ Service principal created")
                
                # Update .env file with real credentials
                self.update_env_with_credentials(sp_info)
                
                return sp_info
            else:
                print("❌ Failed to create service principal")
                print(f"Error: {result.stderr}")
                return None
                
        except Exception as e:
            print(f"❌ Error creating service principal: {e}")
            return None
    
    def update_env_with_credentials(self, sp_info):
        """Update .env file with real Azure credentials"""
        env_file = Path("../.env_azure_openai")
        
        try:
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Replace placeholder credentials with real ones
            content = content.replace(
                'AZURE_CLIENT_ID=your_azure_client_id_here',
                f"AZURE_CLIENT_ID={sp_info['appId']}"
            )
            content = content.replace(
                'AZURE_CLIENT_SECRET=your_azure_client_secret_here',
                f"AZURE_CLIENT_SECRET={sp_info['password']}"
            )
            
            with open(env_file, 'w') as f:
                f.write(content)
            
            print("✅ Updated .env file with real Azure credentials")
            
        except Exception as e:
            print(f"❌ Error updating .env file: {e}")
    
    def create_azure_resources(self):
        """Create all Azure resources for Daena brain"""
        print("📦 Creating Azure resources...")
        
        # Create resource group
        print("   📦 Creating resource group...")
        try:
            subprocess.run([
                'az', 'group', 'create',
                '--name', 'daena-brain-rg',
                '--location', 'eastus2'
            ], check=True)
            print("   ✅ Resource group created")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to create resource group: {e}")
            return False
        
        # Create storage account
        print("   💾 Creating storage account...")
        try:
            subprocess.run([
                'az', 'storage', 'account', 'create',
                '--name', 'daenabrainstorage',
                '--resource-group', 'daena-brain-rg',
                '--location', 'eastus2',
                '--sku', 'Standard_LRS',
                '--kind', 'StorageV2'
            ], check=True)
            print("   ✅ Storage account created")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to create storage account: {e}")
            return False
        
        # Create storage container
        print("   🗂️ Creating storage container...")
        try:
            subprocess.run([
                'az', 'storage', 'container', 'create',
                '--name', 'model-cache',
                '--account-name', 'daenabrainstorage'
            ], check=True)
            print("   ✅ Storage container created")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to create storage container: {e}")
            return False
        
        # Get connection string
        print("   🔗 Getting connection string...")
        try:
            result = subprocess.run([
                'az', 'storage', 'account', 'show-connection-string',
                '--name', 'daenabrainstorage',
                '--resource-group', 'daena-brain-rg'
            ], capture_output=True, text=True, check=True)
            
            conn_info = json.loads(result.stdout)
            connection_string = conn_info['connectionString']
            
            # Update .env file
            self.update_storage_connection_string(connection_string)
            
            print("   ✅ Got storage connection string")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to get connection string: {e}")
            return False
        
        return True
    
    def update_storage_connection_string(self, connection_string):
        """Update .env file with storage connection string"""
        env_file = Path("../.env_azure_openai")
        
        try:
            with open(env_file, 'r') as f:
                content = f.read()
            
            # Replace placeholder with real connection string
            content = content.replace(
                'AZURE_STORAGE_CONNECTION_STRING=your_azure_storage_connection_string_here',
                f"AZURE_STORAGE_CONNECTION_STRING={connection_string}"
            )
            
            with open(env_file, 'w') as f:
                f.write(content)
            
            print("✅ Updated .env file with storage connection string")
            
        except Exception as e:
            print(f"❌ Error updating .env file: {e}")
    
    def setup_complete(self):
        """Complete Azure setup"""
        print("🚀 ULTIMATE AZURE SETUP FOR DAENA BRAIN")
        print("=" * 60)
        print(f"👤 Owner: {self.owner_email}")
        print(f"📊 Subscription: {self.subscription_id}")
        print(f"🏢 Tenant: {self.tenant_id}")
        print()
        
        # Step 1: Install Azure CLI
        if not self.check_azure_cli():
            print("🔧 Azure CLI not found. Installing...")
            
            if not self.install_azure_cli_automatic():
                print("❌ Automatic installation failed")
                
                if not self.provide_manual_installation():
                    return False
        
        # Step 2: Login to Azure
        print("\n🔐 Logging into Azure...")
        if not self.login_to_azure():
            print("❌ Failed to login to Azure")
            return False
        
        # Step 3: Create service principal
        print("\n🔑 Creating service principal...")
        sp_info = self.create_service_principal()
        if not sp_info:
            print("❌ Failed to create service principal")
            return False
        
        # Step 4: Create Azure resources
        print("\n📦 Creating Azure resources...")
        if not self.create_azure_resources():
            print("❌ Failed to create Azure resources")
            return False
        
        print("\n🎉 AZURE SETUP COMPLETED!")
        print("=" * 40)
        print("✅ Azure CLI installed")
        print("✅ Azure login successful")
        print("✅ Service principal created")
        print("✅ Resource group created")
        print("✅ Storage account created")
        print("✅ Storage container created")
        print("✅ .env file updated with real credentials")
        
        print("\n🚀 Ready to start training!")
        print("Run: python azure_trainer.py")
        
        return True

def main():
    """Main function"""
    setup = UltimateAzureSetup()
    setup.setup_complete()

if __name__ == "__main__":
    main() 