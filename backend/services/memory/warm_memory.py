"""
L2 WARM Memory — NBMF Encoded Knowledge Storage

Stores data in compressed Neural Bytecode format.
Supports both lossless and semantic compression modes.

Part of NBMF (Neural Bytecode Memory Format) architecture.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
import json
import zlib
import base64
import hashlib
from datetime import datetime, timezone
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import os

logger = logging.getLogger(__name__)


class WarmMemory:
    """
    L2 WARM tier - NBMF encoded knowledge storage.
    
    Features:
    - Zlib/Brotli compression
    - Optional AES-256 encryption
    - Lossless or semantic modes
    - Progressive aging support
    """
    
    def __init__(self, encryption_key: Optional[bytes] = None):
        self._storage_dir = Path(__file__).parent.parent.parent.parent / ".l2_store" / "warm"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Encryption setup
        if encryption_key:
            self._fernet = Fernet(encryption_key)
        else:
            self._fernet = self._create_default_fernet()
        
        # Index
        self._index_path = self._storage_dir / "index.json"
        self._index: Dict[str, Dict[str, Any]] = {}
        self._load_index()
    
    def _create_default_fernet(self) -> Fernet:
        """Create default Fernet key (in production, use vault/env)."""
        # Derive key from machine-specific info
        salt = b"daena_nbmf_salt_v1"
        password = f"daena_{os.name}_{os.getenv('COMPUTERNAME', 'default')}".encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return Fernet(key)
    
    def _load_index(self):
        """Load storage index."""
        if self._index_path.exists():
            try:
                with open(self._index_path, "r") as f:
                    self._index = json.load(f)
            except Exception as e:
                logger.error(f"Failed to load WARM index: {e}")
    
    def _save_index(self):
        """Save storage index."""
        try:
            with open(self._index_path, "w") as f:
                json.dump(self._index, f)
        except Exception as e:
            logger.error(f"Failed to save WARM index: {e}")
    
    def store(self, item_id: str, content: str, lossless: bool = False, encrypt: bool = True) -> int:
        """
        Store content in WARM tier.
        
        Args:
            item_id: Unique identifier
            content: Text content to store
            lossless: If True, store exactly; if False, may summarize
            encrypt: If True, encrypt at rest
            
        Returns:
            Compressed size in bytes
        """
        original_size = len(content.encode())
        
        # Step 1: Compress
        if lossless:
            compressed = self._compress_lossless(content)
        else:
            compressed = self._compress_semantic(content)
        
        # Step 2: Encrypt if requested
        if encrypt:
            compressed = self._encrypt(compressed)
        
        # Step 3: Write to storage
        file_path = self._storage_dir / f"{item_id}.nbmf"
        with open(file_path, "wb") as f:
            f.write(compressed)
        
        # Step 4: Update index
        self._index[item_id] = {
            "original_size": original_size,
            "compressed_size": len(compressed),
            "lossless": lossless,
            "encrypted": encrypt,
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "hash": hashlib.sha256(content.encode()).hexdigest()[:32]
        }
        self._save_index()
        
        compression_ratio = original_size / len(compressed) if len(compressed) > 0 else 0
        logger.debug(
            f"Stored {item_id}: {original_size}b → {len(compressed)}b "
            f"(ratio: {compression_ratio:.1f}x, lossless: {lossless})"
        )
        
        return len(compressed)
    
    def recall(self, item_id: str) -> Optional[str]:
        """Recall content from WARM tier."""
        if item_id not in self._index:
            return None
        
        file_path = self._storage_dir / f"{item_id}.nbmf"
        if not file_path.exists():
            return None
        
        meta = self._index[item_id]
        
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            
            # Decrypt if needed
            if meta.get("encrypted", False):
                data = self._decrypt(data)
            
            # Decompress
            content = self._decompress(data)
            return content
            
        except Exception as e:
            logger.error(f"Failed to recall {item_id}: {e}")
            return None
    
    def _compress_lossless(self, content: str) -> bytes:
        """
        Lossless compression using zlib.
        
        For production NBMF, could use:
        - Brotli
        - Zstd
        - Custom neural encoder
        """
        return zlib.compress(content.encode(), level=9)
    
    def _compress_semantic(self, content: str) -> bytes:
        """
        Semantic compression - preserves meaning, may change phrasing.
        
        For production NBMF, this would use a learned encoder:
        - Train autoencoder on domain data
        - Map text → latent vector (256-2048 dims)
        - Compress latent vector
        
        For now, uses summarization + compression.
        """
        # Simple semantic compression: remove redundancy, compress
        content = self._remove_redundancy(content)
        return zlib.compress(content.encode(), level=9)
    
    def _remove_redundancy(self, content: str) -> str:
        """Remove obvious redundancy from content."""
        lines = content.split("\n")
        
        # Remove duplicate lines
        seen = set()
        unique_lines = []
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and line_stripped not in seen:
                seen.add(line_stripped)
                unique_lines.append(line)
        
        # Remove excessive whitespace
        result = "\n".join(unique_lines)
        result = " ".join(result.split())
        
        return result
    
    def _decompress(self, data: bytes) -> str:
        """Decompress NBMF data."""
        return zlib.decompress(data).decode()
    
    def _encrypt(self, data: bytes) -> bytes:
        """Encrypt with AES-256 (via Fernet)."""
        return self._fernet.encrypt(data)
    
    def _decrypt(self, data: bytes) -> bytes:
        """Decrypt with AES-256."""
        return self._fernet.decrypt(data)
    
    def verify_integrity(self, item_id: str, content: str) -> bool:
        """Verify content matches stored hash."""
        if item_id not in self._index:
            return False
        
        expected_hash = self._index[item_id].get("hash", "")
        actual_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
        
        return expected_hash == actual_hash
    
    def delete(self, item_id: str) -> bool:
        """Delete item from WARM storage."""
        file_path = self._storage_dir / f"{item_id}.nbmf"
        
        if file_path.exists():
            file_path.unlink()
        
        if item_id in self._index:
            del self._index[item_id]
            self._save_index()
            return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WARM tier statistics."""
        total_original = sum(m.get("original_size", 0) for m in self._index.values())
        total_compressed = sum(m.get("compressed_size", 0) for m in self._index.values())
        
        return {
            "items": len(self._index),
            "total_original_bytes": total_original,
            "total_compressed_bytes": total_compressed,
            "compression_ratio": total_original / total_compressed if total_compressed > 0 else 0,
            "lossless_count": sum(1 for m in self._index.values() if m.get("lossless")),
            "encrypted_count": sum(1 for m in self._index.values() if m.get("encrypted"))
        }
