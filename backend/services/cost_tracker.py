"""
Cost Tracker Service
=====================
Monitors LLM API usage and enforces budget limits.
"""

import os
import time
import json
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

class CostTracker:
    def __init__(self):
        self.max_daily_cost = float(os.getenv("MAX_DAILY_COST_USD", "10.0"))
        self.max_per_request = float(os.getenv("MAX_PER_REQUEST_COST_USD", "1.0"))
        
        self.ledger_path = Path(__file__).parent.parent.parent / ".ledger" / "costs.json"
        self._load_ledger()

    def _load_ledger(self):
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        if self.ledger_path.exists():
            try:
                with open(self.ledger_path, "r") as f:
                    self.data = json.load(f)
            except:
                self.data = {"daily_total": 0.0, "last_reset": time.strftime("%Y-%m-%d")}
        else:
            self.data = {"daily_total": 0.0, "last_reset": time.strftime("%Y-%m-%d")}

    def _save_ledger(self):
        with open(self.ledger_path, "w") as f:
            json.dump(self.data, f)

    def check_budget(self) -> bool:
        """Check if we are within daily budget."""
        today = time.strftime("%Y-%m-%d")
        if self.data["last_reset"] != today:
            self.data["daily_total"] = 0.0
            self.data["last_reset"] = today
            self._save_ledger()
            
        return self.data["daily_total"] < self.max_daily_cost

    def record_usage(self, model: str, tokens_prompt: int, tokens_completion: int):
        """Record cost based on tokens (simulated pricing)."""
        # Simulated pricing per 1M tokens
        pricing = {
            "claude-3-5-sonnet": {"prompt": 3.0, "completion": 15.0},
            "gpt-4o": {"prompt": 5.0, "completion": 15.0},
            "gpt-4o-mini": {"prompt": 0.15, "completion": 0.6},
            "ollama": {"prompt": 0.0, "completion": 0.0}
        }
        
        # Simplified match
        prices = pricing.get("ollama")
        for k, v in pricing.items():
            if k in model.lower():
                prices = v
                break
        
        cost = (tokens_prompt / 1_000_000 * prices["prompt"]) + (tokens_completion / 1_000_000 * prices["completion"])
        
        self.data["daily_total"] += cost
        self._save_ledger()
        
        logger.info(f"Cost recorded: ${cost:.6f} for {model}. Daily total: ${self.data['daily_total']:.4f}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "daily_total_usd": self.data["daily_total"],
            "daily_limit_usd": self.max_daily_cost,
            "can_spend": self.check_budget()
        }

# Singleton
_tracker = None

def get_cost_tracker():
    global _tracker
    if not _tracker:
        _tracker = CostTracker()
    return _tracker
