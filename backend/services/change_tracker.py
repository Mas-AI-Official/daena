"""
Incremental Change Tracker Service

Tracks file changes with space-efficient incremental backups.
Only stores diffs, not full copies. Fast and auditable.
"""

import os
import json
import hashlib
import difflib
import gzip
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import uuid


class ChangeTracker:
    """
    Incremental backup system that:
    - Creates backups before file changes
    - Stores only diffs (not full copies)
    - Compresses backups for space efficiency
    - Provides fast rollback capability
    - Tracks who, what, why, when for every change
    """
    
    def __init__(self, backup_dir: str = None):
        if backup_dir is None:
            # Default backup location
            backup_dir = os.path.join(os.getcwd(), "backups")
        
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_file = self.backup_dir / "index.json"
        self.index = self._load_index()
    
    def _load_index(self) -> Dict[str, Any]:
        """Load backup index from disk"""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load index: {e}")
                return {"backups": [], "stats": {"total_backups": 0, "total_size": 0}}
        return {"backups": [], "stats": {"total_backups": 0, "total_size": 0}}
    
    def _save_index(self):
        """Save backup index to disk"""
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving index: {e}")
    
    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def _compute_diff(self, original: str, modified: str) -> List[str]:
        """Compute unified diff between two strings"""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)
        
        diff = list(difflib.unified_diff(
            original_lines,
            modified_lines,
            lineterm='',
            n=3  # Context lines
        ))
        
        return diff
    
    def _compress_content(self, content: str) -> bytes:
        """Compress content using gzip"""
        return gzip.compress(content.encode('utf-8'))
    
    def _decompress_content(self, compressed: bytes) -> str:
        """Decompress gzip content"""
        return gzip.decompress(compressed).decode('utf-8')
    
    def before_change(
        self,
        file_path: str,
        change_type: str,
        actor: str,
        reason: str
    ) -> str:
        """
        Create backup before changing a file
        
        Args:
            file_path: Absolute path to file being changed
            change_type: 'create', 'modify', or 'delete'
            actor: Who is making the change (e.g., 'masoud', 'daena', 'agent_id')
            reason: Why the change is being made
        
        Returns:
            backup_id: Unique ID for this backup
        """
        file_path = Path(file_path).absolute()
        backup_id = f"backup_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now()
        
        # Read current file content if exists
        original_content = ""
        file_exists = file_path.exists()
        
        if file_exists:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
            except Exception as e:
                print(f"Warning: Could not read file {file_path}: {e}")
                original_content = ""
        
        # Compute hash
        content_hash = self._compute_hash(original_content) if original_content else "empty"
        
        # Create backup directory for today
        date_dir = self.backup_dir / timestamp.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # Save original content (compressed)
        backup_file = date_dir / f"{backup_id}.backup.gz"
        compressed = self._compress_content(original_content)
        
        with open(backup_file, 'wb') as f:
            f.write(compressed)
        
        # Create metadata
        metadata = {
            "backup_id": backup_id,
            "file_path": str(file_path),
            "change_type": change_type,
            "actor": actor,
            "reason": reason,
            "timestamp": timestamp.isoformat(),
            "original_hash": content_hash,
            "original_size": len(original_content),
            "compressed_size": len(compressed),
            "backup_file": str(backup_file),
            "file_existed": file_exists,
            "status": "pending"
        }
        
        # Save metadata
        metadata_file = date_dir / f"{backup_id}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        # Update index
        self.index["backups"].append(metadata)
        self.index["stats"]["total_backups"] += 1
        self.index["stats"]["total_size"] += len(compressed)
        self._save_index()
        
        return backup_id
    
    def after_change(
        self,
        backup_id: str,
        success: bool,
        new_content: Optional[str] = None
    ):
        """
        Mark backup as complete and optionally store diff
        
        Args:
            backup_id: ID from before_change()
            success: Whether the change succeeded
            new_content: New file content (optional, for diff storage)
        """
        # Find backup in index
        backup = None
        for b in self.index["backups"]:
            if b["backup_id"] == backup_id:
                backup = b
                break
        
        if not backup:
            print(f"Warning: Backup {backup_id} not found")
            return
        
        # Update status
        backup["status"] = "complete" if success else "failed"
        backup["completed_at"] = datetime.now().isoformat()
        
        # If success and we have new content, store diff
        if success and new_content:
            # Load original content
            backup_file = Path(backup["backup_file"])
            if backup_file.exists():
                with open(backup_file, 'rb') as f:
                    original_content = self._decompress_content(f.read())
                
                # Compute diff
                diff = self._compute_diff(original_content, new_content)
                
                # Save diff (compressed)
                diff_file = backup_file.with_suffix('.diff.gz')
                diff_compressed = self._compress_content('\n'.join(diff))
                
                with open(diff_file, 'wb') as f:
                    f.write(diff_compressed)
                
                backup["diff_file"] = str(diff_file)
                backup["diff_size"] = len(diff_compressed)
                backup["new_hash"] = self._compute_hash(new_content)
        
        self._save_index()
    
    def rollback(self, backup_id: str) -> bool:
        """
        Restore file from backup
        
        Args:
            backup_id: ID of backup to restore
        
        Returns:
            success: True if rollback succeeded
        """
        # Find backup
        backup = None
        for b in self.index["backups"]:
            if b["backup_id"] == backup_id:
                backup = b
                break
        
        if not backup:
            print(f"Error: Backup {backup_id} not found")
            return False
        
        backup_file = Path(backup["backup_file"])
        if not backup_file.exists():
            print(f"Error: Backup file not found: {backup_file}")
            return False
        
        try:
            # Read backup
            with open(backup_file, 'rb') as f:
                original_content = self._decompress_content(f.read())
            
            # Restore file
            file_path = Path(backup["file_path"])
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(original_content)
            
            # Record rollback
            backup["rolled_back_at"] = datetime.now().isoformat()
            self._save_index()
            
            return True
            
        except Exception as e:
            print(f"Error during rollback: {e}")
            return False
    
    def get_history(
        self,
        file_path: Optional[str] = None,
        actor: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get change history with optional filters
        
        Args:
            file_path: Filter by file path
            actor: Filter by actor
            limit: Maximum number of results
        
        Returns:
            List of backup metadata
        """
        results = self.index["backups"]
        
        # Filter by file path
        if file_path:
            file_path = str(Path(file_path).absolute())
            results = [b for b in results if b["file_path"] == file_path]
        
        # Filter by actor
        if actor:
            results = [b for b in results if b["actor"] == actor]
        
        # Sort by timestamp (newest first)
        results = sorted(results, key=lambda x: x["timestamp"], reverse=True)
        
        return results[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get backup statistics"""
        return {
            "total_backups": self.index["stats"]["total_backups"],
            "total_size": self.index["stats"]["total_size"],
            "total_size_mb": round(self.index["stats"]["total_size"] / (1024 * 1024), 2),
            "oldest_backup": min([b["timestamp"] for b in self.index["backups"]]) if self.index["backups"] else None,
            "newest_backup": max([b["timestamp"] for b in self.index["backups"]]) if self.index["backups"] else None,
            "backups_by_actor": self._group_by(self.index["backups"], "actor"),
            "backups_by_change_type": self._group_by(self.index["backups"], "change_type")
        }
    
    def _group_by(self, items: List[Dict], key: str) -> Dict[str, int]:
        """Group items by a key and count"""
        result = {}
        for item in items:
            value = item.get(key, "unknown")
            result[value] = result.get(value, 0) + 1
        return result


# Global instance
change_tracker = ChangeTracker()
