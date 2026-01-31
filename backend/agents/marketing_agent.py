"""
Marketing Agent (Phase 3 Reference Implementation)
==================================================

This agent demonstrates the Daena "Phase 3" architecture:
1. Uses Unified Memory System (backend.memory)
2. Dependency Injection for Tools
3. Stateless execution logic (state persisted in Memory)

Usage:
    agent = MarketingAgent()
    agent.run("Create a tweet for Daena launch")
"""
import logging
import uuid
import sys
import os
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# PHASE 3: Unified Memory Import
from backend.memory import memory

logger = logging.getLogger(__name__)

class MarketingAgent:
    def __init__(self, agent_id: str = "marketing_v1"):
        self.agent_id = agent_id
        self.role = "Marketing Specialist"
        
    def run(self, task: str) -> Dict[str, Any]:
        """Execute a marketing task with memory persistence."""
        
        # 1. Log Task Start (L2 Memory)
        task_id = str(uuid.uuid4())
        memory.write(
            key=f"{self.agent_id}:task:{task_id}",
            cls="task",
            payload={
                "task": task,
                "status": "started",
                "timestamp": datetime.utcnow().isoformat()
            },
            meta={"agent_id": self.agent_id}
        )
        
        # 2. Check Memory for Context (L1/L2)
        # "Have I done this before?"
        similar_tasks = memory.search(task, top_k=3)
        context = [t['payload'] for t in similar_tasks]
        
        logger.info(f"[{self.agent_id}] Running task: {task}. Context found: {len(context)}")
        
        # 3. "Think" (Simulated Logic)
        # In real world, this calls LLM
        thought = f"Generating content for '{task}'. Context from memory suggests using professional tone."
        
        # 4. "Act" (Simulated Output)
        output = f"Draft Content: {task} - [AI Generated: {uuid.uuid4().hex[:8]}]"
        
        # 5. Store Result (L2 Memory + CAS)
        result_payload = {
            "task_id": task_id,
            "input": task,
            "output": output,
            "thought_process": thought,
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        memory.write(
            key=f"{self.agent_id}:result:{task_id}",
            cls="execution_result",
            payload=result_payload,
            meta={"tags": ["marketing", "content"]}
        )
        
        return result_payload

if __name__ == "__main__":
    # Self-test
    logging.basicConfig(level=logging.INFO)
    agent = MarketingAgent()
    res = agent.run("Draft a LinkedIn post about Unified Memory")
    print("\nResult:", res)
