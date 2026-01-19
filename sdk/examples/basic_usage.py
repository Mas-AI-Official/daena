"""
Basic usage examples for Daena Python SDK.
"""

from daena_sdk import DaenaClient
import os

# Initialize client
API_KEY = os.getenv("DAENA_API_KEY", "test-api-key")
BASE_URL = os.getenv("DAENA_BASE_URL", "http://localhost:8000")

client = DaenaClient(api_key=API_KEY, base_url=BASE_URL)


def example_system_operations():
    """Example: System operations."""
    print("=" * 60)
    print("SYSTEM OPERATIONS")
    print("=" * 60)
    
    # Test connection
    if client.test_connection():
        print("✅ Connected to Daena!")
    else:
        print("❌ Connection failed")
        return
    
    # Get health
    health = client.get_health()
    print(f"Health Status: {health.get('status', 'unknown')}")
    
    # Get system summary
    summary = client.get_system_summary()
    print(f"Total Agents: {summary.get('agents', {}).get('total', 0)}")
    print(f"Departments: {summary.get('departments', {}).get('total', 0)}")
    
    # Get metrics
    metrics = client.get_system_metrics()
    print(f"Active Agents: {metrics.active_agents}")
    print(f"Average Latency: {metrics.average_latency_ms:.2f}ms")


def example_agent_management():
    """Example: Agent management."""
    print("\n" + "=" * 60)
    print("AGENT MANAGEMENT")
    print("=" * 60)
    
    # Get all agents
    agents = client.get_agents(limit=10)
    print(f"Total Agents: {len(agents)}")
    
    # Get agents by department
    if agents:
        first_agent = agents[0]
        print(f"First Agent: {first_agent.name} ({first_agent.department})")
        
        # Get specific agent details
        try:
            agent = client.get_agent(first_agent.agent_id)
            print(f"Agent Status: {agent.status}")
            print(f"Capabilities: {', '.join(agent.capabilities[:3])}")
        except Exception as e:
            print(f"Error getting agent: {e}")


def example_chat():
    """Example: Chat with Daena."""
    print("\n" + "=" * 60)
    print("DAENA CHAT")
    print("=" * 60)
    
    try:
        # Send a message
        response = client.chat("What's the current system status?")
        print(f"Response: {response.get('response', 'No response')[:200]}")
    except Exception as e:
        print(f"Chat error: {e}")


def example_memory_operations():
    """Example: Memory operations."""
    print("\n" + "=" * 60)
    print("MEMORY OPERATIONS")
    print("=" * 60)
    
    try:
        # Store memory
        record = client.store_memory(
            key="example:test:data",
            payload={
                "message": "This is a test memory",
                "timestamp": "2025-01-XX"
            },
            class_name="example"
        )
        print(f"✅ Stored memory: {record.record_id}")
        
        # Retrieve memory
        retrieved = client.retrieve_memory("example:test:data")
        if retrieved:
            print(f"✅ Retrieved memory: {retrieved.key}")
        
        # Search memory
        results = client.search_memory("test", limit=5)
        print(f"✅ Found {len(results)} matching memories")
        
    except Exception as e:
        print(f"Memory error: {e}")


def example_council_system():
    """Example: Council system."""
    print("\n" + "=" * 60)
    print("COUNCIL SYSTEM")
    print("=" * 60)
    
    try:
        # Run debate
        decision = client.run_council_debate(
            department="ai",
            topic="Should we optimize the memory system?",
            context={"priority": "high"}
        )
        print(f"✅ Decision: {decision.decision[:100]}")
        print(f"Confidence: {decision.confidence:.2%}")
        
        # Get conclusions
        conclusions = client.get_council_conclusions(limit=5)
        print(f"✅ Recent Conclusions: {len(conclusions)}")
        
    except Exception as e:
        print(f"Council error: {e}")


def example_analytics():
    """Example: Analytics."""
    print("\n" + "=" * 60)
    print("ANALYTICS")
    print("=" * 60)
    
    try:
        # Get analytics summary
        summary = client.get_analytics_summary()
        print(f"✅ Analytics Summary: {len(summary)} metrics")
        
        # Get insights
        insights = client.get_advanced_insights()
        print(f"✅ Advanced Insights: Available")
        
    except Exception as e:
        print(f"Analytics error: {e}")


if __name__ == "__main__":
    print("🚀 Daena Python SDK - Basic Usage Examples\n")
    
    try:
        example_system_operations()
        example_agent_management()
        example_chat()
        example_memory_operations()
        example_council_system()
        example_analytics()
        
        print("\n" + "=" * 60)
        print("✅ All examples completed!")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

