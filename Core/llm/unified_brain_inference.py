#!/usr/bin/env python3
"""
Unified Brain Inference for Daena
Loads and uses the trained unified brain model for direct inference
"""

import os
import json
import torch
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

class UnifiedBrainInference:
    def __init__(self):
        self.owner_name = "Masoud"
        self.owner_nickname = "Mas"
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.unified_model_path = "./models/daena-unified-brain"
        self.tokenizer = None
        self.model = None
        self.model_loaded = False
        self.setup_logging()
        
        print("🧠 Unified Brain Inference")
        print("=" * 50)
        print(f"👤 Owner: {self.owner_name} ({self.owner_nickname})")
        print(f"🚀 Device: {self.device}")
        print(f"📁 Model Path: {self.unified_model_path}")
        print()
    
    def setup_logging(self):
        """Setup logging for unified brain inference"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/unified_brain_inference.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('UnifiedBrainInference')
    
    def load_unified_brain(self) -> bool:
        """Load the trained unified brain model"""
        print("📥 Loading unified brain model...")
        
        try:
            if not os.path.exists(self.unified_model_path):
                self.logger.error(f"Unified brain model not found at: {self.unified_model_path}")
                print(f"❌ Model not found at: {self.unified_model_path}")
                return False
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.unified_model_path)
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model with or without quantization based on device
            if torch.cuda.is_available():
                try:
                    # Try with quantization for GPU
                    quantization_config = BitsAndBytesConfig(
                        load_in_8bit=True,
                        llm_int8_threshold=6.0
                    )
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.unified_model_path,
                        torch_dtype=torch.float16,
                        device_map='auto',
                        quantization_config=quantization_config
                    )
                except Exception as e:
                    self.logger.warning(f"Quantization failed, trying without: {e}")
                    # Fallback to non-quantized GPU loading
                    self.model = AutoModelForCausalLM.from_pretrained(
                        self.unified_model_path,
                        torch_dtype=torch.float16,
                        device_map='auto'
                    )
            else:
                # Use CPU without quantization
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.unified_model_path,
                    torch_dtype=torch.float32,
                    device_map='cpu'
                )
            
            self.model_loaded = True
            print("✅ Unified brain model loaded successfully")
            
            # Load model info
            model_info = self.get_model_info()
            if model_info.get("status") != "not_trained":
                print(f"📊 Model Info: {model_info.get('name', 'Unknown')} v{model_info.get('version', 'Unknown')}")
                print(f"📊 Training Data: {model_info.get('training_data_size', 'Unknown')} examples")
                print(f"📊 Created: {model_info.get('created_at', 'Unknown')}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading unified brain: {e}")
            print(f"❌ Failed to load unified brain: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the unified brain model"""
        info_path = os.path.join(self.unified_model_path, "model_info.json")
        
        if os.path.exists(info_path):
            try:
                with open(info_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading model info: {e}")
        
        return {
            "name": "daena-unified-brain",
            "status": "not_trained",
            "path": self.unified_model_path,
            "exists": os.path.exists(self.unified_model_path)
        }
    
    def generate_response(self, prompt: str, max_length: int = 200, temperature: float = 0.7) -> str:
        """Generate response using the unified brain"""
        if not self.model_loaded:
            print("❌ Unified brain not loaded")
            return "Unified brain not loaded. Please load the model first."
        
        try:
            # Prepare input
            input_text = f"User: {prompt}\nDaena:"
            inputs = self.tokenizer(input_text, return_tensors="pt").to(self.device)
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=inputs['input_ids'].shape[1] + max_length,
                    temperature=temperature,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id,
                    repetition_penalty=1.1
                )
            
            # Decode response
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            response = response.replace(input_text, "").strip()
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating response: {e}")
            return f"Error generating response: {e}"
    
    def generate_enhanced_response(self, prompt: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Generate enhanced response with metadata"""
        if not self.model_loaded:
            return {
                "response": "Unified brain not loaded",
                "success": False,
                "error": "Model not loaded"
            }
        
        try:
            start_time = datetime.now()
            
            # Generate response
            response = self.generate_response(prompt)
            
            end_time = datetime.now()
            generation_time = (end_time - start_time).total_seconds()
            
            return {
                "response": response,
                "success": True,
                "model": "daena-unified-brain",
                "prompt": prompt,
                "generation_time": generation_time,
                "timestamp": datetime.now().isoformat(),
                "context": context
            }
            
        except Exception as e:
            self.logger.error(f"Error in enhanced response generation: {e}")
            return {
                "response": f"Error: {e}",
                "success": False,
                "error": str(e)
            }
    
    def batch_generate(self, prompts: List[str]) -> List[Dict[str, Any]]:
        """Generate responses for multiple prompts"""
        results = []
        
        for i, prompt in enumerate(prompts):
            print(f"🎯 Processing prompt {i+1}/{len(prompts)}: {prompt[:50]}...")
            result = self.generate_enhanced_response(prompt)
            results.append(result)
        
        return results
    
    def test_unified_brain(self) -> bool:
        """Test the unified brain with sample prompts"""
        print("🧪 Testing unified brain...")
        
        if not self.model_loaded:
            print("❌ Model not loaded")
            return False
        
        test_prompts = [
            f"Hello {self.owner_nickname}, what should we focus on today?",
            "Can you help me analyze this business opportunity?",
            "What's your recommendation for this situation?",
            "How should we approach this problem?",
            "What are the key factors to consider?",
            "Can you provide strategic advice?"
        ]
        
        results = self.batch_generate(test_prompts)
        
        print("\n📊 Test Results:")
        for i, result in enumerate(results):
            print(f"\n🎯 Test {i+1}: {test_prompts[i]}")
            print(f"🤖 Response: {result['response']}")
            print(f"⏱️ Time: {result.get('generation_time', 'N/A')}s")
            print(f"✅ Success: {result['success']}")
        
        success_count = sum(1 for r in results if r['success'])
        print(f"\n📈 Overall: {success_count}/{len(results)} tests passed")
        
        return success_count == len(results)
    
    def get_brain_status(self) -> Dict[str, Any]:
        """Get unified brain status"""
        model_info = self.get_model_info()
        
        return {
            "owner": f"{self.owner_name} ({self.owner_nickname})",
            "device": str(self.device),
            "model_loaded": self.model_loaded,
            "model_path": self.unified_model_path,
            "model_exists": os.path.exists(self.unified_model_path),
            "model_info": model_info,
            "timestamp": datetime.now().isoformat()
        }

# Global instance for easy access
unified_brain = None

def initialize_unified_brain():
    """Initialize the unified brain globally"""
    global unified_brain
    unified_brain = UnifiedBrainInference()
    return unified_brain

def get_unified_brain():
    """Get the global unified brain instance"""
    global unified_brain
    if unified_brain is None:
        unified_brain = initialize_unified_brain()
    return unified_brain

def load_unified_brain():
    """Load the unified brain model"""
    brain = get_unified_brain()
    return brain.load_unified_brain() 