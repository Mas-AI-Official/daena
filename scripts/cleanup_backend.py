
import os
import shutil
from datetime import datetime

# Files to backup and remove (DUPLICATES)
DUPLICATE_FILES = [
    # Agent Builder (keep only agent_builder.py)
    "backend/routes/agent_builder_api.py",
    "backend/routes/agent_builder_simple.py",
    "backend/routes/agent_builder_complete.py",
    "backend/routes/agent_builder_platform.py",
    "backend/routes/agent_builder_api_simple.py",
    
    # Brain (keep only brain.py)
    "backend/routes/brain_status.py",
    "backend/routes/enhanced_brain.py",
    
    # Council (keep only councils.py)
    "backend/routes/council.py",
    "backend/routes/council_approval.py",
    "backend/routes/council_rounds.py",
    "backend/routes/council_status.py",
    "backend/routes/council_v2.py",
    
    # Daena (keep only daena.py)
    "backend/routes/daena_vp.py",
    "backend/routes/daena_decisions.py",
    "backend/routes/daena_tools.py",
    
    # Others
    "backend/routes/health_routing.py",
    "backend/routes/llm_status.py",
    "backend/routes/websocket_fallback.py",
    "backend/routes/workspace_v2.py",
    "backend/routes/founder_panel.py",
    "backend/routes/voice_agents.py",
    "backend/routes/voice_panel.py",
    "backend/routes/ocr_fallback.py",
    "backend/routes/strategic_meetings.py",
    "backend/routes/strategic_room.py",
]

def cleanup():
    # Use absolute path for root to be safe, assuming script is run from project root or checks relative
    # Better to assume script runs from D:\Ideas\Daena_old_upgrade_20251213
    
    current_dir = os.getcwd()
    print(f"Running cleanup from: {current_dir}")
    
    backup_dir = f"backup_backend_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    removed_count = 0
    
    for file_path in DUPLICATE_FILES:
        # Check if full path exists
        full_path = os.path.abspath(file_path)
        if os.path.exists(full_path):
            # Backup
            # Maintain folder structure in backup? Or just flat? Prompt said copy2 to backup_dir
            # Flat is safer for now unless collisions
            dest_name = os.path.basename(file_path)
            shutil.copy2(full_path, os.path.join(backup_dir, dest_name))
            
            # Remove
            os.remove(full_path)
            print(f"✓ Removed: {file_path}")
            removed_count += 1
        else:
             print(f"Skipped (not found): {file_path}")
    
    print(f"\n✅ Cleanup complete. {removed_count} files removed.")
    print(f"Backups stored in: {os.path.abspath(backup_dir)}")

if __name__ == "__main__":
    cleanup()
