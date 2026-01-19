import os
import zipfile
import datetime
from pathlib import Path

# Configuration
ROOT_DIR = Path(r"D:\Ideas\Daena_old_upgrade_20251213")
BACKUP_DIR = ROOT_DIR / "backups"
TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_FILENAME = f"pre_fix_{TIMESTAMP}.zip"
BACKUP_PATH = BACKUP_DIR / BACKUP_FILENAME

# Directories and files to include
INCLUDE_DIRS = [
    "backend",
    "frontend",
    "audio",
    "scripts",
    "config",
]

INCLUDE_FILES = [
    "START_DAENA.bat",
    "requirements.txt",
    "requirements_audio.txt",
]

# Extensions to include in root
INCLUDE_EXTENSIONS = [".env", ".py", ".bat", ".json"]

def create_backup():
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir(parents=True)

    print(f"Creating backup at {BACKUP_PATH}...")

    with zipfile.ZipFile(BACKUP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Add specific directories
        for dir_name in INCLUDE_DIRS:
            source_dir = ROOT_DIR / dir_name
            if source_dir.exists():
                for root, _, files in os.walk(source_dir):
                    for file in files:
                        file_path = Path(root) / file
                        # Skip __pycache__ and large model files if any slipped in
                        if "__pycache__" in str(file_path):
                            continue
                        if file_path.suffix in ['.bin', '.safetensors', '.pth', '.gguf']:
                            # Skip large weights just in case, though they should be in models/
                            if file_path.stat().st_size > 100 * 1024 * 1024: # > 100MB
                                print(f"Skipping large file: {file_path}")
                                continue
                        
                        arcname = file_path.relative_to(ROOT_DIR)
                        zipf.write(file_path, arcname)
                        print(f"Added: {arcname}")
            else:
                print(f"Warning: Directory {dir_name} not found.")

        # Add specific files in root
        for file_name in INCLUDE_FILES:
            file_path = ROOT_DIR / file_name
            if file_path.exists():
                zipf.write(file_path, file_name)
                print(f"Added: {file_name}")

        # Add .env and other config files from root
        for file in ROOT_DIR.iterdir():
            if file.is_file():
                if file.name.startswith(".env") or file.suffix in INCLUDE_EXTENSIONS:
                    # Avoid re-adding files already in INCLUDE_FILES
                    if file.name not in INCLUDE_FILES:
                         zipf.write(file, file.name)
                         print(f"Added: {file.name}")

    print(f"✅ Backup created successfully: {BACKUP_PATH}")

if __name__ == "__main__":
    create_backup()
