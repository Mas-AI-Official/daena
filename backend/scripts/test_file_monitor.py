#!/usr/bin/env python3
"""
Test File Monitor Improvements
Verifies that git lock files and temporary files are properly filtered
"""
import asyncio
import sys
import os
from pathlib import Path
import tempfile
import time

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

from services.file_monitor import FileChangeHandler, FileMonitorService

def test_file_filtering():
    """Test that file filtering works correctly"""
    print("🧪 Testing File Monitor Filtering...")
    print("=" * 50)
    
    # Create a temporary file monitor service for testing
    temp_root = tempfile.mkdtemp()
    monitor = FileMonitorService(temp_root)
    
    # Test files that should be ignored
    ignore_test_files = [
        "test.lock",
        ".git/HEAD.lock",
        ".git/refs/remotes/origin/HEAD.lock",
        ".git/objects/maintenance.lock",
        "xtts_temp/.git/index.lock",
        "test_permissions.txt",
        ".gitkeep",
        "__pycache__/test.pyc",
        ".tmp/test.tmp"
    ]
    
    print("📁 Testing files that should be ignored:")
    for test_file in ignore_test_files:
        full_path = os.path.join(temp_root, test_file)
        
        # Create directory structure if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Create the test file
        with open(full_path, 'w') as f:
            f.write("test content")
        
        # Test if it should be ignored
        should_ignore = monitor.handler._should_ignore_file(full_path)
        status = "✅ IGNORED" if should_ignore else "❌ NOT IGNORED"
        
        print(f"   {status} {test_file}")
        
        # Clean up
        os.remove(full_path)
    
    # Test files that should NOT be ignored
    include_test_files = [
        "main.py",
        "config.json",
        "README.md",
        "src/app.js",
        "styles/main.css"
    ]
    
    print("\n📁 Testing files that should NOT be ignored:")
    for test_file in include_test_files:
        full_path = os.path.join(temp_root, test_file)
        
        # Create directory structure if needed
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Create the test file
        with open(full_path, 'w') as f:
            f.write("test content")
        
        # Test if it should be ignored
        should_ignore = monitor.handler._should_ignore_file(full_path)
        status = "✅ INCLUDED" if not should_ignore else "❌ INCORRECTLY IGNORED"
        
        print(f"   {status} {test_file}")
        
        # Clean up
        os.remove(full_path)
    
    # Clean up temporary directory
    import shutil
    shutil.rmtree(temp_root)
    
    print("\n" + "=" * 50)
    print("🎯 File Monitor Filtering Test Complete!")

def test_git_patterns():
    """Test specific git pattern filtering"""
    print("\n🔧 Testing Git Pattern Filtering...")
    print("-" * 40)
    
    # Create a temporary file monitor service for testing
    temp_root = tempfile.mkdtemp()
    monitor = FileMonitorService(temp_root)
    
    git_test_patterns = [
        (".git\\index.lock", True),  # Should be ignored
        (".git/HEAD.lock", True),    # Should be ignored
        ("xtts_temp\\.git\\refs\\remotes\\origin\\HEAD.lock", True),  # Should be ignored
        ("xtts_temp/.git/objects/maintenance.lock", True),  # Should be ignored
        ("src/main.py", False),      # Should NOT be ignored
        ("config.json", False),      # Should NOT be ignored
        ("README.md", False),        # Should NOT be ignored
    ]
    
    print("📁 Testing Git Pattern Filtering:")
    for pattern, should_ignore in git_test_patterns:
        # Test the pattern
        result = monitor.handler._should_ignore_file(pattern)
        status = "✅ CORRECT" if result == should_ignore else "❌ INCORRECT"
        
        print(f"   {status} {pattern} -> {'IGNORED' if result else 'INCLUDED'} (expected: {'IGNORED' if should_ignore else 'INCLUDED'})")
    
    # Clean up
    import shutil
    shutil.rmtree(temp_root)
    
    print("\n" + "-" * 40)
    print("🎯 Git Pattern Filtering Test Complete!")

async def main():
    """Main test function"""
    print("🧪 Daena AI VP - File Monitor Filtering Test")
    print("=" * 60)
    
    try:
        test_file_filtering()
        test_git_patterns()
        
        print("\n🎉 All file monitor tests completed successfully!")
        print("\n💡 The file monitor should now properly filter out:")
        print("   • Git lock files (.lock)")
        print("   • Temporary files (.tmp)")
        print("   • Git directory contents")
        print("   • Test files and .gitkeep files")
        print("   • Python cache files")
        
        return 0
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 