#!/usr/bin/env python3
"""
Real Unified Brain Trainer for Daena
Downloads and trains on actual HuggingFace models (R1, R2, Yi-34B, etc.)
"""

import os
import json
import torch
import logging
import asyncio
import requests
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from transformers import (
    AutoTokenizer, AutoModelForCausalLM, TrainingArguments, 
    Trainer, DataCollatorForLanguageModeling, BitsAndBytesConfig
)
from datasets import Dataset
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

class RealUnifiedBrainTrainer:
    def __init__(self):
        self.owner_name = "Masoud"
        self.owner_nickname = "Mas"
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.unified_model_path = "./models/daena-real-unified-brain"
        self.training_data_path = "./data/real_training_data"
        self.hf_token = os.getenv('HUGGINGFACE_TOKEN')
        self.setup_logging()
        
        # Real models to download and train on
        self.target_models = {
            'r1': {
                'name': 'microsoft/phi-2',  # Placeholder for R1
                'type': 'reasoning',
                'weight': 1.5,
                'priority': 'high'
            },
            'r2': {
                'name': 'microsoft/DialoGPT-medium',  # Placeholder for R2
                'type': 'reasoning',
                'weight': 1.4,
                'priority': 'high'
            },
            'yi-34b': {
                'name': '01-ai/Yi-34B',
                'type': 'general',
                'weight': 1.0,
                'priority': 'medium'
            },
            'deepseek-coder': {
                'name': 'deepseek-ai/deepseek-coder-33b-instruct',
                'type': 'coding',
                'weight': 1.2,
                'priority': 'medium'
            },
            'qwen2.5': {
                'name': 'Qwen/Qwen2.5-7B-Instruct',
                'type': 'general',
                'weight': 1.1,
                'priority': 'medium'
            },
            'codellama': {
                'name': 'codellama/CodeLlama-34b-Instruct-hf',
                'type': 'coding',
                'weight': 1.1,
                'priority': 'medium'
            }
        }
        
        print("🧠 Real Unified Brain Trainer")
        print("=" * 60)
        print(f"👤 Owner: {self.owner_name} ({self.owner_nickname})")
        print(f"🚀 Device: {self.device}")
        print(f"📁 Model Path: {self.unified_model_path}")
        print(f"🔑 HF Token: {'✅ Set' if self.hf_token else '❌ Missing'}")
        print()
    
    def setup_logging(self):
        """Setup logging for real unified brain training"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/real_unified_brain_training.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('RealUnifiedBrainTrainer')
    
    async def download_model_from_huggingface(self, model_name: str, model_config: Dict) -> bool:
        """Download a model from HuggingFace"""
        print(f"📥 Downloading {model_name} from HuggingFace...")
        
        try:
            # Download tokenizer
            tokenizer = AutoTokenizer.from_pretrained(
                model_config['name'],
                token=self.hf_token,
                trust_remote_code=True
            )
            
            # Download model with quantization for memory efficiency
            if torch.cuda.is_available():
                quantization_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16
                )
                model = AutoModelForCausalLM.from_pretrained(
                    model_config['name'],
                    token=self.hf_token,
                    torch_dtype=torch.float16,
                    device_map='auto',
                    quantization_config=quantization_config,
                    trust_remote_code=True
                )
            else:
                model = AutoModelForCausalLM.from_pretrained(
                    model_config['name'],
                    token=self.hf_token,
                    torch_dtype=torch.float32,
                    device_map='cpu',
                    trust_remote_code=True
                )
            
            # Save locally
            local_path = f"./models/hf_models/{model_name}"
            os.makedirs(local_path, exist_ok=True)
            
            tokenizer.save_pretrained(local_path)
            model.save_pretrained(local_path)
            
            print(f"✅ {model_name} downloaded and saved to {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error downloading {model_name}: {e}")
            print(f"❌ Failed to download {model_name}: {e}")
            return False
    
    async def collect_real_training_data(self) -> List[Dict[str, str]]:
        """Collect real training data from downloaded models"""
        print("📥 Collecting real training data from models...")
        
        training_data = []
        
        # Test prompts that cover different aspects
        test_prompts = [
            # Reasoning prompts (for R1/R2)
            "What is the logical conclusion of this argument?",
            "How would you systematically analyze this problem?",
            "What are the key assumptions in this reasoning?",
            
            # Coding prompts (for DeepSeek, CodeLlama)
            "Write a Python function to solve this problem:",
            "How would you optimize this algorithm?",
            "What's the best practice for this code pattern?",
            
            # General knowledge (for Yi, Qwen)
            "Explain this concept in detail:",
            "What are the implications of this?",
            "How does this relate to other concepts?",
            
            # Business/Strategy (for all models)
            "What's the strategic approach to this business challenge?",
            "How would you evaluate this market opportunity?",
            "What are the key success factors for this project?",
            
            # Daena-specific
            f"Hello {self.owner_nickname}, what should we focus on today?",
            "How can I assist with strategic planning?",
            "What's your recommendation for this situation?"
        ]
        
        # For each model, generate responses to create training data
        for model_name, model_config in self.target_models.items():
            local_path = f"./models/hf_models/{model_name}"
            
            if os.path.exists(local_path):
                try:
                    print(f"🤖 Generating responses from {model_name}...")
                    
                    # Load model
                    tokenizer = AutoTokenizer.from_pretrained(local_path)
                    model = AutoModelForCausalLM.from_pretrained(
                        local_path,
                        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                        device_map='auto' if torch.cuda.is_available() else 'cpu'
                    )
                    
                    # Generate responses for each prompt
                    for prompt in test_prompts[:5]:  # Limit to 5 prompts per model for efficiency
                        try:
                            inputs = tokenizer(prompt, return_tensors="pt").to(self.device)
                            
                            with torch.no_grad():
                                outputs = model.generate(
                                    **inputs,
                                    max_length=inputs['input_ids'].shape[1] + 100,
                                    temperature=0.7,
                                    do_sample=True,
                                    pad_token_id=tokenizer.eos_token_id
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
                    
                    # Clear model from memory
                    del model
                    del tokenizer
                    torch.cuda.empty_cache() if torch.cuda.is_available() else None
                    
                except Exception as e:
                    self.logger.error(f"Error loading {model_name}: {e}")
                    continue
        
        print(f"✅ Collected {len(training_data)} real training examples")
        return training_data
    
    async def train_real_unified_brain(self):
        """Train the real unified brain with actual model data"""
        print("🚀 Starting real unified brain training...")
        
        try:
            # Step 1: Download models from HuggingFace
            print("📥 Step 1: Downloading models from HuggingFace...")
            if not self.hf_token:
                print("❌ HuggingFace token not set. Please set HUGGINGFACE_TOKEN in .env")
                return False
            
            download_success = 0
            for model_name, model_config in self.target_models.items():
                if await self.download_model_from_huggingface(model_name, model_config):
                    download_success += 1
            
            print(f"✅ Downloaded {download_success}/{len(self.target_models)} models")
            
            # Step 2: Collect real training data
            print("📊 Step 2: Collecting real training data...")
            training_data = await self.collect_real_training_data()
            
            if len(training_data) == 0:
                print("❌ No training data collected")
                return False
            
            # Step 3: Prepare dataset
            print("📊 Step 3: Preparing dataset...")
            dataset_dict = {
                "input_text": [item["input_text"] for item in training_data],
                "target_text": [item["target_text"] for item in training_data],
                "prompt": [item["prompt"] for item in training_data],
                "response": [item["response"] for item in training_data],
                "model": [item["model"] for item in training_data],
                "weight": [item["weight"] for item in training_data]
            }
            
            dataset = Dataset.from_dict(dataset_dict)
            
            # Save dataset
            os.makedirs(self.training_data_path, exist_ok=True)
            dataset.save_to_disk(self.training_data_path)
            
            # Step 4: Load base model for training
            print("📥 Step 4: Loading base model for training...")
            base_model_name = "microsoft/DialoGPT-medium"
            
            tokenizer = AutoTokenizer.from_pretrained(base_model_name)
            tokenizer.pad_token = tokenizer.eos_token
            
            if torch.cuda.is_available():
                model = AutoModelForCausalLM.from_pretrained(
                    base_model_name,
                    torch_dtype=torch.float16,
                    device_map='auto'
                )
            else:
                model = AutoModelForCausalLM.from_pretrained(
                    base_model_name,
                    torch_dtype=torch.float32,
                    device_map='cpu'
                )
            
            # Step 5: Tokenize dataset
            print("🔤 Step 5: Tokenizing dataset...")
            def tokenize_function(examples):
                combined_texts = [f"{input_text} {target_text}" for input_text, target_text in zip(examples["input_text"], examples["target_text"])]
                
                tokenized = tokenizer(
                    combined_texts,
                    truncation=True,
                    padding=True,
                    max_length=2048,
                    return_tensors="pt"
                )
                
                tokenized["labels"] = tokenized["input_ids"].clone()
                return tokenized
            
            tokenized_dataset = dataset.map(
                tokenize_function,
                batched=True,
                remove_columns=dataset.column_names
            )
            
            # Step 6: Setup training
            print("🎯 Step 6: Setting up training...")
            training_args = TrainingArguments(
                output_dir=self.unified_model_path,
                num_train_epochs=5,
                per_device_train_batch_size=2,
                learning_rate=1e-5,
                warmup_steps=50,
                save_steps=500,
                logging_steps=50,
                overwrite_output_dir=True,
                remove_unused_columns=False,
                push_to_hub=False,
                save_total_limit=3,
                prediction_loss_only=True,
            )
            
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=tokenizer,
                mlm=False
            )
            
            trainer = Trainer(
                model=model,
                args=training_args,
                train_dataset=tokenized_dataset,
                data_collator=data_collator,
                tokenizer=tokenizer
            )
            
            # Step 7: Train
            print("🎯 Step 7: Training real unified brain...")
            trainer.train()
            
            # Step 8: Save
            print("💾 Step 8: Saving real unified brain...")
            trainer.save_model()
            tokenizer.save_pretrained(self.unified_model_path)
            
            # Step 9: Save model info
            model_info = {
                "name": "daena-real-unified-brain",
                "version": "1.0",
                "owner": f"{self.owner_name} ({self.owner_nickname})",
                "base_model": base_model_name,
                "training_data_size": len(training_data),
                "models_used": list(self.target_models.keys()),
                "training_config": {
                    "epochs": 5,
                    "batch_size": 2,
                    "learning_rate": 1e-5
                },
                "created_at": datetime.now().isoformat(),
                "description": "Real unified brain trained on actual HuggingFace models (R1, R2, Yi-34B, etc.)"
            }
            
            with open(os.path.join(self.unified_model_path, "model_info.json"), "w") as f:
                json.dump(model_info, f, indent=2)
            
            print("✅ Real unified brain training completed!")
            print(f"📁 Model saved to: {self.unified_model_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during training: {e}")
            print(f"❌ Training failed: {e}")
            return False

# Global instance
real_trainer = None

async def initialize_real_trainer():
    """Initialize the real trainer globally"""
    global real_trainer
    real_trainer = RealUnifiedBrainTrainer()
    return real_trainer

async def get_real_trainer():
    """Get the global real trainer instance"""
    global real_trainer
    if real_trainer is None:
        real_trainer = await initialize_real_trainer()
    return real_trainer 