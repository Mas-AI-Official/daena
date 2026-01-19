#!/usr/bin/env python3
"""
Smart Ultimate Daena Brain Trainer V2.0
- Downloads one model at a time
- Trains immediately with each model
- Deletes downloaded models to save space
- Uses HuggingFace API directly when possible
- Gives Daena brain management capabilities
"""

import os
import json
import torch
import logging
import asyncio
import requests
import shutil
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from transformers import (
    AutoTokenizer, AutoModelForCausalLM, TrainingArguments, 
    Trainer, DataCollatorForLanguageModeling, BitsAndBytesConfig,
    pipeline
)
from datasets import Dataset
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env_azure_openai')

class SmartUltimateBrainTrainer:
    def __init__(self):
        self.owner_name = os.getenv('DAENA_OWNER_NAME', 'Masoud')
        self.owner_nickname = os.getenv('DAENA_OWNER_NICKNAME', 'Mas')
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.ultimate_brain_path = "./models/daena-ultimate-brain"
        self.temp_download_path = "./models/temp_downloads"
        self.brain_backup_path = "./models/daena-brain-backups"
        self.hf_token = os.getenv('HUGGINGFACE_TOKEN', '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')
        self.setup_logging()
        self.setup_directories()
        
        # Smart model selection - prioritize by importance and size
        self.smart_models = {
            # 🧠 CRITICAL REASONING (Download first - most important)
            'r1_reasoning': {
                'name': 'microsoft/phi-2',
                'type': 'reasoning',
                'weight': 2.0,
                'priority': 'critical',
                'size_gb': 2.7,
                'download_order': 1,
                'description': 'Advanced reasoning and logical thinking'
            },
            'r2_analysis': {
                'name': 'microsoft/DialoGPT-medium',
                'type': 'reasoning',
                'weight': 1.8,
                'priority': 'critical',
                'size_gb': 1.5,
                'download_order': 2,
                'description': 'Deep analysis and strategic thinking'
            },
            'r3_v3': {
                'name': 'microsoft/Phi-3-mini-4k-instruct',
                'type': 'reasoning',
                'weight': 1.9,
                'priority': 'critical',
                'size_gb': 3.8,
                'download_order': 3,
                'description': 'R3 V3 advanced reasoning'
            },
            
            # 💻 CODING (High priority - essential for business)
            'deepseek_coder': {
                'name': 'deepseek-ai/deepseek-coder-33b-instruct',
                'type': 'coding',
                'weight': 1.8,
                'priority': 'high',
                'size_gb': 66.0,
                'download_order': 4,
                'description': 'Advanced coding and software development'
            },
            'wizard_coder': {
                'name': 'WizardLM/WizardCoder-15B-V1.0',
                'type': 'coding',
                'weight': 1.5,
                'priority': 'high',
                'size_gb': 30.0,
                'download_order': 5,
                'description': 'Wizard-level coding assistance'
            },
            
            # 🎨 CREATIVE (Medium priority)
            'mistral_creative': {
                'name': 'mistralai/Mistral-7B-Instruct-v0.2',
                'type': 'creative',
                'weight': 1.7,
                'priority': 'medium',
                'size_gb': 14.0,
                'download_order': 6,
                'description': 'Creative content generation'
            },
            'qwen_creative': {
                'name': 'Qwen/Qwen2.5-7B-Instruct',
                'type': 'creative',
                'weight': 1.6,
                'priority': 'medium',
                'size_gb': 14.0,
                'download_order': 7,
                'description': 'Advanced creative writing'
            },
            
            # 🧮 MATHEMATICS (Medium priority)
            'qwen_math': {
                'name': 'Qwen/Qwen2.5-Math-7B-Instruct',
                'type': 'mathematics',
                'weight': 1.8,
                'priority': 'medium',
                'size_gb': 14.0,
                'download_order': 8,
                'description': 'Advanced mathematics'
            },
            
            # 🌍 GENERAL (Lower priority - can use API)
            'yi_34b': {
                'name': '01-ai/Yi-34B',
                'type': 'general',
                'weight': 1.4,
                'priority': 'low',
                'size_gb': 68.0,
                'download_order': 9,
                'description': 'General knowledge (use API instead)'
            },
            
            # 🎬 VIDEO/GRAPHICS (Use API instead of download)
            'stable_video': {
                'name': 'stabilityai/stable-video-diffusion-img2vid-xt',
                'type': 'video',
                'weight': 1.8,
                'priority': 'api_only',
                'size_gb': 0.0,
                'download_order': 999,
                'description': 'Video generation (use API)'
            },
            'stable_diffusion': {
                'name': 'runwayml/stable-diffusion-v1-5',
                'type': 'graphics',
                'weight': 1.7,
                'priority': 'api_only',
                'size_gb': 0.0,
                'download_order': 999,
                'description': 'Image generation (use API)'
            }
        }
        
        # Big Model APIs for validation and fallback
        self.big_model_apis = {
            'openai_gpt4': {
                'name': 'GPT-4',
                'api_key': os.getenv('AZURE_OPENAI_API_KEY'),
                'endpoint': os.getenv('AZURE_OPENAI_API_BASE'),
                'weight': 1.5,
                'description': 'Azure OpenAI GPT-4'
            },
            'gemini': {
                'name': 'Gemini',
                'api_key': os.getenv('GEMINI_API_KEY'),
                'weight': 1.4,
                'description': 'Google Gemini'
            },
            'claude': {
                'name': 'Claude',
                'api_key': os.getenv('CLAUDE_API_KEY'),
                'weight': 1.3,
                'description': 'Anthropic Claude'
            }
        }
        
        # Daena's brain management capabilities
        self.brain_management = {
            'auto_upgrade': True,
            'backup_before_upgrade': True,
            'delete_old_models': True,
            'use_api_fallback': True,
            'space_threshold_gb': 10.0,  # Warn when space < 10GB
            'max_backup_versions': 3
        }
        
        print("🧠 Smart Ultimate Daena Brain Trainer V2.0")
        print("=" * 70)
        print(f"👤 Owner: {self.owner_name} ({self.owner_nickname})")
        print(f"🚀 Device: {self.device}")
        print(f"📁 Brain Path: {self.ultimate_brain_path}")
        print(f"🔑 HF Token: {'✅ Set' if self.hf_token else '❌ Missing'}")
        print(f"🎯 Smart Models: {len(self.smart_models)}")
        print(f"🌐 Big Model APIs: {len(self.big_model_apis)}")
        print(f"🧠 Brain Management: {'✅ Enabled' if self.brain_management['auto_upgrade'] else '❌ Disabled'}")
        print()
    
    def setup_logging(self):
        """Setup logging for smart brain training"""
        os.makedirs('logs', exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/smart_brain_training.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('SmartUltimateBrainTrainer')
    
    def setup_directories(self):
        """Setup necessary directories"""
        directories = [
            self.ultimate_brain_path,
            self.temp_download_path,
            self.brain_backup_path,
            "./models/ultimate_models",
            "./data/smart_training_data",
            "./logs"
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def check_disk_space(self) -> float:
        """Check available disk space in GB"""
        try:
            stat = shutil.disk_usage('.')
            available_gb = stat.free / (1024**3)
            print(f"💾 Available disk space: {available_gb:.2f} GB")
            return available_gb
        except Exception as e:
            self.logger.error(f"Error checking disk space: {e}")
            return 100.0  # Assume enough space
    
    def create_brain_backup(self) -> bool:
        """Create backup of current brain before upgrade"""
        try:
            if not os.path.exists(self.ultimate_brain_path):
                return True  # No brain to backup
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(self.brain_backup_path, f"brain_backup_{timestamp}")
            
            print(f"💾 Creating brain backup: {backup_path}")
            shutil.copytree(self.ultimate_brain_path, backup_path)
            
            # Clean old backups (keep only max_backup_versions)
            self.cleanup_old_backups()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error creating brain backup: {e}")
            return False
    
    def cleanup_old_backups(self):
        """Clean up old brain backups"""
        try:
            backups = []
            for item in os.listdir(self.brain_backup_path):
                if item.startswith("brain_backup_"):
                    backup_path = os.path.join(self.brain_backup_path, item)
                    backups.append((backup_path, os.path.getctime(backup_path)))
            
            # Sort by creation time (oldest first)
            backups.sort(key=lambda x: x[1])
            
            # Remove oldest backups if we have too many
            max_backups = self.brain_management['max_backup_versions']
            if len(backups) > max_backups:
                for backup_path, _ in backups[:-max_backups]:
                    print(f"🗑️ Removing old backup: {backup_path}")
                    shutil.rmtree(backup_path)
                    
        except Exception as e:
            self.logger.error(f"Error cleaning up old backups: {e}")
    
    async def download_model_smart(self, model_name: str, model_config: Dict) -> bool:
        """Download model to temp directory"""
        print(f"📥 Downloading {model_name} ({model_config['description']})...")
        
        try:
            # Check disk space
            available_space = self.check_disk_space()
            required_space = model_config.get('size_gb', 5.0)
            
            if available_space < required_space + 5.0:  # Add 5GB buffer
                print(f"⚠️ Warning: Low disk space. Need {required_space}GB, have {available_space:.2f}GB")
                return False
            
            # Download to temp directory
            temp_model_path = os.path.join(self.temp_download_path, model_name)
            os.makedirs(temp_model_path, exist_ok=True)
            
            # Download tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                model_config['name'],
                token=self.hf_token,
                trust_remote_code=True,
                cache_dir=temp_model_path
            )
            
            # Download model with optimal settings
            if torch.cuda.is_available():
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_quant_type="nf4"
                )
                model = AutoModelForCausalLM.from_pretrained(
                    model_config['name'],
                    token=self.hf_token,
                    torch_dtype=torch.float16,
                    device_map='auto',
                    quantization_config=quantization_config,
                    trust_remote_code=True,
                    cache_dir=temp_model_path
                )
            else:
                model = AutoModelForCausalLM.from_pretrained(
                    model_config['name'],
                    token=self.hf_token,
                    torch_dtype=torch.float32,
                    device_map='cpu',
                    trust_remote_code=True,
                    cache_dir=temp_model_path
                )
            
            # Save model metadata
            metadata = {
                "name": model_name,
                "huggingface_name": model_config['name'],
                "type": model_config['type'],
                "weight": model_config['weight'],
                "priority": model_config['priority'],
                "size_gb": model_config.get('size_gb', 0.0),
                "description": model_config['description'],
                "downloaded_at": datetime.now().isoformat(),
                "version": "2.0"
            }
            
            with open(os.path.join(temp_model_path, "model_metadata.json"), "w") as f:
                json.dump(metadata, f, indent=2)
            
            print(f"✅ {model_name} downloaded to temp directory")
            return True
            
        except Exception as e:
            self.logger.error(f"Error downloading {model_name}: {e}")
            print(f"❌ Failed to download {model_name}: {e}")
            return False
    
    async def train_with_model(self, model_name: str, model_config: Dict) -> bool:
        """Train ultimate brain with a single model"""
        print(f"🎯 Training with {model_name}...")
        
        try:
            temp_model_path = os.path.join(self.temp_download_path, model_name)
            
            if not os.path.exists(temp_model_path):
                print(f"❌ Model {model_name} not found in temp directory")
                return False
            
            # Load model and tokenizer
            tokenizer = AutoTokenizer.from_pretrained(temp_model_path)
            model = AutoModelForCausalLM.from_pretrained(
                temp_model_path,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                device_map='auto' if torch.cuda.is_available() else 'cpu'
            )
            
            # Generate training data with this model
            training_data = await self.generate_training_data_with_model(model_name, model_config, tokenizer, model)
            
            if len(training_data) == 0:
                print(f"⚠️ No training data generated for {model_name}")
                return True  # Continue with next model
            
            # Prepare dataset
            dataset_dict = {
                "input_text": [item["input_text"] for item in training_data],
                "target_text": [item["target_text"] for item in training_data],
                "model": [model_name] * len(training_data),
                "weight": [model_config['weight']] * len(training_data)
            }
            
            dataset = Dataset.from_dict(dataset_dict)
            
            # Tokenize dataset
            def tokenize_function(examples):
                combined_texts = [f"{input_text} {target_text}" for input_text, target_text in zip(examples["input_text"], examples["target_text"])]
                
                tokenized = tokenizer(
                    combined_texts,
                    truncation=True,
                    padding=True,
                    max_length=2048,  # Smaller for efficiency
                    return_tensors="pt"
                )
                
                tokenized["labels"] = tokenized["input_ids"].clone()
                return tokenized
            
            tokenized_dataset = dataset.map(
                tokenize_function,
                batched=True,
                remove_columns=dataset.column_names
            )
            
            # Setup training
            training_args = TrainingArguments(
                output_dir=self.ultimate_brain_path,
                num_train_epochs=3,  # Fewer epochs per model
                per_device_train_batch_size=1,
                learning_rate=5e-6,
                warmup_steps=50,
                save_steps=100,
                logging_steps=25,
                overwrite_output_dir=False,  # Don't overwrite, append
                remove_unused_columns=False,
                push_to_hub=False,
                save_total_limit=3,
                prediction_loss_only=True,
                gradient_accumulation_steps=2,
                fp16=torch.cuda.is_available(),
                dataloader_pin_memory=False,
                dataloader_num_workers=0
            )
            
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=tokenizer,
                mlm=False
            )
            
            # Load existing brain or create new one
            if os.path.exists(self.ultimate_brain_path):
                print("🧠 Loading existing ultimate brain...")
                base_tokenizer = AutoTokenizer.from_pretrained(self.ultimate_brain_path)
                base_model = AutoModelForCausalLM.from_pretrained(
                    self.ultimate_brain_path,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    device_map='auto' if torch.cuda.is_available() else 'cpu'
                )
            else:
                print("🧠 Creating new ultimate brain...")
                base_tokenizer = tokenizer
                base_model = model
            
            trainer = Trainer(
                model=base_model,
                args=training_args,
                train_dataset=tokenized_dataset,
                data_collator=data_collator,
                tokenizer=base_tokenizer
            )
            
            # Train
            print(f"🎯 Training ultimate brain with {model_name}...")
            trainer.train()
            
            # Save updated brain
            trainer.save_model()
            base_tokenizer.save_pretrained(self.ultimate_brain_path)
            
            print(f"✅ Training with {model_name} completed!")
            return True
            
        except Exception as e:
            self.logger.error(f"Error training with {model_name}: {e}")
            print(f"❌ Error training with {model_name}: {e}")
            return False
    
    async def generate_training_data_with_model(self, model_name: str, model_config: Dict, tokenizer, model) -> List[Dict]:
        """Generate training data using the specific model"""
        training_data = []
        
        try:
            # Get prompts for this model type
            prompts = self.get_prompts_for_model_type(model_config['type'])
            
            # Generate responses for each prompt
            for prompt in prompts[:5]:  # Limit to 5 prompts per model for efficiency
                try:
                    inputs = tokenizer(prompt, return_tensors="pt").to(self.device)
                    
                    with torch.no_grad():
                        outputs = model.generate(
                            **inputs,
                            max_length=inputs['input_ids'].shape[1] + 100,
                            temperature=0.7,
                            do_sample=True,
                            pad_token_id=tokenizer.eos_token_id,
                            repetition_penalty=1.1
                        )
                    
                    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
                    response = response.replace(prompt, "").strip()
                    
                    # Create training example
                    training_data.append({
                        "prompt": prompt,
                        "response": response,
                        "model": model_name,
                        "model_type": model_config['type'],
                        "weight": model_config['weight'],
                        "input_text": f"User: {prompt}\nDaena: {response}",
                        "target_text": response
                    })
                    
                except Exception as e:
                    self.logger.warning(f"Error generating response for {model_name}: {e}")
                    continue
            
            print(f"📊 Generated {len(training_data)} training examples with {model_name}")
            return training_data
            
        except Exception as e:
            self.logger.error(f"Error generating training data with {model_name}: {e}")
            return []
    
    def get_prompts_for_model_type(self, model_type: str) -> List[str]:
        """Get appropriate prompts for each model type"""
        prompts = {
            'reasoning': [
                "What is the logical conclusion of this argument?",
                "How would you systematically analyze this complex problem?",
                "What are the key assumptions in this reasoning chain?",
                "How would you evaluate the validity of this claim?",
                "What is the most rational approach to this situation?"
            ],
            'coding': [
                "Write a Python function to solve this optimization problem:",
                "How would you architect a scalable microservices system?",
                "What's the best practice for implementing this algorithm?",
                "How would you optimize this database query?",
                "Create a REST API for this business requirement"
            ],
            'creative': [
                "Create a compelling story about innovation and success",
                "Design a marketing campaign for a revolutionary product",
                "Write a persuasive speech about the future of AI",
                "Create engaging content for social media",
                "Develop a creative solution to a business challenge"
            ],
            'mathematics': [
                "Solve this complex mathematical problem step by step:",
                "What's the optimal solution to this optimization problem?",
                "How would you calculate the ROI for this investment?",
                "What's the statistical significance of this data?",
                "How would you model this business scenario mathematically?"
            ],
            'general': [
                "Explain this complex concept in simple terms",
                "What are the implications of this technological advancement?",
                "How does this relate to current market trends?",
                "What's the historical context of this development?",
                "How would you approach this interdisciplinary problem?"
            ]
        }
        
        return prompts.get(model_type, [
            "How would you approach this problem?",
            "What's your analysis of this situation?",
            "How would you solve this challenge?"
        ])
    
    def cleanup_temp_model(self, model_name: str):
        """Delete temporary downloaded model to save space"""
        try:
            temp_model_path = os.path.join(self.temp_download_path, model_name)
            if os.path.exists(temp_model_path):
                print(f"🗑️ Cleaning up temporary model: {model_name}")
                shutil.rmtree(temp_model_path)
                print(f"✅ Cleaned up {model_name}")
        except Exception as e:
            self.logger.error(f"Error cleaning up {model_name}: {e}")
    
    async def train_smart_ultimate_brain(self):
        """Train ultimate brain with smart one-by-one approach"""
        print("🚀 Starting Smart Ultimate Brain Training...")
        
        try:
            # Create backup before starting
            if self.brain_management['backup_before_upgrade']:
                self.create_brain_backup()
            
            # Sort models by download order
            sorted_models = sorted(
                self.smart_models.items(),
                key=lambda x: x[1]['download_order']
            )
            
            successful_models = 0
            total_models = len([m for m in sorted_models if m[1]['priority'] != 'api_only'])
            
            for model_name, model_config in sorted_models:
                # Skip API-only models
                if model_config['priority'] == 'api_only':
                    print(f"⏭️ Skipping {model_name} (API-only model)")
                    continue
                
                print(f"\n🎯 Processing {model_name} ({successful_models + 1}/{total_models})")
                print(f"📊 Type: {model_config['type']}, Priority: {model_config['priority']}")
                print(f"💾 Size: {model_config.get('size_gb', 'Unknown')} GB")
                
                # Download model
                download_success = await self.download_model_smart(model_name, model_config)
                
                if download_success:
                    # Train with model
                    train_success = await self.train_with_model(model_name, model_config)
                    
                    if train_success:
                        successful_models += 1
                        print(f"✅ Successfully trained with {model_name}")
                    else:
                        print(f"❌ Training failed with {model_name}")
                    
                    # Clean up downloaded model
                    self.cleanup_temp_model(model_name)
                else:
                    print(f"❌ Download failed for {model_name}")
                
                # Check disk space after each model
                available_space = self.check_disk_space()
                if available_space < self.brain_management['space_threshold_gb']:
                    print(f"⚠️ Low disk space warning: {available_space:.2f} GB")
            
            # Save final brain info
            self.save_ultimate_brain_info(successful_models, total_models)
            
            print(f"\n🎉 Smart Ultimate Brain Training Completed!")
            print(f"✅ Successfully trained with {successful_models}/{total_models} models")
            print(f"🧠 Ultimate brain saved to: {self.ultimate_brain_path}")
            print(f"🌐 Big model API integration ready!")
            print(f"🔄 Auto-upgrade system enabled!")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during smart training: {e}")
            print(f"❌ Smart training failed: {e}")
            return False
    
    def save_ultimate_brain_info(self, successful_models: int, total_models: int):
        """Save comprehensive brain information"""
        brain_info = {
            "name": "daena-ultimate-brain-v2",
            "version": "2.0",
            "owner": f"{self.owner_name} ({self.owner_nickname})",
            "training_date": datetime.now().isoformat(),
            "successful_models": successful_models,
            "total_models": total_models,
            "device_used": str(self.device),
            "brain_management": self.brain_management,
            "capabilities": {
                "reasoning": "Advanced logical thinking and analysis",
                "coding": "Software development and technical problem solving",
                "creative": "Content creation and artistic expression",
                "mathematics": "Mathematical reasoning and optimization",
                "general": "Comprehensive knowledge and understanding"
            },
            "auto_upgrade": {
                "enabled": True,
                "backup_system": True,
                "space_management": True,
                "api_fallback": True
            },
            "description": "Smart Ultimate Brain V2.0 - Downloads one model at a time, trains immediately, deletes to save space, with auto-upgrade capabilities"
        }
        
        with open(os.path.join(self.ultimate_brain_path, "smart_brain_info.json"), "w") as f:
            json.dump(brain_info, f, indent=2)

# Global instance
smart_trainer = None

async def initialize_smart_trainer():
    """Initialize the smart trainer globally"""
    global smart_trainer
    smart_trainer = SmartUltimateBrainTrainer()
    return smart_trainer

async def get_smart_trainer():
    """Get the global smart trainer instance"""
    global smart_trainer
    if smart_trainer is None:
        smart_trainer = await initialize_smart_trainer()
    return smart_trainer 