"""
Security Input Gate
Centralized validation for inbound content: files, text, and URLs.
"""
import re
import magic  # requires python-magic or python-magic-bin
import logging
from pathlib import Path
from typing import Optional, List, Tuple
from fastapi import UploadFile, HTTPException

logger = logging.getLogger(__name__)

# D-1: Inbound Content Gate
class SecurityGate:
    
    # 1. File Upload Security
    ALLOWED_EXTENSIONS = {
        # Documents
        '.pdf', '.txt', '.md', '.csv', '.xlsx', '.docx', '.pptx',
        # Images
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg',
        # Code (use with caution)
        '.py', '.js', '.ts', '.css', '.html', '.json', '.yaml', '.yml',
        # Audio/Video
        '.mp3', '.wav', '.mp4', '.webm'
    }
    
    Allowed_MIME_TYPES = {
        'application/pdf', 'text/plain', 'text/markdown', 'text/csv',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/svg+xml',
        'audio/mpeg', 'audio/wav', 'video/mp4', 'video/webm'
    }

    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB limit by default

    @staticmethod
    async def validate_file(file: UploadFile, max_size: int = MAX_FILE_SIZE) -> None:
        """
        Validate file upload: size, extension, and content sniffing.
        Raises HTTPException if invalid.
        """
        # 1. Check filename/extension
        filename = file.filename or "unknown"
        ext = Path(filename).suffix.lower()
        if ext not in SecurityGate.ALLOWED_EXTENSIONS:
            logger.warning(f"SecurityGate: Blocked forbidden extension {ext}")
            raise HTTPException(status_code=400, detail="File type not allowed")

        # 2. Check size (this requires reading, so we might read chunks)
        # Note: UploadFile.file IS a SpooledTemporaryFile or similar.
        # We can also check content-length header if trusted, but better to check stream.
        # For simplicity in FastAPI, we assume backend limit logs/rejects huge bodies, 
        # but here we check logically.
        file.file.seek(0, 2)
        size = file.file.tell()
        file.file.seek(0)
        
        if size > max_size:
            raise HTTPException(status_code=413, detail=f"File too large (max {max_size/1024/1024}MB)")

        # 3. Magic Number Check (Content sniffing)
        # Read header
        header = file.file.read(2048)
        file.file.seek(0)
        
        # Determine mime type from content
        try:
             mime_type = magic.from_buffer(header, mime=True)
             # Relaxed check: Only block if it looks like an executable or script when not allowed
             if mime_type == 'application/x-dosexec' or mime_type == 'application/x-executable':
                 raise HTTPException(status_code=400, detail="Executable files are not allowed")
        except Exception:
             # If magic fails, rely on extension whitelist
             pass

    # 2. Prompt Injection Heuristics
    INJECTION_PATTERNS = [
        r"ignore previous instructions",
        r"bypass security",
        r"delete all files",
        r"system override",
        r"you are now .* unlocked",
        r"sudo "
    ]

    @staticmethod
    def scan_for_injection(text: str) -> bool:
        """Return True if prompt injection suspected."""
        text_lower = text.lower()
        for pattern in SecurityGate.INJECTION_PATTERNS:
            if re.search(pattern, text_lower):
                logger.warning(f"SecurityGate: Potential prompt injection detected: '{pattern}'")
                return True
        return False

    # 3. URL Verification (SSRF Prevention)
    BLOCKED_RANGES = [
        # IPv4
        r"^127\.", r"^10\.", r"^192\.168\.", r"^172\.(1[6-9]|2[0-9]|3[0-1])\.", r"^0\.0\.0\.0",
        # Localhost
        r"localhost"
    ]

    @staticmethod
    def validate_url(url: str, allow_local: bool = False) -> None:
        if allow_local:
            return
            
        from urllib.parse import urlparse
        import socket
        
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise HTTPException(status_code=400, detail="Invalid URL")

        # Check blacklist regex
        for pattern in SecurityGate.BLOCKED_RANGES:
            if re.match(pattern, hostname):
                 raise HTTPException(status_code=403, detail="Access to local network resources denied")
        
        # DNS Resolution check (prevent DNS rebinding to internal IP)
        try:
            ip = socket.gethostbyname(hostname)
            for pattern in SecurityGate.BLOCKED_RANGES:
                if re.match(pattern, ip):
                     raise HTTPException(status_code=403, detail="Access to private network denied")
        except socket.error:
            # Failed to resolve? Treat as risky or fail open depending on policy.
            pass

    @staticmethod
    def sanitize_input(text: str) -> str:
        """Basic sanitization."""
        if SecurityGate.scan_for_injection(text):
             # Tag it or reject it. For now, we append a warning tag for the LLM.
             return f"[SYSTEM WARNING: POTENTIAL INJECTION DETECTED] {text}"
        return text

security_gate = SecurityGate()
