#!/usr/bin/env python3
"""
Pull Qwen models using Ollama API (works even if ollama CLI not in PATH).
"""
import sys
import os
import httpx
import json
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

OLLAMA_BASE_URL = "http://localhost:11434"

def check_ollama():
    """Check if Ollama is running."""
    try:
        response = httpx.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            return True, response.json()
        return False, None
    except Exception as e:
        print(f"❌ Cannot connect to Ollama: {e}")
        return False, None

def pull_model(model_name: str):
    """Pull a model using Ollama API."""
    print(f"Pulling {model_name}...")
    print("This may take a while depending on your internet connection...")
    
    try:
        # Start pull request
        response = httpx.post(
            f"{OLLAMA_BASE_URL}/api/pull",
            json={"name": model_name},
            timeout=None  # No timeout for large downloads
        )
        
        if response.status_code == 200:
            # Stream the response
            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "status" in data:
                            print(f"  {data['status']}")
                        if "completed" in data and data.get("completed") == 100:
                            print(f"✅ Successfully pulled {model_name}")
                            return True
                    except json.JSONDecodeError:
                        continue
            
            print(f"✅ Pull request completed for {model_name}")
            return True
        else:
            print(f"❌ Failed to pull {model_name}: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error pulling {model_name}: {e}")
        return False

def main():
    """Main function."""
    print("=" * 60)
    print("PULL QWEN MODELS FOR DAENA TRAINING")
    print("=" * 60)
    print()
    
    # Check Ollama
    print("Checking Ollama connection...")
    is_running, models_data = check_ollama()
    if not is_running:
        print("❌ Ollama is not running. Please start Ollama first.")
        return 1
    
    print("✅ Ollama is running")
    print()
    
    # Check existing models
    existing_models = []
    if models_data and "models" in models_data:
        existing_models = [m.get("name", "") for m in models_data["models"] if isinstance(m, dict)]
        print(f"Existing models: {', '.join(existing_models)}")
        print()
    
    # Models to pull
    models_to_pull = []
    
    # Check if qwen2.5:7b-instruct exists
    if "qwen2.5:7b-instruct" not in existing_models:
        models_to_pull.append("qwen2.5:7b-instruct")
    else:
        print("✅ qwen2.5:7b-instruct already available")
    
    # Check if qwen2.5:14b-instruct exists
    if "qwen2.5:14b-instruct" not in existing_models:
        models_to_pull.append("qwen2.5:14b-instruct")
    else:
        print("✅ qwen2.5:14b-instruct already available")
    
    print()
    
    if not models_to_pull:
        print("✅ All required models are already available!")
        return 0
    
    # Pull models
    success_count = 0
    for model in models_to_pull:
        print(f"\n{'=' * 60}")
        print(f"Pulling {model}")
        print(f"{'=' * 60}")
        if pull_model(model):
            success_count += 1
        print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Successfully pulled: {success_count}/{len(models_to_pull)} models")
    print()
    
    if success_count == len(models_to_pull):
        print("✅ All models pulled successfully!")
        print()
        print("Next steps:")
        print("  1. Train daena-brain using qwen2.5:14b-instruct")
        print("  2. System will automatically use trained model when available")
        return 0
    else:
        print("⚠️ Some models failed to pull. Check your internet connection.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

