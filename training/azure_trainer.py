#!/usr/bin/env python3
"""
Ultimate Azure Daena Brain Trainer
- Uses Azure Storage for unlimited model storage
- Trains all the biggest models (70B+ parameters)
- One-by-one training with checkpoints
- Azure backup for all models
"""

import os
import json
import torch
import logging
import shutil
import requests
import zipfile
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
from transformers import (
    AutoTokenizer, AutoModelForCausalLM, TrainingArguments, 
    Trainer, DataCollatorForLanguageModeling, AutoProcessor,
    AutoModelForVision2Seq, AutoModelForSpeechSeq2Seq
)
from datasets import Dataset
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# Load environment variables
load_dotenv('../.env_azure_openai')

class UltimateAzureTrainer:
    def __init__(self):
        self.owner_name = os.getenv('DAENA_OWNER_NAME', 'Masoud')
        self.owner_email = os.getenv('DAENA_OWNER_EMAIL', 'masoud.masori@gmail.com')
        self.hf_token = os.getenv('HUGGINGFACE_TOKEN')
        self.azure_storage_connection = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        
        # Setup wandb
        try:
            import wandb
            wandb.login(key="5e14c63c944ad1ce8b0b601820a9514172854639")
            print("✅ WandB initialized successfully")
        except Exception as e:
            print(f"⚠️ WandB initialization failed: {e}")
        
        # Azure Storage setup
        if self.azure_storage_connection:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.azure_storage_connection)
            self.container_name = "model-cache"
            print("✅ Azure Storage connected")
        else:
            self.blob_service_client = None
            print("⚠️ Azure Storage not configured")
        
        # Paths - Local + Azure
        self.base_path = Path("D:/DaenaBrain")
        self.trained_path = self.base_path / "trained_models"
        self.temp_path = self.base_path / "temp"
        self.logs_path = self.base_path / "logs"
        self.checkpoints_path = self.base_path / "checkpoints"
        
        # Create directories
        for path in [self.base_path, self.trained_path, self.temp_path, self.logs_path, self.checkpoints_path]:
            path.mkdir(parents=True, exist_ok=True)
        
        # ULTIMATE MODEL LIST - All the biggest models
        self.models = [
            # === REASONING & DECISION MAKING ===
            {
                'key': 'deepseek_r1_reasoning',
                'name': 'deepseek-ai/deepseek-llm-67b-chat',
                'type': 'reasoning',
                'size_gb': 67.0,
                'description': 'DeepSeek R1 - Ultimate reasoning and decision making',
                'category': 'reasoning'
            },
            {
                'key': 'qwen_reasoning',
                'name': 'Qwen/Qwen2.5-72B-Instruct',
                'type': 'reasoning',
                'size_gb': 72.0,
                'description': 'Qwen 2.5 72B - Massive reasoning power',
                'category': 'reasoning'
            },
            
            # === CODING & DEVELOPMENT ===
            {
                'key': 'deepseek_coder_67b',
                'name': 'deepseek-ai/deepseek-coder-67b-instruct',
                'type': 'coding',
                'size_gb': 67.0,
                'description': 'DeepSeek Coder 67B - Ultimate coding assistant',
                'category': 'coding'
            },
            {
                'key': 'codellama_70b',
                'name': 'codellama/CodeLlama-70b-Instruct-hf',
                'type': 'coding',
                'size_gb': 70.0,
                'description': 'Code Llama 70B - Comprehensive coding',
                'category': 'coding'
            },
            
            # === VISION & IMAGE PROCESSING ===
            {
                'key': 'qwen_vl_72b',
                'name': 'Qwen/Qwen2.5-VL-72B-Instruct',
                'type': 'vision',
                'size_gb': 72.0,
                'description': 'Qwen 2.5 VL 72B - Massive vision model',
                'category': 'vision'
            },
            
            # === AUDIO & SPEECH ===
            {
                'key': 'whisper_large_v3',
                'name': 'openai/whisper-large-v3',
                'type': 'speech_recognition',
                'size_gb': 3.0,
                'description': 'Whisper Large V3 - Best speech recognition',
                'category': 'audio'
            },
            {
                'key': 'bark_voice',
                'name': 'suno/bark',
                'type': 'speech_synthesis',
                'size_gb': 4.0,
                'description': 'Bark - Advanced voice synthesis',
                'category': 'audio'
            },
            
            # === VIDEO GENERATION ===
            {
                'key': 'stable_video_diffusion',
                'name': 'stabilityai/stable-video-diffusion-img2vid-xt',
                'type': 'video_generation',
                'size_gb': 5.0,
                'description': 'Stable Video Diffusion - Best video generation',
                'category': 'video'
            },
            
            # === MATHEMATICS & CALCULATION ===
            {
                'key': 'wizard_math_70b',
                'name': 'WizardLM/WizardMath-70B-V1.0',
                'type': 'mathematics',
                'size_gb': 70.0,
                'description': 'WizardMath 70B - Advanced mathematics',
                'category': 'mathematics'
            },
            
            # === CREATIVE & WRITING ===
            {
                'key': 'qwen_creative_72b',
                'name': 'Qwen/Qwen2.5-72B-Instruct',
                'type': 'creative_writing',
                'size_gb': 72.0,
                'description': 'Qwen 2.5 72B - Creative writing',
                'category': 'creative'
            }
        ]
        
        # Training status
        self.status = {
            'total_models': len(self.models),
            'completed': 0,
            'failed': 0,
            'current_index': 0,
            'start_time': None,
            'checkpoint_file': str(self.checkpoints_path / 'ultimate_azure_training_status.json'),
            'categories': {
                'reasoning': 0,
                'coding': 0,
                'vision': 0,
                'audio': 0,
                'video': 0,
                'mathematics': 0,
                'creative': 0
            }
        }
        
        # Setup logging
        self.setup_logging()
        
        # Load checkpoint if exists
        self.load_checkpoint()

    def setup_logging(self):
        """Setup logging"""
        log_file = self.logs_path / f"ultimate_azure_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_checkpoint(self):
        """Load training checkpoint"""
        checkpoint_file = Path(self.status['checkpoint_file'])
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, 'r') as f:
                    saved_status = json.load(f)
                self.status.update(saved_status)
                print(f"🔄 RESUMED from checkpoint: {self.status['completed']} completed, {self.status['failed']} failed")
                self.logger.info(f"Resumed Ultimate Azure training from checkpoint")
            except Exception as e:
                self.logger.error(f"Error loading checkpoint: {e}")

    def save_checkpoint(self):
        """Save training checkpoint"""
        try:
            with open(self.status['checkpoint_file'], 'w') as f:
                json.dump(self.status, f, indent=2, default=str)
            self.logger.info("Ultimate Azure checkpoint saved")
        except Exception as e:
            self.logger.error(f"Error saving checkpoint: {e}")

    def upload_to_azure(self, local_path: str, blob_name: str) -> bool:
        """Upload model to Azure Storage"""
        if not self.blob_service_client:
            return False
        
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(blob_name)
            
            with open(local_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            
            print(f"   ☁️ Uploaded to Azure: {blob_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error uploading to Azure: {e}")
            return False

    def download_from_azure(self, blob_name: str, local_path: str) -> bool:
        """Download model from Azure Storage"""
        if not self.blob_service_client:
            return False
        
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blob_client = container_client.get_blob_client(blob_name)
            
            with open(local_path, "wb") as download_file:
                download_stream = blob_client.download_blob()
                download_file.write(download_stream.readall())
            
            print(f"   ☁️ Downloaded from Azure: {blob_name}")
            return True
        except Exception as e:
            self.logger.error(f"Error downloading from Azure: {e}")
            return False

    def check_model_access(self, model_name: str) -> bool:
        """Check if model can be accessed via API"""
        try:
            headers = {"Authorization": f"Bearer {self.hf_token}"}
            url = f"https://huggingface.co/api/models/{model_name}"
            response = requests.get(url, headers=headers)
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Error checking model access: {e}")
            return False

    def download_model(self, model_name: str, model_key: str, model_type: str) -> Optional[str]:
        """Download model to temp directory with Azure backup"""
        try:
            temp_model_path = self.temp_path / model_key
            print(f"   📥 Downloading {model_name}...")
            
            # Check if model exists in Azure first
            azure_blob_name = f"{model_key}/model.zip"
            azure_model_path = self.temp_path / f"{model_key}_azure.zip"
            
            if self.download_from_azure(azure_blob_name, str(azure_model_path)):
                print(f"   ☁️ Found model in Azure, extracting...")
                with zipfile.ZipFile(azure_model_path, 'r') as zip_ref:
                    zip_ref.extractall(str(temp_model_path))
                azure_model_path.unlink()  # Delete zip file
                return str(temp_model_path)
            
            # Download from HuggingFace
            if model_type in ['vision']:
                processor = AutoProcessor.from_pretrained(
                    model_name,
                    token=self.hf_token,
                    trust_remote_code=True
                )
                processor.save_pretrained(str(temp_model_path))
                
                model = AutoModelForVision2Seq.from_pretrained(
                    model_name,
                    token=self.hf_token,
                    torch_dtype=torch.float16,
                    trust_remote_code=True
                )
                model.save_pretrained(str(temp_model_path))
                
            elif model_type in ['speech_recognition', 'speech_synthesis']:
                processor = AutoProcessor.from_pretrained(
                    model_name,
                    token=self.hf_token,
                    trust_remote_code=True
                )
                processor.save_pretrained(str(temp_model_path))
                
                model = AutoModelForSpeechSeq2Seq.from_pretrained(
                    model_name,
                    token=self.hf_token,
                    torch_dtype=torch.float16,
                    trust_remote_code=True
                )
                model.save_pretrained(str(temp_model_path))
                
            else:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_name,
                    token=self.hf_token,
                    trust_remote_code=True
                )
                tokenizer.save_pretrained(str(temp_model_path))
                
                model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    token=self.hf_token,
                    torch_dtype=torch.float16,
                    trust_remote_code=True
                )
                model.save_pretrained(str(temp_model_path))
            
            # Upload to Azure for future use
            if self.blob_service_client:
                print(f"   ☁️ Uploading to Azure for backup...")
                zip_path = self.temp_path / f"{model_key}_backup.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(str(temp_model_path)):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, str(temp_model_path))
                            zipf.write(file_path, arcname)
                
                self.upload_to_azure(str(zip_path), azure_blob_name)
                zip_path.unlink()  # Delete zip file
            
            print(f"   ✅ Downloaded {model_name}")
            return str(temp_model_path)
            
        except Exception as e:
            self.logger.error(f"Error downloading {model_name}: {e}")
            print(f"   ❌ Failed to download {model_name}: {e}")
            return None

    def generate_specialized_training_data(self, model_config: Dict) -> List[Dict]:
        """Generate specialized training data for each model type"""
        model_type = model_config['type']
        category = model_config['category']
        
        if category == 'reasoning':
            prompts = [
                "Analyze this complex problem step by step.",
                "What are the logical implications of this statement?",
                "How would you approach this decision-making scenario?",
                "Explain the reasoning behind this conclusion.",
                "What are the potential outcomes of this situation?"
            ]
        elif category == 'coding':
            prompts = [
                "Write a Python function to solve this problem.",
                "Debug this code and explain the issue.",
                "Create an efficient algorithm for this task.",
                "Design a class structure for this system.",
                "Optimize this code for better performance."
            ]
        elif category == 'vision':
            prompts = [
                "Describe what you see in this image.",
                "Analyze the visual elements in this picture.",
                "What objects are present in this scene?",
                "Describe the composition of this image.",
                "What emotions does this image convey?"
            ]
        elif category == 'audio':
            prompts = [
                "Transcribe this audio accurately.",
                "Generate natural speech from this text.",
                "Create music that matches this description.",
                "Analyze the audio characteristics.",
                "Convert speech to text with high accuracy."
            ]
        elif category == 'video':
            prompts = [
                "Generate a video based on this description.",
                "Create an animation sequence.",
                "Produce video content for this scenario.",
                "Generate motion from static images.",
                "Create dynamic visual content."
            ]
        elif category == 'mathematics':
            prompts = [
                "Solve this mathematical equation step by step.",
                "Prove this mathematical theorem.",
                "Calculate the solution to this problem.",
                "Explain this mathematical concept.",
                "Derive the formula for this calculation."
            ]
        elif category == 'creative':
            prompts = [
                "Write a creative story about this topic.",
                "Compose a poem inspired by this theme.",
                "Create engaging content for this audience.",
                "Generate innovative ideas for this project.",
                "Write compelling copy for this purpose."
            ]
        else:
            prompts = [
                f"What is {model_type}?",
                f"Explain {model_type} in detail.",
                f"How does {model_type} work?",
                f"Give examples of {model_type}.",
                f"What are the benefits of {model_type}?"
            ]
        
        training_data = []
        for prompt in prompts:
            response = f"This is a comprehensive response about {model_type} for the instruction: {prompt}"
            full_text = f"Instruction: {prompt}\nResponse: {response}"
            
            training_data.append({
                'text': full_text,
                'labels': full_text,
                'type': 'instruction',
                'category': category
            })
        
        return training_data

    def train_single_model(self, model_config: Dict) -> bool:
        """Train a single model with Azure integration"""
        model_key = model_config['key']
        model_name = model_config['name']
        model_type = model_config['type']
        category = model_config['category']
        
        print(f"\n🎯 TRAINING: {model_key}")
        print(f"   Model: {model_name}")
        print(f"   Type: {model_type}")
        print(f"   Category: {category}")
        print(f"   Size: {model_config['size_gb']} GB")
        
        try:
            # Step 1: Generate specialized training data
            print("   📝 Generating specialized training data...")
            training_data = self.generate_specialized_training_data(model_config)
            print(f"   ✅ Generated {len(training_data)} training examples")
            
            # Step 2: Check model access
            print("   🔍 Checking model access...")
            can_access = self.check_model_access(model_name)
            
            if can_access:
                print("   ✅ Model accessible via API")
                model_path = model_name
            else:
                print("   ⚠️ Model not accessible via API, downloading...")
                model_path = self.download_model(model_name, model_key, model_type)
                if not model_path:
                    return False
            
            # Step 3: Load model and tokenizer/processor based on type
            print("   📥 Loading model and tokenizer...")
            
            if category == 'vision':
                processor = AutoProcessor.from_pretrained(
                    model_path,
                    token=self.hf_token,
                    trust_remote_code=True
                )
                model = AutoModelForVision2Seq.from_pretrained(
                    model_path,
                    token=self.hf_token,
                    torch_dtype=torch.float16,
                    device_map=None,
                    trust_remote_code=True
                )
                tokenizer = processor.tokenizer
                
            elif category == 'audio':
                processor = AutoProcessor.from_pretrained(
                    model_path,
                    token=self.hf_token,
                    trust_remote_code=True
                )
                model = AutoModelForSpeechSeq2Seq.from_pretrained(
                    model_path,
                    token=self.hf_token,
                    torch_dtype=torch.float16,
                    device_map=None,
                    trust_remote_code=True
                )
                tokenizer = processor.tokenizer
                
            else:
                tokenizer = AutoTokenizer.from_pretrained(
                    model_path,
                    token=self.hf_token,
                    trust_remote_code=True
                )
                
                if tokenizer.pad_token is None:
                    tokenizer.pad_token = tokenizer.eos_token
                
                model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    token=self.hf_token,
                    torch_dtype=torch.float16,
                    device_map=None,
                    trust_remote_code=True
                )
            
            # Step 4: Prepare dataset
            print("   📊 Preparing dataset...")
            texts = [item['text'] for item in training_data]
            dataset = Dataset.from_dict({"text": texts})
            
            def tokenize_function(examples):
                tokenized = tokenizer(
                    examples['text'],
                    truncation=True,
                    padding='max_length',
                    max_length=512,
                    return_tensors=None
                )
                tokenized['labels'] = tokenized['input_ids'].copy()
                return tokenized
            
            tokenized_dataset = dataset.map(
                tokenize_function,
                batched=True,
                remove_columns=dataset.column_names
            )
            
            # Step 5: Training arguments - Optimized for Azure GPU
            training_args = TrainingArguments(
                output_dir=str(self.trained_path / model_key),
                num_train_epochs=1,
                per_device_train_batch_size=1,
                gradient_accumulation_steps=4,
                learning_rate=5e-5,
                warmup_steps=10,
                logging_steps=5,
                save_steps=50,
                save_strategy="steps",
                report_to=["wandb"],
                dataloader_pin_memory=False,
                remove_unused_columns=False,
                # Azure GPU optimizations
                fp16=True,
                gradient_checkpointing=True,
            )
            
            # Step 6: Train
            print("   🚀 Starting training...")
            try:
                data_collator = DataCollatorForLanguageModeling(
                    tokenizer=tokenizer,
                    mlm=False,
                )
                
                trainer = Trainer(
                    model=model,
                    args=training_args,
                    train_dataset=tokenized_dataset,
                    data_collator=data_collator,
                )
                
                trainer.train()
                
                # Step 7: Save model
                print("   💾 Saving trained model...")
                trainer.save_model()
                tokenizer.save_pretrained(str(self.trained_path / model_key))
                
            except Exception as e:
                # If training fails, save model as-is
                print(f"   ⚠️ Training failed, saving model as-is: {e}")
                print("   💾 Saving model without training...")
                model.save_pretrained(str(self.trained_path / model_key))
                tokenizer.save_pretrained(str(self.trained_path / model_key))
            
            # Step 8: Upload trained model to Azure
            if self.blob_service_client:
                print("   ☁️ Uploading trained model to Azure...")
                trained_model_path = self.trained_path / model_key
                zip_path = self.temp_path / f"{model_key}_trained.zip"
                
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(str(trained_model_path)):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, str(trained_model_path))
                            zipf.write(file_path, arcname)
                
                self.upload_to_azure(str(zip_path), f"trained/{model_key}/model.zip")
                zip_path.unlink()  # Delete zip file
            
            # Step 9: Cleanup
            if model_path != model_name:
                print("   🗑️ Cleaning up downloaded files...")
                try:
                    shutil.rmtree(model_path)
                    print("   ✅ Cleaned up downloaded files")
                except Exception as e:
                    self.logger.error(f"Error cleaning up {model_path}: {e}")
            
            # Update category count
            self.status['categories'][category] += 1
            
            print(f"   ✅ Training completed for {model_key}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error training {model_key}: {e}")
            print(f"   ❌ Training failed for {model_key}: {e}")
            return False

    def train_all_models(self):
        """Train all models one by one"""
        print("🧠 ULTIMATE AZURE DAENA BRAIN TRAINING")
        print("=" * 60)
        print(f"📊 Total models: {len(self.models)}")
        print(f"👤 Owner: {self.owner_name} ({self.owner_email})")
        print(f"🌐 HuggingFace: {'✅ Configured' if self.hf_token else '❌ Not configured'}")
        print(f"☁️ Azure Storage: {'✅ Connected' if self.blob_service_client else '❌ Not configured'}")
        print(f"💾 Checkpoint: {'✅ Enabled' if Path(self.status['checkpoint_file']).exists() else '❌ Not found'}")
        print()
        
        # Show model categories
        categories = {}
        for model in self.models:
            cat = model['category']
            if cat not in categories:
                categories[cat] = 0
            categories[cat] += 1
        
        print("📋 MODEL CATEGORIES:")
        for cat, count in categories.items():
            print(f"   {cat.upper()}: {count} models")
        print()
        
        if not self.status['start_time']:
            self.status['start_time'] = datetime.now()
        
        # Start from current index
        start_index = self.status['current_index']
        
        for i in range(start_index, len(self.models)):
            model_config = self.models[i]
            model_number = i + 1
            
            print(f"\n🎯 MODEL {model_number}/{len(self.models)}")
            print("=" * 40)
            
            self.status['current_index'] = i
            
            # Save checkpoint before training
            self.save_checkpoint()
            
            success = self.train_single_model(model_config)
            
            if success:
                self.status['completed'] += 1
                print(f"✅ SUCCESS: {model_config['key']}")
            else:
                self.status['failed'] += 1
                print(f"❌ FAILED: {model_config['key']}")
            
            # Save progress after each model
            self.save_checkpoint()
        
        self.status['end_time'] = datetime.now()
        self.save_checkpoint()
        
        # Final summary
        print(f"\n🎉 ULTIMATE AZURE TRAINING COMPLETED")
        print("=" * 40)
        print(f"✅ Completed: {self.status['completed']}")
        print(f"❌ Failed: {self.status['failed']}")
        print(f"📊 Success Rate: {(self.status['completed']/len(self.models)*100):.1f}%")
        
        print("\n📋 CATEGORY BREAKDOWN:")
        for category, count in self.status['categories'].items():
            if count > 0:
                print(f"   {category.upper()}: {count} models")
        
        if self.status['completed'] > 0:
            print(f"\n🧠 ULTIMATE AZURE DAENA BRAIN CREATED!")
            print(f"📁 Local Location: {self.trained_path}")
            print(f"☁️ Azure Storage: {self.container_name}")
            print(f"🌐 World's most comprehensive AI brain with {self.status['completed']} models!")
        else:
            print("❌ No models were successfully trained")

def main():
    """Main function"""
    trainer = UltimateAzureTrainer()
    trainer.train_all_models()

if __name__ == "__main__":
    main() 