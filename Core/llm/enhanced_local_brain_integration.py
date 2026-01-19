#!/usr/bin/env python3
"""
Enhanced Local Brain Integration for Daena Core
Integrates H: drive models with existing Core consensus engine
"""

import os
import json
import torch
import logging
import asyncio
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from dotenv import load_dotenv

# Import existing Core components
from Core.llm.advanced_model_integration import AdvancedModelIntegration
from Core.llm.voting.vote_engine import vote_on_responses
from Core.llm.fallback.fallback_strategy_kernel import fallback_handler

# Load environment variables
load_dotenv('.env')

class EnhancedLocalBrainIntegration:
    def __init__(self, db_session=None):
        self.owner_name = "Masoud"
        self.owner_nickname = "Mas"
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.models: Dict[str, Any] = {}
        self.model_paths = {}
        self.consensus_threshold = 0.7
        self.deep_search_enabled = False
        self.deep_search_threshold = 0.8  # Confidence threshold for deep search
        
        # Initialize existing Core components
        self.advanced_integration = AdvancedModelIntegration(db_session) if db_session else None
        
        self.setup_logging()
        self.load_h_drive_models()
        self.register_models_with_core()
        
        print("🧠 Enhanced Local Brain Integration")
        print("=" * 50)
        print(f"👤 Owner: {self.owner_name} ({self.owner_nickname})")
        print(f"🚀 Device: {self.device}")
        print(f"📁 H: Drive Models: {len(self.model_paths)} found")
        print(f"🎯 Consensus Threshold: {self.consensus_threshold}")
        print(f"🔍 Deep Search: {'Enabled' if self.deep_search_enabled else 'Disabled'}")
        print()
    
    def setup_logging(self):
        """Setup logging for the enhanced brain"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/enhanced_brain.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('EnhancedLocalBrain')
    
    def load_h_drive_models(self):
        """Load model configurations from H: drive"""
        # Try multiple possible H: drive paths
        h_drive_paths = [
            "H:/Daena/models",
            "H:/models",
            "H:/Daena",
            "H:/",
            "D:/Ideas/Daena/models",  # Fallback to local models
            "./models"  # Current directory models
        ]
        
        h_drive_path = None
        for path in h_drive_paths:
            if os.path.exists(path):
                h_drive_path = path
                self.logger.info(f"Found models directory: {path}")
                break
        
        if not h_drive_path:
            self.logger.warning("No models directory found. Will use fallback to Azure OpenAI.")
            return
        
        # Define model configurations for H: drive
        h_drive_models = {
            'r1': {
                'path': f"{h_drive_path}/r1",
                'weight': 1.5,
                'specialization': 'reasoning',
                'priority': 'high'
            },
            'r2': {
                'path': f"{h_drive_path}/r2", 
                'weight': 1.4,
                'specialization': 'reasoning',
                'priority': 'high'
            },
            'yi-34b': {
                'path': f"{h_drive_path}/yi-34b",
                'weight': 1.0,
                'specialization': 'general',
                'priority': 'medium'
            },
            'deepseek-coder': {
                'path': f"{h_drive_path}/deepseek-coder-33b",
                'weight': 1.2,
                'specialization': 'coding',
                'priority': 'medium'
            },
            'qwen2.5': {
                'path': f"{h_drive_path}/qwen2.5",
                'weight': 1.1,
                'specialization': 'general',
                'priority': 'medium'
            },
            'codellama': {
                'path': f"{h_drive_path}/codellama-34b",
                'weight': 1.1,
                'specialization': 'coding',
                'priority': 'medium'
            },
            'phi-2': {
                'path': f"{h_drive_path}/phi-2",
                'weight': 0.9,
                'specialization': 'general',
                'priority': 'low'
            }
        }
        
        # Check which models exist on H: drive
        for model_name, config in h_drive_models.items():
            if os.path.exists(config['path']):
                self.model_paths[model_name] = config
                print(f"Found {model_name} at {config['path']}")
            else:
                print(f"Model {model_name} not found at {config['path']}")
        
        print(f"Total models found: {len(self.model_paths)}")
    
    def register_models_with_core(self):
        """Register H: drive models with existing Core system"""
        if not self.advanced_integration:
            return
        
        for model_name, config in self.model_paths.items():
            try:
                # Register with Core's advanced integration
                self.advanced_integration.register_model_in_db(
                    name=model_name,
                    model_type=config['specialization'],
                    provider='local_h_drive',
                    config=config,
                    model_path=config['path'],
                    model_size='large',
                    context_length=8192,
                    is_quantized=True,
                    quantization_type='int8'
                )
                print(f"📝 Registered {model_name} with Core system")
            except Exception as e:
                self.logger.error(f"Error registering {model_name}: {e}")
    
    async def load_model(self, model_name: str) -> bool:
        """Load a specific model from H: drive"""
        if model_name not in self.model_paths:
            self.logger.error(f"Model {model_name} not found in H: drive")
            return False
        
        try:
            config = self.model_paths[model_name]
            model_path = config['path']
            
            if not os.path.exists(model_path):
                self.logger.error(f"Model path does not exist: {model_path}")
                return False
            
            print(f"📥 Loading {model_name} from H: drive...")
            
            # Load tokenizer
            tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # Load model with quantization
            quantization_config = BitsAndBytesConfig(
                load_in_8bit=True,
                llm_int8_threshold=6.0
            )
            
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map='auto',
                quantization_config=quantization_config
            )
            
            self.models[model_name] = {
                'tokenizer': tokenizer,
                'model': model,
                'config': config,
                'loaded_at': datetime.now()
            }
            
            print(f"✅ {model_name} loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading {model_name}: {e}")
            return False
    
    async def load_priority_models(self):
        """Load high-priority models (R1, R2) first"""
        priority_models = ['r1', 'r2']
        
        for model_name in priority_models:
            if model_name in self.model_paths:
                await self.load_model(model_name)
    
    async def generate_response(self, model_name: str, prompt: str) -> str:
        """Generate response using a specific model"""
        if model_name not in self.models:
            self.logger.error(f"Model {model_name} not loaded")
            return ""
        
        try:
            model_data = self.models[model_name]
            tokenizer = model_data['tokenizer']
            model = model_data['model']
            
            # Prepare input
            inputs = tokenizer(prompt, return_tensors="pt").to(self.device)
            
            # Generate response
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_length=inputs['input_ids'].shape[1] + 200,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=tokenizer.eos_token_id
                )
            
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            return response.replace(prompt, "").strip()
            
        except Exception as e:
            self.logger.error(f"Error generating response with {model_name}: {e}")
            return ""
    
    async def consensus_decision(self, prompt: str, use_deep_search: bool = False) -> Dict[str, Any]:
        """Make consensus decision using multiple models"""
        print(f"🧠 Daena making consensus decision...")
        print(f"🔍 Deep Search: {'Enabled' if use_deep_search else 'Disabled'}")
        
        # Determine which models to use
        if use_deep_search:
            # Use all available models for deep search
            models_to_use = list(self.models.keys())
        else:
            # Use priority models for regular decisions
            models_to_use = [name for name in ['r1', 'r2'] if name in self.models]
            if not models_to_use:
                models_to_use = list(self.models.keys())[:3]  # Use first 3 available
        
        if not models_to_use:
            return {
                'decision': 'No local models available',
                'confidence': 0.0,
                'models_used': [],
                'fallback': True
            }
        
        # Generate responses from all models
        responses = {}
        tasks = []
        
        for model_name in models_to_use:
            task = self.generate_response(model_name, prompt)
            tasks.append((model_name, task))
        
        # Execute all tasks concurrently
        for model_name, task in tasks:
            try:
                response = await task
                if response:
                    responses[model_name] = response
            except Exception as e:
                self.logger.error(f"Error with model {model_name}: {e}")
        
        if not responses:
            return {
                'decision': 'No responses generated',
                'confidence': 0.0,
                'models_used': [],
                'fallback': True
            }
        
        # Use Core's voting engine
        if len(responses) > 1:
            # Convert to format expected by Core voting engine
            vote_responses = [{'response': resp} for resp in responses.values()]
            consensus_response = vote_on_responses(vote_responses)
        else:
            consensus_response = list(responses.values())[0]
        
        # Calculate confidence based on agreement
        confidence = len(responses) / len(models_to_use)
        
        return {
            'decision': consensus_response,
            'confidence': confidence,
            'models_used': list(responses.keys()),
            'all_responses': responses,
            'fallback': False
        }
    
    async def should_use_deep_search(self, prompt: str) -> bool:
        """Determine if deep search should be used for this prompt"""
        # Simple heuristic - can be enhanced with ML
        deep_search_keywords = [
            'strategy', 'plan', 'roadmap', 'research', 'analyze', 'investigate',
            'project', 'business plan', 'market analysis', 'competitive analysis',
            'long term', 'comprehensive', 'detailed analysis'
        ]
        
        prompt_lower = prompt.lower()
        keyword_count = sum(1 for keyword in deep_search_keywords if keyword in prompt_lower)
        
        # Use deep search if multiple keywords found or prompt is long
        return keyword_count >= 2 or len(prompt.split()) > 50
    
    async def make_decision(self, prompt: str, force_deep_search: bool = False) -> Dict[str, Any]:
        """Main decision-making method"""
        print(f"🎯 Daena processing: {prompt[:100]}...")
        
        # Determine if deep search is needed
        if not force_deep_search:
            force_deep_search = await self.should_use_deep_search(prompt)
        
        # Make consensus decision
        result = await self.consensus_decision(prompt, use_deep_search=force_deep_search)
        
        # Log the decision
        self.log_decision(prompt, result)
        
        return result
    
    def log_decision(self, prompt: str, result: Dict[str, Any]):
        """Log decision for analysis"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'prompt': prompt,
            'decision': result['decision'],
            'confidence': result['confidence'],
            'models_used': result['models_used'],
            'deep_search': result.get('deep_search', False)
        }
        
        log_path = 'logs/enhanced_brain_decisions.jsonl'
        os.makedirs('logs', exist_ok=True)
        
        with open(log_path, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def get_brain_status(self) -> Dict[str, Any]:
        """Get current brain status"""
        return {
            'owner': f"{self.owner_name} ({self.owner_nickname})",
            'device': str(self.device),
            'models_available': len(self.model_paths),
            'models_loaded': len(self.models),
            'loaded_models': list(self.models.keys()),
            'consensus_threshold': self.consensus_threshold,
            'deep_search_enabled': self.deep_search_enabled,
            'h_drive_models': list(self.model_paths.keys())
        }

# Global instance for easy access
enhanced_brain = None

async def initialize_enhanced_brain(db_session=None):
    """Initialize the enhanced brain globally"""
    global enhanced_brain
    enhanced_brain = EnhancedLocalBrainIntegration(db_session)
    await enhanced_brain.load_priority_models()
    return enhanced_brain

async def get_enhanced_brain():
    """Get the global enhanced brain instance"""
    global enhanced_brain
    if enhanced_brain is None:
        enhanced_brain = await initialize_enhanced_brain()
    return enhanced_brain 