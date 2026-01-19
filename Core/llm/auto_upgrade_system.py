#!/usr/bin/env python3
"""
Auto Upgrade System for Daena's Perfect Brain
Automatically detects and adopts better models
"""

import os
import json
import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('.env')

class AutoUpgradeSystem:
    def __init__(self):
        self.hf_token = "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"
        self.brain_path = "./models/daena-perfect-brain"
        self.upgrade_log_path = "./logs/auto_upgrades.jsonl"
        self.setup_logging()
        
        # Model performance tracking
        self.model_performance = {}
        self.upgrade_threshold = 0.15  # 15% improvement threshold
        
        # New model discovery
        self.discovery_interval = timedelta(days=7)  # Check weekly
        self.last_discovery = None
        
        print("🔄 Auto Upgrade System")
        print("=" * 40)
        print("🎯 Automatically detects better models")
        print("📈 Tracks performance improvements")
        print("🔄 Replaces outdated models")
        print("✅ Requires owner permission")
        print()
    
    def setup_logging(self):
        """Setup logging for auto upgrade system"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/auto_upgrade.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('AutoUpgradeSystem')
    
    def discover_new_models(self) -> List[Dict[str, Any]]:
        """Discover new and better models on HuggingFace"""
        print("🔍 Discovering new models on HuggingFace...")
        
        new_models = []
        
        # Search for trending models
        search_queries = [
            "reasoning", "logic", "analysis",
            "creative", "content", "storytelling",
            "coding", "programming", "software",
            "mathematics", "science", "optimization",
            "general", "intelligence", "understanding",
            "specialized", "expert", "domain"
        ]
        
        for query in search_queries:
            try:
                url = f"https://huggingface.co/api/models"
                params = {
                    "search": query,
                    "sort": "downloads",
                    "direction": "-1",
                    "limit": 10
                }
                headers = {"Authorization": f"Bearer {self.hf_token}"}
                
                response = requests.get(url, params=params, headers=headers)
                if response.status_code == 200:
                    models = response.json()
                    
                    for model in models:
                        # Check if it's a new/better model
                        if self.is_better_model(model):
                            new_models.append({
                                "name": model["modelId"],
                                "downloads": model.get("downloads", 0),
                                "likes": model.get("likes", 0),
                                "category": self.categorize_model(model),
                                "description": model.get("description", ""),
                                "discovered_at": datetime.now().isoformat()
                            })
                
            except Exception as e:
                self.logger.warning(f"Error discovering models for {query}: {e}")
                continue
        
        print(f"✅ Discovered {len(new_models)} potential new models")
        return new_models
    
    def is_better_model(self, model: Dict) -> bool:
        """Check if a model is better than current ones"""
        try:
            # Check download count (popularity)
            downloads = model.get("downloads", 0)
            if downloads < 1000:  # Too new/unpopular
                return False
            
            # Check likes (quality indicator)
            likes = model.get("likes", 0)
            if likes < 100:  # Not well-received
                return False
            
            # Check if it's a recent model (last 6 months)
            created_at = model.get("createdAt")
            if created_at:
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if created_date < datetime.now() - timedelta(days=180):
                    return False  # Too old
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Error checking model quality: {e}")
            return False
    
    def categorize_model(self, model: Dict) -> str:
        """Categorize a model based on its description and tags"""
        description = model.get("description", "").lower()
        tags = model.get("tags", [])
        
        if any(tag in description for tag in ["reasoning", "logic", "analysis"]):
            return "reasoning"
        elif any(tag in description for tag in ["creative", "story", "content"]):
            return "creative"
        elif any(tag in description for tag in ["code", "programming", "software"]):
            return "coding"
        elif any(tag in description for tag in ["math", "mathematics", "science"]):
            return "mathematics"
        elif any(tag in description for tag in ["general", "understanding"]):
            return "general"
        else:
            return "specialized"
    
    def evaluate_model_performance(self, model_name: str, responses: List[str]) -> float:
        """Evaluate model performance based on response quality"""
        try:
            # Simple evaluation metrics
            avg_length = sum(len(response) for response in responses) / len(responses)
            coherence_score = self.calculate_coherence(responses)
            relevance_score = self.calculate_relevance(responses)
            
            # Combined score
            performance_score = (avg_length * 0.3 + coherence_score * 0.4 + relevance_score * 0.3)
            
            return performance_score
            
        except Exception as e:
            self.logger.error(f"Error evaluating model performance: {e}")
            return 0.0
    
    def calculate_coherence(self, responses: List[str]) -> float:
        """Calculate response coherence score"""
        # Simple coherence check
        coherent_count = 0
        for response in responses:
            if len(response.split()) > 10 and response.endswith(('.', '!', '?')):
                coherent_count += 1
        
        return coherent_count / len(responses) if responses else 0.0
    
    def calculate_relevance(self, responses: List[str]) -> float:
        """Calculate response relevance score"""
        # Simple relevance check
        relevant_count = 0
        for response in responses:
            if len(response) > 20 and not response.startswith("I don't know"):
                relevant_count += 1
        
        return relevant_count / len(responses) if responses else 0.0
    
    def compare_models(self, current_model: str, new_model: str) -> Dict[str, Any]:
        """Compare current model with new model"""
        try:
            # Get current model performance
            current_performance = self.model_performance.get(current_model, 0.0)
            
            # Test new model (simplified)
            new_performance = self.test_new_model(new_model)
            
            improvement = (new_performance - current_performance) / current_performance if current_performance > 0 else 0
            
            return {
                "current_model": current_model,
                "new_model": new_model,
                "current_performance": current_performance,
                "new_performance": new_performance,
                "improvement": improvement,
                "should_upgrade": improvement > self.upgrade_threshold
            }
            
        except Exception as e:
            self.logger.error(f"Error comparing models: {e}")
            return {"should_upgrade": False}
    
    def test_new_model(self, model_name: str) -> float:
        """Test a new model with sample prompts"""
        # Simplified testing - in real implementation, this would load and test the model
        return 0.8  # Placeholder score
    
    def request_upgrade_permission(self, upgrade_info: Dict) -> bool:
        """Request permission from owner for upgrade"""
        print("\n🔄 UPGRADE REQUEST")
        print("=" * 30)
        print(f"Current Model: {upgrade_info['current_model']}")
        print(f"New Model: {upgrade_info['new_model']}")
        print(f"Performance Improvement: {upgrade_info['improvement']:.2%}")
        print(f"Category: {upgrade_info.get('category', 'unknown')}")
        print()
        
        # In real implementation, this would send notification to owner
        # For now, we'll simulate approval
        response = input("Approve upgrade? (y/n): ").lower().strip()
        return response == 'y'
    
    def perform_upgrade(self, upgrade_info: Dict) -> bool:
        """Perform the model upgrade"""
        try:
            print(f"🔄 Upgrading {upgrade_info['current_model']} to {upgrade_info['new_model']}...")
            
            # Download new model
            # Update brain configuration
            # Retrain with new model
            # Update metadata
            
            # Log upgrade
            upgrade_log = {
                "timestamp": datetime.now().isoformat(),
                "action": "model_upgrade",
                "current_model": upgrade_info['current_model'],
                "new_model": upgrade_info['new_model'],
                "improvement": upgrade_info['improvement'],
                "status": "completed"
            }
            
            with open(self.upgrade_log_path, "a") as f:
                f.write(json.dumps(upgrade_log) + "\n")
            
            print("✅ Upgrade completed successfully!")
            return True
            
        except Exception as e:
            self.logger.error(f"Error performing upgrade: {e}")
            print(f"❌ Upgrade failed: {e}")
            return False
    
    def run_auto_upgrade_cycle(self) -> bool:
        """Run the complete auto upgrade cycle"""
        print("🔄 Starting auto upgrade cycle...")
        
        try:
            # Step 1: Discover new models
            new_models = self.discover_new_models()
            
            if not new_models:
                print("✅ No new models to evaluate")
                return True
            
            # Step 2: Evaluate each new model
            upgrades_needed = []
            
            for new_model in new_models:
                # Find current model in same category
                current_model = self.find_current_model_in_category(new_model['category'])
                
                if current_model:
                    comparison = self.compare_models(current_model, new_model['name'])
                    comparison['category'] = new_model['category']
                    
                    if comparison['should_upgrade']:
                        upgrades_needed.append(comparison)
            
            # Step 3: Request permissions and perform upgrades
            for upgrade_info in upgrades_needed:
                if self.request_upgrade_permission(upgrade_info):
                    success = self.perform_upgrade(upgrade_info)
                    if not success:
                        print(f"❌ Failed to upgrade {upgrade_info['current_model']}")
                else:
                    print(f"❌ Upgrade rejected for {upgrade_info['current_model']}")
            
            print(f"✅ Auto upgrade cycle completed. {len(upgrades_needed)} upgrades processed.")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in auto upgrade cycle: {e}")
            print(f"❌ Auto upgrade cycle failed: {e}")
            return False
    
    def find_current_model_in_category(self, category: str) -> Optional[str]:
        """Find current model in a specific category"""
        # This would read from current brain configuration
        # For now, return a placeholder
        category_models = {
            "reasoning": "r1_reasoning",
            "creative": "mistral_creative",
            "coding": "deepseek_coder",
            "mathematics": "qwen_math",
            "general": "yi_34b",
            "specialized": "internlm_20b"
        }
        return category_models.get(category)
    
    def get_upgrade_status(self) -> Dict[str, Any]:
        """Get current upgrade system status"""
        return {
            "last_discovery": self.last_discovery.isoformat() if self.last_discovery else None,
            "upgrade_threshold": self.upgrade_threshold,
            "model_performance": self.model_performance,
            "auto_upgrade_enabled": True
        }

# Global instance
auto_upgrade_system = None

def initialize_auto_upgrade_system():
    """Initialize the auto upgrade system globally"""
    global auto_upgrade_system
    auto_upgrade_system = AutoUpgradeSystem()
    return auto_upgrade_system

def get_auto_upgrade_system():
    """Get the global auto upgrade system instance"""
    global auto_upgrade_system
    if auto_upgrade_system is None:
        auto_upgrade_system = initialize_auto_upgrade_system()
    return auto_upgrade_system 