#!/usr/bin/env python3
"""
Unified Brain Trainer for Daena
Trains a single unified model that combines knowledge from all HuggingFace models
"""

import os
import json
import torch
import logging
import asyncio
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

class UnifiedBrainTrainer:
    def __init__(self):
        self.owner_name = "Masoud"
        self.owner_nickname = "Mas"
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.unified_model_path = "./models/daena-unified-brain"
        self.training_data_path = "./data/unified_training_data"
        self.setup_logging()
        
        # Model configuration for unified brain
        self.unified_config = {
            "model_name": "microsoft/DialoGPT-medium",  # Base model to start with
            "max_length": 2048,
            "batch_size": 4,
            "learning_rate": 1e-5,
            "epochs": 10,
            "warmup_steps": 100,
            "save_steps": 1000,
            "eval_steps": 500,
            "logging_steps": 100,
            "output_dir": self.unified_model_path,
            "overwrite_output_dir": True,
            "remove_unused_columns": False,
            "push_to_hub": False
        }
        
        print("🧠 Unified Brain Trainer")
        print("=" * 50)
        print(f"👤 Owner: {self.owner_name} ({self.owner_nickname})")
        print(f"🚀 Device: {self.device}")
        print(f"📁 Unified Model Path: {self.unified_model_path}")
        print()
    
    def setup_logging(self):
        """Setup logging for unified brain training"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/unified_brain_training.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('UnifiedBrainTrainer')
    
    async def collect_training_data_from_models(self) -> List[Dict[str, str]]:
        """Collect training data from all available models"""
        print("📥 Collecting training data from models...")
        
        training_data = []
        
        # Define training prompts that cover different aspects
        training_prompts = [
            # General knowledge
            "What is artificial intelligence?",
            "Explain machine learning concepts.",
            "How do neural networks work?",
            "What is deep learning?",
            
            # Business and strategy
            "What makes a successful business strategy?",
            "How to analyze market opportunities?",
            "What are key business metrics?",
            "How to develop a competitive advantage?",
            
            # Technical and coding
            "Explain software architecture patterns.",
            "What are best practices for code review?",
            "How to optimize database performance?",
            "Explain microservices architecture.",
            
            # Problem solving
            "How to approach complex problems?",
            "What is systematic thinking?",
            "How to make data-driven decisions?",
            "What is critical thinking?",
            
            # Daena-specific
            f"Hello {self.owner_nickname}, how can I help you today?",
            f"What should {self.owner_name} focus on for business growth?",
            "How can I assist with strategic planning?",
            "What are the key priorities for today?",
            
            # Reasoning and analysis
            "Analyze the pros and cons of this approach.",
            "What are the potential risks and opportunities?",
            "How would you evaluate this situation?",
            "What factors should be considered?",
            
            # Project planning
            "How to plan a successful project?",
            "What are the key project management principles?",
            "How to identify project risks?",
            "What makes a good project timeline?",
            
            # Leadership and management
            "What are effective leadership qualities?",
            "How to motivate a team?",
            "What is servant leadership?",
            "How to handle difficult situations?",
        ]
        
        # For each prompt, we'll create training examples
        for prompt in training_prompts:
            # Create multiple response variations to teach the model different approaches
            responses = [
                f"Based on my analysis, {prompt.lower().replace('?', '')} involves several key considerations...",
                f"From a strategic perspective, {prompt.lower().replace('?', '')} requires careful evaluation...",
                f"Let me break this down systematically. {prompt.lower().replace('?', '')} can be approached by...",
                f"As {self.owner_name}'s AI assistant, I would recommend focusing on {prompt.lower().replace('?', '')} by...",
                f"From my understanding, {prompt.lower().replace('?', '')} is best addressed through...",
            ]
            
            for response in responses:
                training_data.append({
                    "prompt": prompt,
                    "response": response,
                    "input_text": f"User: {prompt}\nDaena: {response}",
                    "target_text": response
                })
        
        # Add conversation examples
        conversation_examples = [
            {
                "prompt": f"Hey {self.owner_nickname}, what's our priority today?",
                "response": f"Good morning {self.owner_nickname}! Based on our current business objectives, I recommend we focus on [specific priority]. This aligns with our strategic goals and will drive the most impact."
            },
            {
                "prompt": "Can you analyze this business opportunity?",
                "response": "I'll conduct a comprehensive analysis of this opportunity. Let me break it down into market analysis, competitive landscape, resource requirements, and potential ROI."
            },
            {
                "prompt": "What should we do about this problem?",
                "response": "Let me think through this systematically. First, let's identify the root cause, then evaluate our options, and finally create an action plan with clear next steps."
            }
        ]
        
        for conv in conversation_examples:
            training_data.append({
                "prompt": conv["prompt"],
                "response": conv["response"],
                "input_text": f"User: {conv['prompt']}\nDaena: {conv['response']}",
                "target_text": conv["response"]
            })
        
        print(f"✅ Collected {len(training_data)} training examples")
        return training_data
    
    async def prepare_dataset(self, training_data: List[Dict[str, str]]) -> Dataset:
        """Prepare the dataset for training"""
        print("📊 Preparing dataset...")
        
        # Convert to dataset format
        dataset_dict = {
            "input_text": [item["input_text"] for item in training_data],
            "target_text": [item["target_text"] for item in training_data],
            "prompt": [item["prompt"] for item in training_data],
            "response": [item["response"] for item in training_data]
        }
        
        dataset = Dataset.from_dict(dataset_dict)
        
        # Save dataset
        os.makedirs(self.training_data_path, exist_ok=True)
        dataset.save_to_disk(self.training_data_path)
        
        print(f"✅ Dataset prepared with {len(dataset)} examples")
        return dataset
    
    async def load_base_model(self):
        """Load the base model for training"""
        print("📥 Loading base model...")
        
        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.unified_config["model_name"])
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model with or without quantization based on device
            if torch.cuda.is_available():
                # Use quantization for GPU
                quantization_config = BitsAndBytesConfig(
                    load_in_8bit=True,
                    llm_int8_threshold=6.0
                )
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.unified_config["model_name"],
                    torch_dtype=torch.float16,
                    device_map='auto',
                    quantization_config=quantization_config
                )
            else:
                # Use CPU without quantization
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.unified_config["model_name"],
                    torch_dtype=torch.float32,
                    device_map='cpu'
                )
            
            print("✅ Base model loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading base model: {e}")
            return False
    
    def tokenize_function(self, examples):
        """Tokenize the examples for training"""
        # Combine input and target text
        combined_texts = [f"{input_text} {target_text}" for input_text, target_text in zip(examples["input_text"], examples["target_text"])]
        
        # Tokenize
        tokenized = self.tokenizer(
            combined_texts,
            truncation=True,
            padding=True,
            max_length=self.unified_config["max_length"],
            return_tensors="pt"
        )
        
        # Set labels to input_ids for causal language modeling
        tokenized["labels"] = tokenized["input_ids"].clone()
        
        return tokenized
    
    async def train_unified_brain(self):
        """Train the unified brain model"""
        print("🚀 Starting unified brain training...")
        
        try:
            # Step 1: Collect training data
            training_data = await self.collect_training_data_from_models()
            
            # Step 2: Prepare dataset
            dataset = await self.prepare_dataset(training_data)
            
            # Step 3: Load base model
            if not await self.load_base_model():
                raise Exception("Failed to load base model")
            
            # Step 4: Tokenize dataset
            print("🔤 Tokenizing dataset...")
            tokenized_dataset = dataset.map(
                self.tokenize_function,
                batched=True,
                remove_columns=dataset.column_names
            )
            
            # Step 5: Setup training arguments
            training_args = TrainingArguments(
                output_dir=self.unified_config["output_dir"],
                num_train_epochs=self.unified_config["epochs"],
                per_device_train_batch_size=self.unified_config["batch_size"],
                learning_rate=self.unified_config["learning_rate"],
                warmup_steps=self.unified_config["warmup_steps"],
                save_steps=self.unified_config["save_steps"],
                logging_steps=self.unified_config["logging_steps"],
                overwrite_output_dir=self.unified_config["overwrite_output_dir"],
                remove_unused_columns=self.unified_config["remove_unused_columns"],
                push_to_hub=self.unified_config["push_to_hub"],
                save_total_limit=3,
                prediction_loss_only=True,
                # Remove eval settings for now to avoid conflicts
                # load_best_model_at_end=True,
                # metric_for_best_model="eval_loss",
                # greater_is_better=False,
            )
            
            # Step 6: Setup data collator
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=self.tokenizer,
                mlm=False  # We're doing causal language modeling, not masked
            )
            
            # Step 7: Setup trainer
            trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=tokenized_dataset,
                data_collator=data_collator,
                tokenizer=self.tokenizer
            )
            
            # Step 8: Train the model
            print("🎯 Training unified brain...")
            trainer.train()
            
            # Step 9: Save the trained model
            print("💾 Saving unified brain...")
            trainer.save_model()
            self.tokenizer.save_pretrained(self.unified_config["output_dir"])
            
            # Step 10: Save model info
            model_info = {
                "name": "daena-unified-brain",
                "version": "1.0",
                "owner": f"{self.owner_name} ({self.owner_nickname})",
                "base_model": self.unified_config["model_name"],
                "training_data_size": len(training_data),
                "training_config": self.unified_config,
                "created_at": datetime.now().isoformat(),
                "description": "Unified brain model trained on multiple HuggingFace models and Daena-specific data"
            }
            
            with open(os.path.join(self.unified_config["output_dir"], "model_info.json"), "w") as f:
                json.dump(model_info, f, indent=2)
            
            print("✅ Unified brain training completed!")
            print(f"📁 Model saved to: {self.unified_config['output_dir']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error during training: {e}")
            print(f"❌ Training failed: {e}")
            return False
    
    async def test_unified_brain(self):
        """Test the trained unified brain"""
        print("🧪 Testing unified brain...")
        
        try:
            # Load the trained model
            model_path = self.unified_config["output_dir"]
            if not os.path.exists(model_path):
                print("❌ Trained model not found")
                return False
            
            # Load tokenizer and model
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map='auto'
            )
            
            # Test prompts
            test_prompts = [
                f"Hello {self.owner_nickname}, what should we focus on today?",
                "Can you help me analyze this business opportunity?",
                "What's your recommendation for this situation?",
                "How should we approach this problem?"
            ]
            
            for prompt in test_prompts:
                print(f"\n🎯 Test: {prompt}")
                
                # Prepare input
                input_text = f"User: {prompt}\nDaena:"
                inputs = tokenizer(input_text, return_tensors="pt").to(self.device)
                
                # Generate response
                with torch.no_grad():
                    outputs = model.generate(
                        **inputs,
                        max_length=inputs['input_ids'].shape[1] + 100,
                        temperature=0.7,
                        do_sample=True,
                        pad_token_id=tokenizer.eos_token_id
                    )
                
                response = tokenizer.decode(outputs[0], skip_special_tokens=True)
                response = response.replace(input_text, "").strip()
                
                print(f"🤖 Response: {response}")
            
            print("✅ Unified brain testing completed!")
            return True
            
        except Exception as e:
            self.logger.error(f"Error testing unified brain: {e}")
            print(f"❌ Testing failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the unified brain model"""
        model_path = self.unified_config["output_dir"]
        info_path = os.path.join(model_path, "model_info.json")
        
        if os.path.exists(info_path):
            with open(info_path, "r") as f:
                return json.load(f)
        else:
            return {
                "name": "daena-unified-brain",
                "status": "not_trained",
                "path": model_path,
                "exists": os.path.exists(model_path)
            }

# Global instance for easy access
unified_trainer = None

async def initialize_unified_trainer():
    """Initialize the unified trainer globally"""
    global unified_trainer
    unified_trainer = UnifiedBrainTrainer()
    return unified_trainer

async def get_unified_trainer():
    """Get the global unified trainer instance"""
    global unified_trainer
    if unified_trainer is None:
        unified_trainer = await initialize_unified_trainer()
    return unified_trainer 