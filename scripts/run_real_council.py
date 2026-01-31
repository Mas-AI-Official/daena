"""
Script to run a REAL Council Round using the migrated CouncilScheduler.
Validates Scheduler <-> MessageBus <-> UnifiedMemory integration.
"""
import asyncio
import logging
import sys
import os
import time

# Add root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("real_council_runner")

from backend.services.council_scheduler import CouncilScheduler
from backend.utils.message_bus_v2 import message_bus_v2

async def mock_scout_agent(department: str):
    """Simulate a scout agent replying to requests."""
    await asyncio.sleep(1) # Wait for subscription
    topic = f"cell/{department}/requests"
    
    # We subscribe to cell requests? 
    # Actually CouncilScheduler subscribes to cell/dept/* and ring/*
    # Scouts PUBLISH to cell/dept/scout_reports or ring/scout_reports
    
    # Simulate Scout Publishing
    for i in range(2):
        await asyncio.sleep(2)
        logger.info(f"🤖 [Scout] Publishing summary {i+1}...")
        await message_bus_v2.publish(
            f"cell/{department}/scout_report",
            {
                "summary": f"Market analysis {i+1} for {department}. Trend is UP.",
                "confidence": 0.85,
                "emotion": {"excitement": 0.7}
            },
            sender=f"scout_{department}_{i}"
        )

async def mock_advisor_agent(department: str):
    """Simulate an advisor debating on the ring."""
    await asyncio.sleep(5) # Wait for debate phase
    
    # Simulate Advisor Publishing to Ring
    for i in range(2):
        await asyncio.sleep(2)
        logger.info(f"🧙‍♂️ [Advisor] Publishing draft {i+1}...")
        await message_bus_v2.publish(
            f"ring/debate",
            {
                "draft": f"Strategy {i+1}: Invest heavily in {department}.",
                "confidence": 0.9,
                "counter_to": None
            },
            sender=f"advisor_{department}_{i}"
        )

async def run_council():
    logger.info("🚀 Starting Real Council Scheduler Test")
    
    scheduler = CouncilScheduler()
    await scheduler.start()
    
    # Launch mock agents in background
    department = "engineering"
    asyncio.create_task(mock_scout_agent(department))
    asyncio.create_task(mock_advisor_agent(department))
    
    try:
        logger.info("📅 Triggering Council Tick...")
        # Reduce timeouts for test
        scheduler.phase_timeouts = {k: 5.0 for k in scheduler.phase_timeouts} # Speed up
        
        result = await scheduler.council_tick(department, "Q1 Roadmap")
        
        logger.info("\n✅ Council Round Completed!")
        logger.info(f"Round ID: {result['round_id']}")
        logger.info(f"Scout Summaries: {len(result['scout']['summaries'])}")
        logger.info(f"Debate Drafts: {len(result['debate']['drafts'])}")
        logger.info(f"Committed: {result['commit'].get('committed')}")
        logger.info(f"Impact: {result['commit'].get('impact')}")
        
        if result['commit'].get('committed'):
             logger.info("🎉 SUCCESS: Action committed to Unified Memory!")
        else:
             logger.error("❌ FAILURE: No action committed.")
             
    except Exception as e:
        logger.error(f"❌ Error running council: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await scheduler.stop()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_council())
