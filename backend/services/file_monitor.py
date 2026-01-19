"""
File System Monitor Service
Gives Daena real-time awareness of her company structure and files
"""

import os
import time
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Set, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging

logger = logging.getLogger(__name__)

class FileChangeHandler(FileSystemEventHandler):
    """Handles file system change events"""
    
    def __init__(self, monitor_service):
        self.monitor_service = monitor_service
    
    def _should_ignore_file(self, file_path: str) -> bool:
        """Check if file should be ignored"""
        ignore_patterns = [
            '.lock', '.tmp', '.git/refs/remotes', '.git/objects/maintenance',
            '__pycache__', '.pyc', '.pyo', '.pyd', '.gitignore',
            '.gitkeep', 'index.lock', 'HEAD.lock', 'maintenance.lock',
            'test_permissions.txt'  # Ignore test files
        ]
        
        # Convert to lowercase for case-insensitive matching
        file_path_lower = file_path.lower()
        
        # Check for git-related patterns
        if any(pattern in file_path_lower for pattern in ignore_patterns):
            return True
            
        # Check for git directory patterns more specifically
        git_patterns = [
            '.git\\', '.git/', 'xtts_temp\\.git', 'xtts_temp/.git'
        ]
        if any(pattern in file_path for pattern in git_patterns):
            return True
            
        return False
    
    def on_created(self, event):
        if not event.is_directory and not self._should_ignore_file(event.src_path):
            try:
                self.monitor_service.file_created(event.src_path)
            except Exception as e:
                # Silently ignore errors for ignored files
                pass
    
    def on_deleted(self, event):
        if not event.is_directory and not self._should_ignore_file(event.src_path):
            try:
                self.monitor_service.file_deleted(event.src_path)
            except Exception as e:
                # Silently ignore errors for ignored files
                pass
    
    def on_modified(self, event):
        if not event.is_directory and not self._should_ignore_file(event.src_path):
            try:
                self.monitor_service.file_modified(event.src_path)
            except Exception as e:
                # Silently ignore errors for ignored files
                pass
    
    def on_moved(self, event):
        if not event.is_directory and not self._should_ignore_file(event.src_path):
            try:
                self.monitor_service.file_moved(event.src_path, event.dest_path)
            except Exception as e:
                # Silently ignore errors for ignored files
                pass

class FileMonitorService:
    """Monitors file system changes and provides real-time company awareness"""
    
    def __init__(self, root_path: str = None):
        self.root_path = root_path or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.observer = Observer()
        self.handler = FileChangeHandler(self)
        self.file_cache: Dict[str, dict] = {}
        self.directory_structure: Dict[str, dict] = {}
        self.change_history: List[dict] = []
        self.last_scan = 0
        self.scan_interval = 30  # seconds
        
        # Initialize file cache in background to avoid blocking
        import threading
        scan_thread = threading.Thread(target=self.scan_file_system, daemon=True)
        scan_thread.start()
        
        # Start monitoring
        self.start_monitoring()
    
    def _should_ignore_file(self, file_path: str) -> bool:
        """Check if a file should be ignored during monitoring"""
        if not file_path:
            return True
            
        # Convert to string if it's a Path object
        file_path = str(file_path)
        
        # Skip hidden files and directories
        if any(part.startswith('.') for part in Path(file_path).parts):
            return True
            
        # Skip common temporary and cache directories
        skip_dirs = {
            '__pycache__', 'node_modules', 'venv', '.git', 'xtts_temp',
            '.pytest_cache', '.coverage', 'htmlcov', 'dist', 'build',
            '.mypy_cache', '.ruff_cache', '.cache', 'logs', 'temp'
        }
        
        if any(part in skip_dirs for part in Path(file_path).parts):
            return True
            
        # Skip common temporary files
        skip_extensions = {
            '.tmp', '.temp', '.log', '.lock', '.pid', '.swp', '.swo',
            '.pyc', '.pyo', '.pyd', '.so', '.dll', '.exe', '.dmg',
            '.zip', '.tar', '.gz', '.rar', '.7z', '.iso'
        }
        
        if Path(file_path).suffix.lower() in skip_extensions:
            return True
            
        # Skip git-related files
        if '.git' in file_path or file_path.endswith('.gitignore'):
            return True
            
        # Skip lock files
        if file_path.endswith('.lock') or 'lock' in Path(file_path).name:
            return True
            
        # Skip system files
        if file_path.startswith('/proc/') or file_path.startswith('/sys/'):
            return True
            
        return False

    def start_monitoring(self):
        """Start file system monitoring"""
        try:
            self.observer.schedule(self.handler, self.root_path, recursive=True)
            self.observer.start()
            logger.info(f"File monitoring started for: {self.root_path}")
        except Exception as e:
            logger.error(f"Failed to start file monitoring: {e}")
    
    def stop_monitoring(self):
        """Stop file system monitoring"""
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.info("File monitoring stopped")
    
    def scan_file_system(self):
        """Scan entire file system and build cache"""
        logger.info("Scanning file system...")
        self.file_cache.clear()
        self.directory_structure.clear()
        
        for root, dirs, files in os.walk(self.root_path):
            # Skip certain directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules', 'venv', '.git', 'xtts_temp']]
            
            for file in files:
                file_path = os.path.join(root, file)
                # Use the same filtering logic for consistency
                if not self._should_ignore_file(file_path):
                    self._add_file_to_cache(file_path)
        
        self.last_scan = time.time()
        logger.info(f"File system scan complete. Found {len(self.file_cache)} files")
    
    def _add_file_to_cache(self, file_path: str):
        """Add a file to the cache"""
        try:
            # Skip files that should be ignored
            if self._should_ignore_file(file_path):
                return
                
            # Check if file still exists (may have been deleted during processing)
            if not os.path.exists(file_path):
                return
                
            rel_path = os.path.relpath(file_path, self.root_path)
            stat = os.stat(file_path)
            
            # Calculate file hash for change detection
            file_hash = self._calculate_file_hash(file_path)
            
            self.file_cache[rel_path] = {
                'path': rel_path,
                'full_path': file_path,
                'size': stat.st_size,
                'modified': stat.st_mtime,
                'hash': file_hash,
                'type': self._get_file_type(file_path),
                'extension': Path(file_path).suffix,
                'directory': os.path.dirname(rel_path)
            }
            
            # Update directory structure
            self._update_directory_structure(rel_path)
            
        except Exception as e:
            logger.error(f"Error adding file to cache: {file_path} - {e}")
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate MD5 hash of file content"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _get_file_type(self, file_path: str) -> str:
        """Determine file type based on extension and content"""
        ext = Path(file_path).suffix.lower()
        
        if ext in ['.py', '.pyc']:
            return 'python'
        elif ext in ['.js', '.jsx', '.ts', '.tsx']:
            return 'javascript'
        elif ext in ['.html', '.htm']:
            return 'html'
        elif ext in ['.css', '.scss', '.sass']:
            return 'stylesheet'
        elif ext in ['.json', '.xml', '.yaml', '.yml']:
            return 'data'
        elif ext in ['.md', '.txt']:
            return 'documentation'
        elif ext in ['.bat', '.sh', '.ps1']:
            return 'script'
        elif ext in ['.db', '.sqlite']:
            return 'database'
        else:
            return 'other'
    
    def _update_directory_structure(self, file_path: str):
        """Update directory structure with file information"""
        parts = file_path.split(os.sep)
        current = self.directory_structure
        
        for part in parts[:-1]:  # All but the last part (filename)
            if part not in current:
                current[part] = {'files': [], 'subdirs': {}, 'type': 'directory'}
            current = current[part]['subdirs']
        
        # Add file to current directory
        if parts[-1] not in current:
            current[parts[-1]] = {'type': 'file'}
    
    def file_created(self, file_path: str):
        """Handle file creation event"""
        try:
            # Double-check if file should be ignored
            if self._should_ignore_file(file_path):
                return
                
            rel_path = os.path.relpath(file_path, self.root_path)
            self._add_file_to_cache(file_path)
            self._log_change('created', rel_path)
            logger.info(f"File created: {rel_path}")
        except Exception as e:
            # Only log errors for non-ignored files
            if not self._should_ignore_file(file_path):
                logger.error(f"Error handling file creation: {file_path} - {e}")
    
    def file_deleted(self, file_path: str):
        """Handle file deletion event"""
        try:
            # Double-check if file should be ignored
            if self._should_ignore_file(file_path):
                return
                
            rel_path = os.path.relpath(file_path, self.root_path)
            if rel_path in self.file_cache:
                del self.file_cache[rel_path]
                self._log_change('deleted', rel_path)
                logger.info(f"File deleted: {rel_path}")
        except Exception as e:
            # Only log errors for non-ignored files
            if not self._should_ignore_file(file_path):
                logger.error(f"Error handling file deletion: {file_path} - {e}")
    
    def file_modified(self, file_path: str):
        """Handle file modification event"""
        try:
            # Double-check if file should be ignored
            if self._should_ignore_file(file_path):
                return
                
            rel_path = os.path.relpath(file_path, self.root_path)
            if rel_path in self.file_cache:
                old_hash = self.file_cache[rel_path]['hash']
                new_hash = self._calculate_file_hash(file_path)
                
                if old_hash != new_hash:
                    self._add_file_to_cache(file_path)
                    self._log_change('modified', rel_path)
                    logger.info(f"File modified: {rel_path}")
        except Exception as e:
            # Only log errors for non-ignored files
            if not self._should_ignore_file(file_path):
                logger.error(f"Error handling file modification: {file_path} - {e}")
    
    def file_moved(self, old_path: str, new_path: str):
        """Handle file move/rename event"""
        try:
            # Double-check if files should be ignored
            if self._should_ignore_file(old_path) or self._should_ignore_file(new_path):
                return
                
            old_rel = os.path.relpath(old_path, self.root_path)
            new_rel = os.path.relpath(new_path, self.root_path)
            
            if old_rel in self.file_cache:
                # Update the file entry
                self.file_cache[old_rel]['path'] = new_rel
                self.file_cache[old_rel]['full_path'] = new_path
                self.file_cache[new_rel] = self.file_cache.pop(old_rel)
                self._log_change('moved', f"{old_rel} -> {new_rel}")
                logger.info(f"File moved: {old_rel} -> {new_rel}")
        except Exception as e:
            # Only log errors for non-ignored files
            if not (self._should_ignore_file(old_path) or self._should_ignore_file(new_path)):
                logger.error(f"Error handling file move: {old_path} -> {new_path} - {e}")
    
    def _log_change(self, change_type: str, file_path: str):
        """Log file change for history"""
        self.change_history.append({
            'timestamp': time.time(),
            'type': change_type,
            'file': file_path,
            'time_str': time.strftime('%Y-%m-%d %H:%M:%S')
        })
        
        # Keep only last 100 changes
        if len(self.change_history) > 100:
            self.change_history = self.change_history[-100:]
    
    def get_company_structure(self) -> dict:
        """Get current company file structure"""
        return {
            'root_path': self.root_path,
            'total_files': len(self.file_cache),
            'directories': self.directory_structure,
            'last_scan': self.last_scan,
            'scan_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.last_scan))
        }
    
    def get_file_info(self, file_path: str) -> Optional[dict]:
        """Get information about a specific file"""
        return self.file_cache.get(file_path)
    
    def search_files(self, query: str, file_type: str = None) -> List[dict]:
        """Search for files by name or content"""
        results = []
        query_lower = query.lower()
        
        for file_path, file_info in self.file_cache.items():
            if query_lower in file_path.lower():
                if file_type is None or file_info['type'] == file_type:
                    results.append(file_info)
        
        return results
    
    def get_recent_changes(self, limit: int = 10) -> List[dict]:
        """Get recent file changes"""
        return sorted(self.change_history, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    def get_file_statistics(self) -> dict:
        """Get file system statistics"""
        stats = {
            'total_files': len(self.file_cache),
            'file_types': {},
            'extensions': {},
            'total_size': 0,
            'largest_files': [],
            'recent_activity': len([c for c in self.change_history if time.time() - c['timestamp'] < 3600])
        }
        
        for file_info in self.file_cache.values():
            # Count file types
            file_type = file_info['type']
            stats['file_types'][file_type] = stats['file_types'].get(file_type, 0) + 1
            
            # Count extensions
            ext = file_info['extension']
            stats['extensions'][ext] = stats['extensions'].get(ext, 0) + 1
            
            # Total size
            stats['total_size'] += file_info['size']
        
        # Get largest files
        largest_files = sorted(self.file_cache.values(), key=lambda x: x['size'], reverse=True)[:5]
        stats['largest_files'] = [{'path': f['path'], 'size': f['size']} for f in largest_files]
        
        return stats

# Global instance
file_monitor = None

def get_file_monitor() -> FileMonitorService:
    """Get or create global file monitor instance"""
    global file_monitor
    if file_monitor is None:
        file_monitor = FileMonitorService()
    return file_monitor 