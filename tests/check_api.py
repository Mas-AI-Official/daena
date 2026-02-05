#!/usr/bin/env python3
import requests
import json

def check_api():
    base_url = "http://localhost:8000"
    
    print("🔍 Checking Daena API endpoints...")
    
    # Check AI capabilities
    try:
        response = requests.get(f"{base_url}/api/v1/ai/capabilities")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ AI Capabilities: {data.get('capabilities', {}).get('agents', 'N/A')} agents, {data.get('capabilities', {}).get('departments', 'N/A')} departments")
        else:
            print(f"❌ AI Capabilities failed: {response.status_code}")
    except Exception as e:
        print(f"❌ AI Capabilities error: {e}")
    
    # Check departments
    try:
        response = requests.get(f"{base_url}/api/v1/departments/?limit=100")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Departments: {len(data)} total")
            for dept in data:
                print(f"   {dept.get('name', 'Unknown')}: {dept.get('agent_count', 0)} agents")
        else:
            print(f"❌ Departments failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Departments error: {e}")
    
    # Check agents
    try:
        response = requests.get(f"{base_url}/api/v1/agents/?limit=100")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Agents: {len(data)} total")
            # Group by department
            dept_counts = {}
            for agent in data:
                dept = agent.get('department', 'Unknown')
                dept_counts[dept] = dept_counts.get(dept, 0) + 1
            
            for dept, count in dept_counts.items():
                print(f"   {dept}: {count} agents")
        else:
            print(f"❌ Agents failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Agents error: {e}")

if __name__ == "__main__":
    check_api() 