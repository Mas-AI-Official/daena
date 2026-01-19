"""Routing benchmark for Daena's Sunflower × Honeycomb system."""
import asyncio
import time
import json
from pathlib import Path
from typing import Dict, List, Any
import sys

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from utils.sunflower_registry import sunflower_registry
from backend.utils.message_bus import message_bus, Message, MessageType

class RoutingBenchmark:
    """Benchmark routing performance between local-first and CMP fallback."""
    
    def __init__(self):
        self.message_bus = message_bus  # Use global instance
        self.results = {
            "timestamp": time.time(),
            "total_messages": 0,
            "local_first": {
                "count": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "latencies": []
            },
            "cmp_fallback": {
                "count": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "latencies": []
            },
            "routing_failed": {
                "count": 0,
                "errors": []
            },
            "neighbor_distribution": {},
            "department_stats": {}
        }
        
    async def setup(self):
        """Setup benchmark environment."""
        print("🚀 Setting up routing benchmark...")
        
        # Start message bus
        await self.message_bus.start()
        
        # Ensure sunflower registry is populated
        if not sunflower_registry.departments:
            print("  ⚠️  Sunflower registry is empty, running seed...")
            await self.seed_registry()
        
        # Rebuild adjacency
        print("  🍯 Rebuilding adjacency relationships...")
        sunflower_registry.rebuild_adjacency()
        adjacency = sunflower_registry.adjacency_cache
        print(f"  ✅ {len(adjacency)} adjacency relationships created")
        
        # Show sample adjacency
        print("  📍 Sample adjacency (first 3 cells):")
        sample_adj = list(adjacency.items())[:3]
        for cell_id, neighbors in sample_adj:
            print(f"     {cell_id}: {neighbors}")
            
    async def seed_registry(self):
        """Seed the registry if empty."""
        try:
            # Import and run seed script
            from scripts.seed_6x8_council import main as seed_main  # Seeds 6x8 structure: 6 agents per department, 8 departments
            await seed_main()
        except Exception as e:
            print(f"  ❌ Failed to seed registry: {e}")
            # Create minimal test data
            self.create_test_data()
            
    def create_test_data(self):
        """Create minimal test data for benchmarking."""
        print("  🔧 Creating minimal test data...")
        
        # Add test departments
        for i in range(1, 9):
            dept_id = f"d{i}"
            sunflower_registry.register_department(
                dept_id,
                f"Test Department {i}",
                i,
                f"Test department {i} for benchmarking"
            )
            
        # Add test agents
        for dept_id in sunflower_registry.departments:
            for j in range(1, 9):
                agent_id = f"{dept_id}_agent{j}"
                sunflower_registry.register_agent(
                    agent_id,
                    f"Test Agent {j}",
                    f"role{j}",
                    dept_id
                )
                
        print(f"  ✅ Created {len(sunflower_registry.departments)} departments and {len(sunflower_registry.agents)} agents")
        
    async def run_benchmark(self, message_count: int = 100):
        """Run the routing benchmark."""
        print(f"\n🏃 Running routing benchmark with {message_count} messages...")
        
        self.results["total_messages"] = message_count
        
        # Generate test messages
        messages = self.generate_test_messages(message_count)
        
        # Process each message
        for i, message_data in enumerate(messages, 1):
            if i % 10 == 0:
                print(f"  📨 Processing message {i}/{message_count}")
                
            await self.process_message(message_data)
            
        # Calculate final statistics
        self.calculate_statistics()
        
        # Save results
        await self.save_results()
        
        print("\n🎉 Benchmark completed!")
        self.print_summary()
        
    def generate_test_messages(self, count: int) -> List[Dict[str, Any]]:
        """Generate test messages for benchmarking."""
        messages = []
        
        # Get all cell IDs
        cell_ids = list(sunflower_registry.cells.keys())
        
        for i in range(count):
            # Randomly select source and target
            source_cell = cell_ids[i % len(cell_ids)]
            target_cell = cell_ids[(i + 1) % len(cell_ids)]
            
            message_data = {
                "id": f"msg_{i:04d}",
                "topic": f"test_topic_{i % 5}",
                "content": {
                    "test_id": i,
                    "source": source_cell,
                    "target": target_cell,
                    "payload": f"Test message {i} content"
                },
                "sender": source_cell,
                "recipient": target_cell
            }
            
            messages.append(message_data)
            
        return messages
        
    async def process_message(self, message_data: Dict[str, Any]):
        """Process a single message and measure routing performance."""
        start_time = time.time()
        
        try:
            # Create message
            message = Message(
                id=message_data["id"],
                topic=message_data["topic"],
                content=message_data["content"],
                sender=message_data["sender"],
                recipient=message_data["recipient"]
            )
            
            # Get neighbors for local routing
            source_cell = message_data["sender"]
            neighbors = sunflower_registry.get_neighbors(source_cell, max_neighbors=6)
            
            # Route message
            routing_result = await self.message_bus.route(message, neighbors)
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Record results
            if routing_result == "local_success":
                self.results["local_first"]["count"] += 1
                self.results["local_first"]["latencies"].append(latency_ms)
            elif routing_result == "cmp_fallback":
                self.results["cmp_fallback"]["count"] += 1
                self.results["cmp_fallback"]["latencies"].append(latency_ms)
            else:
                self.results["routing_failed"]["count"] += 1
                self.results["routing_failed"]["errors"].append({
                    "message_id": message_data["id"],
                    "error": routing_result,
                    "latency_ms": latency_ms
                })
                
            # Record neighbor distribution
            neighbor_count = len(neighbors)
            self.results["neighbor_distribution"][neighbor_count] = \
                self.results["neighbor_distribution"].get(neighbor_count, 0) + 1
                
        except Exception as e:
            self.results["routing_failed"]["count"] += 1
            self.results["routing_failed"]["errors"].append({
                "message_id": message_data["id"],
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000
            })
            
    def calculate_statistics(self):
        """Calculate final statistics."""
        # Local first statistics
        local_count = self.results["local_first"]["count"]
        if local_count > 0:
            latencies = self.results["local_first"]["latencies"]
            self.results["local_first"]["avg_latency_ms"] = round(sum(latencies) / len(latencies), 2)
            self.results["local_first"]["success_rate"] = round(local_count / self.results["total_messages"] * 100, 2)
            
        # CMP fallback statistics
        cmp_count = self.results["cmp_fallback"]["count"]
        if cmp_count > 0:
            latencies = self.results["cmp_fallback"]["latencies"]
            self.results["cmp_fallback"]["avg_latency_ms"] = round(sum(latencies) / len(latencies), 2)
            self.results["cmp_fallback"]["success_rate"] = round(cmp_count / self.results["total_messages"] * 100, 2)
            
        # Department statistics
        for dept_id, dept_data in sunflower_registry.departments.items():
            self.results["department_stats"][dept_id] = {
                "name": dept_data["name"],
                "agent_count": len(dept_data["agents"]),
                "sunflower_index": dept_data["sunflower_index"],
                "neighbors": len(sunflower_registry.get_neighbors(dept_data["cell_id"]))
            }
            
    async def save_results(self):
        """Save benchmark results to file."""
        timestamp = int(time.time())
        filename = f"routing_benchmark_results_{timestamp}.json"
        filepath = Path(__file__).parent / filename
        
        with open(filepath, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        print(f"  💾 Results saved to: {filepath}")
        
    def print_summary(self):
        """Print benchmark summary."""
        print("\n📊 BENCHMARK SUMMARY")
        print("=" * 50)
        print(f"Total Messages: {self.results['total_messages']}")
        print(f"Local First: {self.results['local_first']['count']} ({self.results['local_first']['success_rate']}%)")
        print(f"CMP Fallback: {self.results['cmp_fallback']['count']} ({self.results['cmp_fallback']['success_rate']}%)")
        print(f"Routing Failed: {self.results['routing_failed']['count']}")
        
        if self.results['local_first']['count'] > 0:
            print(f"Local First Avg Latency: {self.results['local_first']['avg_latency_ms']}ms")
        if self.results['cmp_fallback']['count'] > 0:
            print(f"CMP Fallback Avg Latency: {self.results['cmp_fallback']['avg_latency_ms']}ms")
            
        print(f"\nNeighbor Distribution:")
        for neighbor_count, count in sorted(self.results['neighbor_distribution'].items()):
            print(f"  {neighbor_count} neighbors: {count} cells")
            
        print(f"\nDepartment Stats:")
        for dept_id, stats in self.results['department_stats'].items():
            print(f"  {dept_id}: {stats['name']} ({stats['agent_count']} agents, {stats['neighbors']} neighbors)")

async def main():
    """Main benchmark function."""
    benchmark = RoutingBenchmark()
    
    try:
        await benchmark.setup()
        await benchmark.run_benchmark(message_count=200)
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        raise
    finally:
        await benchmark.message_bus.stop()

if __name__ == "__main__":
    asyncio.run(main()) 