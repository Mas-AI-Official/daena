"""
Test script for file system monitoring and chat functionality
"""

import asyncio
import time
import os
from pathlib import Path

async def test_file_system():
    """Test file system monitoring functionality"""
    print("🧪 Testing File System Monitoring...")
    
    try:
        # Test file monitor service
        from backend.services.file_monitor import get_file_monitor
        monitor = get_file_monitor()
        
        print(f"✅ File monitor initialized for: {monitor.root_path}")
        
        # Get company structure
        structure = monitor.get_company_structure()
        print(f"✅ Company structure: {structure['total_files']} files in {len(structure['directories'])} directories")
        
        # Get file statistics
        stats = monitor.get_file_statistics()
        print(f"✅ File statistics: {stats['total_files']} files, {round(stats['total_size'] / (1024 * 1024), 2)} MB")
        
        # Test file search
        search_results = monitor.search_files("main.py")
        print(f"✅ File search: Found {len(search_results)} files matching 'main.py'")
        
        # Test recent changes
        changes = monitor.get_recent_changes(5)
        print(f"✅ Recent changes: {len(changes)} changes tracked")
        
        print("✅ File system monitoring test passed!")
        return True
        
    except Exception as e:
        print(f"❌ File system test failed: {e}")
        return False

async def test_api_endpoints():
    """Test file system API endpoints"""
    print("\n🧪 Testing File System API Endpoints...")
    
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            # Test company overview endpoint
            response = await client.get("http://localhost:8000/api/v1/files/company-overview")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Company overview: {data['company_status']['total_files']} files, {data['organization']['agents']} agents")
            else:
                print(f"❌ Company overview failed: {response.status_code}")
                return False
            
            # Test file structure endpoint
            response = await client.get("http://localhost:8000/api/v1/files/structure")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ File structure: {data['total_files']} files")
            else:
                print(f"❌ File structure failed: {response.status_code}")
                return False
            
            # Test file search endpoint
            response = await client.get("http://localhost:8000/api/v1/files/search?query=main.py")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ File search: Found {data['count']} files")
            else:
                print(f"❌ File search failed: {response.status_code}")
                return False
        
        print("✅ API endpoints test passed!")
        return True
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False

async def test_daena_responses():
    """Test Daena's enhanced responses with file system awareness"""
    print("\n🧪 Testing Daena's File System Awareness...")
    
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            # Test company analysis request
            response = await client.post("http://localhost:8000/api/v1/daena/chat", 
                json={"message": "Analyze my company structure and files", "user_id": "test"})
            
            if response.status_code == 200:
                data = response.json()
                if "Company File System Analysis" in data.get('response', ''):
                    print("✅ Daena can analyze company structure")
                else:
                    print("⚠️ Daena response doesn't contain file analysis")
            else:
                print(f"❌ Daena chat failed: {response.status_code}")
                return False
            
            # Test agent roles request
            response = await client.post("http://localhost:8000/api/v1/daena/chat", 
                json={"message": "What are the agent roles?", "user_id": "test"})
            
            if response.status_code == 200:
                data = response.json()
                if "Detailed Agent Analysis" in data.get('response', ''):
                    print("✅ Daena can provide detailed agent roles")
                else:
                    print("⚠️ Daena response doesn't contain agent analysis")
            else:
                print(f"❌ Daena chat failed: {response.status_code}")
                return False
        
        print("✅ Daena responses test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Daena test failed: {e}")
        return False

async def main():
    """Run all tests"""
    print("🚀 Starting Comprehensive Test Suite...")
    print("=" * 50)
    
    results = []
    
    # Test file system monitoring
    results.append(await test_file_system())
    
    # Test API endpoints
    results.append(await test_api_endpoints())
    
    # Test Daena responses
    results.append(await test_daena_responses())
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = sum(results)
    total = len(results)
    
    for i, result in enumerate(results):
        status = "✅ PASSED" if result else "❌ FAILED"
        test_name = ["File System", "API Endpoints", "Daena Responses"][i]
        print(f"  {test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is working correctly.")
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    asyncio.run(main()) 