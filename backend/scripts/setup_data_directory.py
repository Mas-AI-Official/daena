#!/usr/bin/env python3
"""
Setup Data Directory with Proper Permissions
Creates necessary directories for chat history and other data storage
"""
import os
import sys
from pathlib import Path

def setup_data_directory():
    """Setup data directory with proper permissions"""
    print("📁 Setting up data directory structure...")
    print("=" * 50)
    
    # Get project root (two levels up from backend)
    project_root = Path(__file__).parent.parent.parent
    backend_dir = Path(__file__).parent.parent
    
    # Define directories to create
    directories = [
        project_root / "data",
        project_root / "data" / "chat_history",
        project_root / "data" / "logs",
        project_root / "data" / "cache",
        project_root / "data" / "uploads",
        backend_dir / "data",
        backend_dir / "data" / "chat_history",
        backend_dir / "data" / "logs",
        backend_dir / "data" / "cache"
    ]
    
    print("📍 Creating directories:")
    for directory in directories:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            
            # Set permissions (readable/writable by owner)
            os.chmod(directory, 0o755)
            
            print(f"   ✅ {directory}")
            
            # Create a .gitkeep file to ensure directory is tracked
            gitkeep_file = directory / ".gitkeep"
            if not gitkeep_file.exists():
                gitkeep_file.touch()
                
        except Exception as e:
            print(f"   ❌ {directory}: {e}")
    
    # Create initial chat history file if it doesn't exist
    chat_history_file = project_root / "data" / "chat_history" / "sessions.json"
    if not chat_history_file.exists():
        try:
            initial_data = {
                "metadata": {
                    "created": "2025-01-20T00:00:00",
                    "version": "1.0",
                    "description": "Chat history storage for Daena AI VP"
                },
                "sessions": {}
            }
            
            import json
            with open(chat_history_file, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, indent=2, ensure_ascii=False)
            
            print(f"   ✅ Created initial chat history file: {chat_history_file}")
            
        except Exception as e:
            print(f"   ❌ Error creating chat history file: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Data directory setup complete!")
    
    # Test write permissions
    print("\n🧪 Testing write permissions:")
    test_file = project_root / "data" / "test_permissions.txt"
    try:
        with open(test_file, 'w') as f:
            f.write("Test write permission")
        
        # Clean up test file
        test_file.unlink()
        print("   ✅ Write permissions working correctly")
        
    except Exception as e:
        print(f"   ❌ Write permission test failed: {e}")
        print("   💡 You may need to run this script with administrator privileges")

if __name__ == "__main__":
    setup_data_directory() 