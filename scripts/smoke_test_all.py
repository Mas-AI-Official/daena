"""
Smoke Test - Verify Brain Truth, MCP, and API
"""
import asyncio
import httpx
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://127.0.0.1:8000/api/v1"

async def test_brain_status():
    logger.info("🧠 Testing Brain Status...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/brain/status")
            if response.status_code != 200:
                logger.error(f"❌ Brain status failed: {response.status_code}")
                return False
            
            data = response.json()
            logger.info(f"✅ Brain Connected: {data.get('connected')}")
            logger.info(f"✅ Active Model: {data.get('active_model')}")
            logger.info(f"✅ Routing Mode: {data.get('routing_mode')}")
            return True
        except Exception as e:
            logger.error(f"❌ Brain status error: {e}")
            return False

async def test_mcp_connections():
    logger.info("🔌 Testing MCP Connections...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/connections/mcp")
            if response.status_code != 200:
                logger.error(f"❌ MCP list failed: {response.status_code}")
                return False
            
            data = response.json()
            logger.info(f"✅ Found {len(data)} MCP servers")
            for server in data:
                logger.info(f"   - {server['name']}: {server['status']}")
            return True
        except Exception as e:
            logger.error(f"❌ MCP error: {e}")
            return False

async def test_recommended_models():
    logger.info("🔍 Testing Recommended Models...")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BASE_URL}/brain/recommended")
            if response.status_code != 200:
                logger.error(f"❌ Recommended list failed: {response.status_code}")
                return False
            
            data = response.json()
            logger.info(f"✅ Found {len(data)} recommended models")
            return True
        except Exception as e:
            logger.error(f"❌ Recommended models error: {e}")
            return False

async def main():
    logger.info("🚀 Starting Smoke Tests...")
    
    # Wait for server to be ready (if running)
    # Note: This script assumes the backend is already running.
    # If not, it will fail.
    
    brain_ok = await test_brain_status()
    mcp_ok = await test_mcp_connections()
    rec_ok = await test_recommended_models()
    
    if brain_ok and mcp_ok and rec_ok:
        logger.info("\n✨ ALL SYSTEMS GO! ✨")
        sys.exit(0)
    else:
        logger.error("\n💥 SOME TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
