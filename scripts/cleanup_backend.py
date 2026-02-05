
# scripts/cleanup_backend.py
"""
DAENA BACKEND CLEANUP SCRIPT
Run this BEFORE frontend rebuild
"""

import os
import shutil
from datetime import datetime

# Files to backup and remove (DUPLICATES)
DUPLICATE_FILES = [
    # Agent Builder Consolidation
    "routes/agent_builder_api.py",
    "routes/agent_builder_api_simple.py",
    "routes/agent_builder_complete.py",
    "routes/agent_builder_platform.py",
    "routes/agent_builder_simple.py",
    
    # Brain Consolidation
    "routes/brain_status.py",
    "routes/enhanced_brain.py",
    
    # Council Consolidation
    "routes/council.py",
    "routes/council_approval.py",
    "routes/council_rounds.py",
    "routes/council_status.py",
    "routes/council_v2.py",
    
    # Daena Consolidation
    "routes/daena_decisions.py",
    "routes/daena_tools.py",
    "routes/daena_vp.py",
    
    # Health Consolidation
    "routes/health_routing.py",
    
    # LLM Consolidation
    "routes/llm_status.py",
    
    # WebSocket Consolidation
    "routes/websocket_fallback.py",
    
    # Workspace Consolidation
    "routes/workspace_v2.py",
    
    # Founder Consolidation
    "routes/founder_panel.py",
    
    # Voice Consolidation
    "routes/voice_agents.py",
    "routes/voice_panel.py",
    
    # OCR Consolidation
    "routes/ocr_fallback.py",
    
    # Strategic Consolidation
    "routes/strategic_meetings.py",
    "routes/strategic_room.py",
]

def cleanup_backend():
    # Set backend root
    backend_root = os.path.join(os.getcwd(), 'backend')
    if not os.path.exists(backend_root):
        print(f"Error: backend directory not found at {backend_root}")
        return

    backup_dir = f"backend-BACKUP-{datetime.now().strftime('%Y%m%d')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    for file_path in DUPLICATE_FILES:
        full_path = os.path.join(backend_root, file_path)
        if os.path.exists(full_path):
            # Backup
            try:
                # Create backup subdir structure if needed (flattening for simplicity here)
                backup_dest = os.path.join(backup_dir, os.path.basename(file_path))
                shutil.copy2(full_path, backup_dest)
                # Remove
                os.remove(full_path)
                print(f"✓ Removed: {file_path}")
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
    
    print(f"\n✅ Cleanup complete. Backups in: {backup_dir}")
    print(f"📊 Processed cleanup list.")

if __name__ == "__main__":
    cleanup_backend()
