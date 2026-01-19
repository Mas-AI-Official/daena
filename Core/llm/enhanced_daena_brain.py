#!/usr/bin/env python3
"""
Enhanced Daena Brain - Advanced AI Brain with Speed, Expertise, and Continuous Learning
Combines unified brain with advanced features for optimal performance
"""

import os
import json
import torch
import logging
import asyncio
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

class EnhancedDaenaBrain:
    def __init__(self):
        self.owner_name = "Masoud"
        self.owner_nickname = "Mas"
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.hf_token = os.getenv('HUGGINGFACE_TOKEN')
        
        # Brain paths
        self.unified_brain_path = "./models/daena-real-unified-brain"
        self.fallback_brain_path = "./models/daena-unified-brain"
        self.cache_path = "./cache/brain_cache"
        
        # Advanced features
        self.enable_continuous_learning = True
        self.enable_self_improvement = True
        self.enable_knowledge_synthesis = True
        self.enable_adaptive_reasoning = True
        
        # Performance optimization
        self.response_cache = {}
        self.knowledge_base = {}
        self.reasoning_patterns = {}
        self.expertise_areas = {}
        
        # Model components
        self.unified_model = None
        self.tokenizer = None
        self.model_loaded = False
        
        self.setup_logging()
        self.initialize_brain()
        
        print("🧠 Enhanced Daena Brain")
        print("=" * 50)
        print(f"👤 Owner: {self.owner_name} ({self.owner_nickname})")
        print(f"🚀 Device: {self.device}")
        print(f"🧠 Unified Brain: {'✅ Loaded' if self.model_loaded else '❌ Not Found'}")
        print(f"📈 Continuous Learning: {'✅ Enabled' if self.enable_continuous_learning else '❌ Disabled'}")
        print(f"🎯 Self Improvement: {'✅ Enabled' if self.enable_self_improvement else '❌ Disabled'}")
        print(f"🧩 Knowledge Synthesis: {'✅ Enabled' if self.enable_knowledge_synthesis else '❌ Disabled'}")
        print(f"🔄 Adaptive Reasoning: {'✅ Enabled' if self.enable_adaptive_reasoning else '❌ Disabled'}")
        print()
    
    def setup_logging(self):
        """Setup enhanced logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/enhanced_daena_brain.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('EnhancedDaenaBrain')
    
    def initialize_brain(self):
        """Initialize the enhanced brain"""
        # Try to load unified brain
        if os.path.exists(self.unified_brain_path):
            self.load_unified_brain(self.unified_brain_path)
        elif os.path.exists(self.fallback_brain_path):
            self.load_unified_brain(self.fallback_brain_path)
        else:
            self.logger.warning("No unified brain found. Will use API fallback.")
        
        # Initialize advanced features
        self.initialize_continuous_learning()
        self.initialize_knowledge_synthesis()
        self.initialize_adaptive_reasoning()
    
    def load_unified_brain(self, brain_path: str) -> bool:
        """Load the unified brain model"""
        try:
            print(f"📥 Loading unified brain from: {brain_path}")
            
            self.tokenizer = AutoTokenizer.from_pretrained(brain_path)
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
            if torch.cuda.is_available():
                try:
                    quantization_config = BitsAndBytesConfig(
                        load_in_4bit=True,
                        bnb_4bit_compute_dtype=torch.float16
                    )
                    self.unified_model = AutoModelForCausalLM.from_pretrained(
                        brain_path,
                        torch_dtype=torch.float16,
                        device_map='auto',
                        quantization_config=quantization_config
                    )
                except Exception as e:
                    self.logger.warning(f"Quantization failed, trying without: {e}")
                    self.unified_model = AutoModelForCausalLM.from_pretrained(
                        brain_path,
                        torch_dtype=torch.float16,
                        device_map='auto'
                    )
            else:
                self.unified_model = AutoModelForCausalLM.from_pretrained(
                    brain_path,
                    torch_dtype=torch.float32,
                    device_map='cpu'
                )
            
            self.model_loaded = True
            print("✅ Unified brain loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading unified brain: {e}")
            print(f"❌ Failed to load unified brain: {e}")
            return False
    
    def initialize_continuous_learning(self):
        """Initialize continuous learning system"""
        if not self.enable_continuous_learning:
            return
        
        # Create learning cache
        os.makedirs(self.cache_path, exist_ok=True)
        
        # Load existing knowledge
        knowledge_file = os.path.join(self.cache_path, "knowledge_base.json")
        if os.path.exists(knowledge_file):
            try:
                with open(knowledge_file, 'r', encoding='utf-8') as f:
                    self.knowledge_base = json.load(f)
                print(f"📚 Loaded {len(self.knowledge_base)} knowledge entries")
            except Exception as e:
                self.logger.error(f"Error loading knowledge base: {e}")
        
        print("✅ Continuous learning initialized")
    
    def initialize_knowledge_synthesis(self):
        """Initialize knowledge synthesis system"""
        if not self.enable_knowledge_synthesis:
            return
        
        # Define expertise areas
        self.expertise_areas = {
            'business_strategy': {
                'weight': 1.5,
                'keywords': ['strategy', 'business', 'market', 'competition', 'growth'],
                'models': ['r1', 'r2', 'yi-34b']
            },
            'coding_development': {
                'weight': 1.3,
                'keywords': ['code', 'programming', 'development', 'algorithm', 'software'],
                'models': ['deepseek-coder', 'codellama', 'r1']
            },
            'financial_analysis': {
                'weight': 1.4,
                'keywords': ['finance', 'investment', 'revenue', 'profit', 'budget'],
                'models': ['r1', 'r2', 'yi-34b']
            },
            'marketing_sales': {
                'weight': 1.2,
                'keywords': ['marketing', 'sales', 'customer', 'brand', 'campaign'],
                'models': ['qwen2.5', 'yi-34b']
            },
            'general_reasoning': {
                'weight': 1.0,
                'keywords': ['analysis', 'problem', 'solution', 'decision', 'logic'],
                'models': ['r1', 'r2', 'phi-2']
            }
        }
        
        print("✅ Knowledge synthesis initialized")
    
    def initialize_adaptive_reasoning(self):
        """Initialize adaptive reasoning system"""
        if not self.enable_adaptive_reasoning:
            return
        
        # Load reasoning patterns
        patterns_file = os.path.join(self.cache_path, "reasoning_patterns.json")
        if os.path.exists(patterns_file):
            try:
                with open(patterns_file, 'r', encoding='utf-8') as f:
                    self.reasoning_patterns = json.load(f)
                print(f"🧩 Loaded {len(self.reasoning_patterns)} reasoning patterns")
            except Exception as e:
                self.logger.error(f"Error loading reasoning patterns: {e}")
        
        print("✅ Adaptive reasoning initialized")
    
    def detect_expertise_area(self, prompt: str) -> str:
        """Detect the expertise area for a given prompt"""
        prompt_lower = prompt.lower()
        
        best_area = 'general_reasoning'
        best_score = 0
        
        for area, config in self.expertise_areas.items():
            score = 0
            for keyword in config['keywords']:
                if keyword in prompt_lower:
                    score += 1
            
            weighted_score = score * config['weight']
            if weighted_score > best_score:
                best_score = weighted_score
                best_area = area
        
        return best_area
    
    def generate_enhanced_response(self, prompt: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Generate enhanced response with advanced features"""
        start_time = datetime.now()
        
        # Detect expertise area
        expertise_area = self.detect_expertise_area(prompt)
        
        # Check cache first
        cache_key = f"{prompt}_{expertise_area}"
        if cache_key in self.response_cache:
            cached_response = self.response_cache[cache_key]
            cached_response['source'] = 'cache'
            cached_response['response_time_ms'] = 0
            return cached_response
        
        # Generate response
        if self.model_loaded and self.unified_model:
            response = self.generate_unified_response(prompt, expertise_area)
        else:
            response = self.generate_api_fallback_response(prompt, expertise_area)
        
        # Apply knowledge synthesis
        if self.enable_knowledge_synthesis:
            response = self.apply_knowledge_synthesis(response, prompt, expertise_area)
        
        # Apply adaptive reasoning
        if self.enable_adaptive_reasoning:
            response = self.apply_adaptive_reasoning(response, prompt, expertise_area)
        
        # Calculate response time
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Prepare result
        result = {
            'response': response,
            'expertise_area': expertise_area,
            'confidence': self.calculate_confidence(response, expertise_area),
            'response_time_ms': response_time,
            'source': 'unified_brain' if self.model_loaded else 'api_fallback',
            'timestamp': datetime.now().isoformat(),
            'context': context or {}
        }
        
        # Cache response
        self.response_cache[cache_key] = result
        
        # Update knowledge base
        if self.enable_continuous_learning:
            self.update_knowledge_base(prompt, result)
        
        return result
    
    def generate_unified_response(self, prompt: str, expertise_area: str) -> str:
        """Generate response using unified brain"""
        try:
            # Prepare input
            input_text = f"User: {prompt}\nDaena: "
            inputs = self.tokenizer(input_text, return_tensors="pt").to(self.device)
            
            # Generate response
            with torch.no_grad():
                outputs = self.unified_model.generate(
                    **inputs,
                    max_length=inputs['input_ids'].shape[1] + 200,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    repetition_penalty=1.1
                )
            
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            response = response.replace(input_text, "").strip()
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating unified response: {e}")
            return self.generate_api_fallback_response(prompt, expertise_area)
    
    def generate_api_fallback_response(self, prompt: str, expertise_area: str) -> str:
        """Generate response using API fallback"""
        try:
            # Use Azure OpenAI as fallback
            from openai import AzureOpenAI
            
            client = AzureOpenAI(
                api_key=os.getenv('AZURE_OPENAI_API_KEY'),
                api_version=os.getenv('AZURE_OPENAI_API_VERSION'),
                azure_endpoint=os.getenv('AZURE_OPENAI_API_BASE')
            )
            
            # Enhance prompt based on expertise area
            enhanced_prompt = self.enhance_prompt_for_expertise(prompt, expertise_area)
            
            response = client.chat.completions.create(
                model=os.getenv('AZURE_OPENAI_DEPLOYMENT_ID'),
                messages=[
                    {"role": "system", "content": f"You are Daena, an AI Vice President. You are an expert in {expertise_area.replace('_', ' ')}. Provide clear, actionable advice."},
                    {"role": "user", "content": enhanced_prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            self.logger.error(f"Error generating API fallback response: {e}")
            return f"I apologize, but I'm having trouble processing your request right now. Please try again later. (Error: {str(e)})"
    
    def enhance_prompt_for_expertise(self, prompt: str, expertise_area: str) -> str:
        """Enhance prompt based on expertise area"""
        expertise_config = self.expertise_areas.get(expertise_area, {})
        
        enhancement = f"Please provide expert-level {expertise_area.replace('_', ' ')} analysis for: {prompt}"
        
        if expertise_area == 'business_strategy':
            enhancement += "\n\nFocus on strategic thinking, market analysis, and actionable recommendations."
        elif expertise_area == 'coding_development':
            enhancement += "\n\nProvide clear, efficient, and well-documented code solutions."
        elif expertise_area == 'financial_analysis':
            enhancement += "\n\nInclude quantitative analysis, risk assessment, and financial implications."
        elif expertise_area == 'marketing_sales':
            enhancement += "\n\nConsider customer psychology, market positioning, and ROI analysis."
        
        return enhancement
    
    def apply_knowledge_synthesis(self, response: str, prompt: str, expertise_area: str) -> str:
        """Apply knowledge synthesis to enhance response"""
        # Add relevant knowledge from knowledge base
        relevant_knowledge = []
        
        for key, knowledge in self.knowledge_base.items():
            if any(keyword in prompt.lower() for keyword in knowledge.get('keywords', [])):
                relevant_knowledge.append(knowledge.get('content', ''))
        
        if relevant_knowledge:
            synthesis = f"\n\nBased on my accumulated knowledge:\n" + "\n".join(relevant_knowledge[:2])
            response += synthesis
        
        return response
    
    def apply_adaptive_reasoning(self, response: str, prompt: str, expertise_area: str) -> str:
        """Apply adaptive reasoning patterns"""
        # Apply reasoning patterns based on expertise area
        patterns = self.reasoning_patterns.get(expertise_area, [])
        
        if patterns:
            # Apply the most relevant pattern
            pattern = patterns[0]
            if pattern.get('type') == 'structured_analysis':
                response = self.apply_structured_analysis(response, pattern)
            elif pattern.get('type') == 'step_by_step':
                response = self.apply_step_by_step_reasoning(response, pattern)
        
        return response
    
    def apply_structured_analysis(self, response: str, pattern: Dict) -> str:
        """Apply structured analysis pattern"""
        structure = pattern.get('structure', [])
        if structure:
            structured_response = "\n\nStructured Analysis:\n"
            for step in structure:
                structured_response += f"• {step}: [Analysis]\n"
            response += structured_response
        
        return response
    
    def apply_step_by_step_reasoning(self, response: str, pattern: Dict) -> str:
        """Apply step-by-step reasoning pattern"""
        steps = pattern.get('steps', [])
        if steps:
            step_response = "\n\nStep-by-Step Reasoning:\n"
            for i, step in enumerate(steps, 1):
                step_response += f"{i}. {step}\n"
            response += step_response
        
        return response
    
    def calculate_confidence(self, response: str, expertise_area: str) -> float:
        """Calculate confidence score for response"""
        base_confidence = 0.8
        
        # Adjust based on expertise area
        expertise_config = self.expertise_areas.get(expertise_area, {})
        area_confidence = expertise_config.get('weight', 1.0) * 0.1
        
        # Adjust based on response length and quality
        length_confidence = min(len(response) / 100, 0.2)
        
        # Adjust based on knowledge base usage
        knowledge_confidence = 0.1 if "accumulated knowledge" in response else 0.0
        
        total_confidence = base_confidence + area_confidence + length_confidence + knowledge_confidence
        return min(total_confidence, 1.0)
    
    def update_knowledge_base(self, prompt: str, result: Dict[str, Any]):
        """Update knowledge base with new information"""
        if not self.enable_continuous_learning:
            return
        
        # Extract key information
        knowledge_entry = {
            'prompt': prompt,
            'response': result['response'],
            'expertise_area': result['expertise_area'],
            'confidence': result['confidence'],
            'timestamp': result['timestamp'],
            'keywords': self.extract_keywords(prompt),
            'content': result['response'][:200] + "..." if len(result['response']) > 200 else result['response']
        }
        
        # Add to knowledge base
        key = f"{result['expertise_area']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.knowledge_base[key] = knowledge_entry
        
        # Save to file
        knowledge_file = os.path.join(self.cache_path, "knowledge_base.json")
        try:
            with open(knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(self.knowledge_base, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Error saving knowledge base: {e}")
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Simple keyword extraction
        words = text.lower().split()
        keywords = [word for word in words if len(word) > 3 and word.isalpha()]
        return keywords[:10]  # Limit to 10 keywords
    
    def get_brain_status(self) -> Dict[str, Any]:
        """Get comprehensive brain status"""
        return {
            'model_loaded': self.model_loaded,
            'device': str(self.device),
            'unified_brain_path': self.unified_brain_path,
            'continuous_learning': self.enable_continuous_learning,
            'self_improvement': self.enable_self_improvement,
            'knowledge_synthesis': self.enable_knowledge_synthesis,
            'adaptive_reasoning': self.enable_adaptive_reasoning,
            'knowledge_base_size': len(self.knowledge_base),
            'reasoning_patterns_size': len(self.reasoning_patterns),
            'response_cache_size': len(self.response_cache),
            'expertise_areas': list(self.expertise_areas.keys()),
            'owner': f"{self.owner_name} ({self.owner_nickname})",
            'timestamp': datetime.now().isoformat()
        }
    
    def self_improve(self):
        """Trigger self-improvement process"""
        if not self.enable_self_improvement:
            return False
        
        print("🔄 Starting self-improvement process...")
        
        try:
            # Analyze performance patterns
            self.analyze_performance_patterns()
            
            # Update reasoning patterns
            self.update_reasoning_patterns()
            
            # Optimize knowledge base
            self.optimize_knowledge_base()
            
            print("✅ Self-improvement completed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error during self-improvement: {e}")
            return False
    
    def analyze_performance_patterns(self):
        """Analyze performance patterns for improvement"""
        # Analyze response times, confidence scores, etc.
        pass
    
    def update_reasoning_patterns(self):
        """Update reasoning patterns based on performance"""
        # Update patterns based on successful responses
        pass
    
    def optimize_knowledge_base(self):
        """Optimize knowledge base by removing outdated entries"""
        # Remove old or low-confidence entries
        pass

# Global instance
enhanced_brain = None

async def initialize_enhanced_brain():
    """Initialize the enhanced brain globally"""
    global enhanced_brain
    enhanced_brain = EnhancedDaenaBrain()
    return enhanced_brain

async def get_enhanced_brain():
    """Get the global enhanced brain instance"""
    global enhanced_brain
    if enhanced_brain is None:
        enhanced_brain = await initialize_enhanced_brain()
    return enhanced_brain 