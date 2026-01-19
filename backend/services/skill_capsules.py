"""Skill Capsules service for Daena's knowledge management."""
import json
import hashlib
import hmac
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

logger = logging.getLogger(__name__)

@dataclass
class SkillCapsule:
    """Skill capsule structure."""
    id: str
    name: str
    version: str
    description: str
    skills: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: str
    expires_at: Optional[str]
    signature: str
    encrypted: bool = False
    capsule_hash: Optional[str] = None

@dataclass
class CapsuleToken:
    """Signed token for capsule access."""
    token_id: str
    capsule_id: str
    permissions: List[str]
    issued_at: str
    expires_at: str
    signature: str

class SkillCapsuleService:
    """Service for managing skill capsules."""
    
    def __init__(self):
        self.capsules: Dict[str, SkillCapsule] = {}
        self.tokens: Dict[str, CapsuleToken] = {}
        # NO hardcoded defaults - must be set via env
        self.secret_key = os.getenv('CAPSULE_SECRET_KEY')
        if not self.secret_key:
            logger.warning("CAPSULE_SECRET_KEY not set - skill capsules encryption disabled")
            self.secret_key = ""  # Empty string disables encryption
        self.encryption_key = self._generate_encryption_key()
        self.cipher_suite = Fernet(self.encryption_key)
        
        # Initialize with some sample capsules
        self._initialize_sample_capsules()
    
    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key from secret."""
        salt = b'daena-salt-2024'
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.secret_key.encode()))
        return key
    
    def _generate_signature(self, data: str) -> str:
        """Generate HMAC signature for data."""
        return hmac.new(
            self.secret_key.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _verify_signature(self, data: str, signature: str) -> bool:
        """Verify HMAC signature."""
        expected = self._generate_signature(data)
        return hmac.compare_digest(expected, signature)
    
    def _initialize_sample_capsules(self):
        """Initialize with sample skill capsules."""
        sample_capsules = [
            {
                "id": "core-communication",
                "name": "Core Communication Skills",
                "version": "1.0.0",
                "description": "Essential communication and interaction skills",
                "skills": [
                    {"name": "active_listening", "level": "expert", "tags": ["communication", "interaction"]},
                    {"name": "clear_expression", "level": "advanced", "tags": ["communication", "clarity"]},
                    {"name": "empathy", "level": "expert", "tags": ["emotional", "understanding"]}
                ],
                "metadata": {"category": "communication", "priority": "high"}
            },
            {
                "id": "strategic-thinking",
                "name": "Strategic Thinking Framework",
                "version": "1.0.0",
                "description": "Strategic analysis and decision-making capabilities",
                "skills": [
                    {"name": "pattern_recognition", "level": "expert", "tags": ["analysis", "strategy"]},
                    {"name": "scenario_planning", "level": "advanced", "tags": ["planning", "futures"]},
                    {"name": "risk_assessment", "level": "advanced", "tags": ["risk", "evaluation"]}
                ],
                "metadata": {"category": "strategy", "priority": "high"}
            }
        ]
        
        for capsule_data in sample_capsules:
            self.create_capsule(**capsule_data)
    
    def create_capsule(self, id: str, name: str, version: str, description: str,
                       skills: List[Dict[str, Any]], metadata: Dict[str, Any],
                       expires_at: Optional[str] = None) -> SkillCapsule:
        """Create a new skill capsule."""
        if id in self.capsules:
            raise ValueError(f"Capsule {id} already exists")
        
        # Create capsule
        capsule = SkillCapsule(
            id=id,
            name=name,
            version=version,
            description=description,
            skills=skills,
            metadata=metadata,
            created_at=datetime.now().isoformat(),
            expires_at=expires_at,
            signature="",
            encrypted=False
        )
        
        # Generate signature
        data_to_sign = f"{id}:{name}:{version}:{description}"
        capsule.signature = self._generate_signature(data_to_sign)
        
        # Generate hash
        capsule.capsule_hash = self._calculate_capsule_hash(capsule)
        
        # Store capsule
        self.capsules[id] = capsule
        
        logger.info(f"Created skill capsule: {id} ({name})")
        return capsule
    
    def _calculate_capsule_hash(self, capsule: SkillCapsule) -> str:
        """Calculate hash of capsule content."""
        content = json.dumps(asdict(capsule), sort_keys=True, default=str)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def pack_capsule(self, capsule_id: str, include_raw_data: bool = False) -> Dict[str, Any]:
        """Pack a capsule for distribution."""
        if capsule_id not in self.capsules:
            raise ValueError(f"Capsule {capsule_id} not found")
        
        capsule = self.capsules[capsule_id]
        
        # Prepare pack data
        pack_data = {
            "id": capsule.id,
            "name": capsule.name,
            "version": capsule.version,
            "description": capsule.description,
            "skills": capsule.skills,
            "metadata": capsule.metadata,
            "created_at": capsule.created_at,
            "expires_at": capsule.expires_at,
            "signature": capsule.signature,
            "capsule_hash": capsule.capsule_hash
        }
        
        # Encrypt sensitive data if requested
        if not include_raw_data:
            pack_data["skills"] = self._encrypt_skills(capsule.skills)
            pack_data["encrypted"] = True
        
        # Generate pack signature
        pack_content = json.dumps(pack_data, sort_keys=True)
        pack_signature = self._generate_signature(pack_content)
        
        return {
            "pack_id": f"pack_{capsule_id}_{int(time.time())}",
            "capsule": pack_data,
            "pack_signature": pack_signature,
            "packed_at": datetime.now().isoformat(),
            "encrypted": not include_raw_data
        }
    
    def _encrypt_skills(self, skills: List[Dict[str, Any]]) -> str:
        """Encrypt skills data."""
        skills_json = json.dumps(skills)
        encrypted = self.cipher_suite.encrypt(skills_json.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def _decrypt_skills(self, encrypted_skills: str) -> List[Dict[str, Any]]:
        """Decrypt skills data."""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_skills.encode())
            decrypted = self.cipher_suite.decrypt(encrypted_bytes)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"Failed to decrypt skills: {e}")
            return []
    
    def install_capsule(self, pack_data: Dict[str, Any], token: str) -> Dict[str, Any]:
        """Install a capsule from pack data."""
        # Verify token
        if not self._verify_installation_token(token, pack_data["capsule"]["id"]):
            raise ValueError("Invalid or expired installation token")
        
        capsule_data = pack_data["capsule"]
        
        # Verify pack signature
        pack_content = json.dumps(capsule_data, sort_keys=True)
        if not self._verify_signature(pack_content, pack_data["pack_signature"]):
            raise ValueError("Invalid pack signature")
        
        # Check if capsule already exists
        if capsule_data["id"] in self.capsules:
            existing = self.capsules[capsule_data["id"]]
            if existing.version == capsule_data["version"]:
                return {
                    "success": True,
                    "message": f"Capsule {capsule_data['id']} already installed with same version",
                    "capsule_id": capsule_data["id"]
                }
        
        # Create/update capsule
        capsule = SkillCapsule(
            id=capsule_data["id"],
            name=capsule_data["name"],
            version=capsule_data["version"],
            description=capsule_data["description"],
            skills=capsule_data["skills"],
            metadata=capsule_data["metadata"],
            created_at=capsule_data["created_at"],
            expires_at=capsule_data["expires_at"],
            signature=capsule_data["signature"],
            encrypted=capsule_data.get("encrypted", False),
            capsule_hash=capsule_data.get("capsule_hash")
        )
        
        # Decrypt skills if encrypted
        if capsule.encrypted:
            capsule.skills = self._decrypt_skills(capsule.skills)
            capsule.encrypted = False
        
        # Store capsule
        self.capsules[capsule.id] = capsule
        
        logger.info(f"Installed skill capsule: {capsule.id} ({capsule.name})")
        
        return {
            "success": True,
            "message": f"Capsule {capsule.id} installed successfully",
            "capsule_id": capsule.id,
            "skills_count": len(capsule.skills),
            "installed_at": datetime.now().isoformat()
        }
    
    def _verify_installation_token(self, token: str, capsule_id: str) -> bool:
        """Verify installation token."""
        if token not in self.tokens:
            return False
        
        token_data = self.tokens[token]
        
        # Check if token is for this capsule
        if token_data.capsule_id != capsule_id:
            return False
        
        # Check if token is expired
        if datetime.fromisoformat(token_data.expires_at) < datetime.now():
            return False
        
        # Verify token signature
        return self._verify_signature(
            f"{token_data.token_id}:{capsule_id}:{','.join(permissions)}",
            token_data.signature
        )
    
    def generate_installation_token(self, capsule_id: str, permissions: List[str],
                                  expires_in_hours: int = 24) -> str:
        """Generate installation token for a capsule."""
        token_id = f"token_{capsule_id}_{int(time.time())}"
        issued_at = datetime.now().isoformat()
        expires_at = (datetime.now() + timedelta(hours=expires_in_hours)).isoformat()
        
        # Create token
        token = CapsuleToken(
            token_id=token_id,
            capsule_id=capsule_id,
            permissions=permissions,
            issued_at=issued_at,
            expires_at=expires_at,
            signature=""
        )
        
        # Generate signature
        data_to_sign = f"{token_id}:{capsule_id}:{','.join(permissions)}"
        token.signature = self._generate_signature(data_to_sign)
        
        # Store token
        self.tokens[token_id] = token
        
        logger.info(f"Generated installation token for capsule {capsule_id}")
        return token_id
    
    def get_capsule(self, capsule_id: str) -> Optional[SkillCapsule]:
        """Get a capsule by ID."""
        return self.capsules.get(capsule_id)
    
    def list_capsules(self) -> List[Dict[str, Any]]:
        """List all available capsules."""
        return [
            {
                "id": capsule.id,
                "name": capsule.name,
                "version": capsule.version,
                "description": capsule.description,
                "skills_count": len(capsule.skills),
                "created_at": capsule.created_at,
                "expires_at": capsule.expires_at,
                "encrypted": capsule.encrypted
            }
            for capsule in self.capsules.values()
        ]
    
    def search_capsules(self, query: str, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search capsules by query and tags."""
        results = []
        query_lower = query.lower()
        
        for capsule in self.capsules.values():
            # Check if query matches name or description
            if (query_lower in capsule.name.lower() or 
                query_lower in capsule.description.lower()):
                
                # Check tags if specified
                if tags:
                    capsule_tags = []
                    for skill in capsule.skills:
                        capsule_tags.extend(skill.get("tags", []))
                    
                    if not any(tag in capsule_tags for tag in tags):
                        continue
                
                results.append({
                    "id": capsule.id,
                    "name": capsule.name,
                    "version": capsule.version,
                    "description": capsule.description,
                    "skills_count": len(capsule.skills),
                    "tags": list(set(tag for skill in capsule.skills for tag in skill.get("tags", [])))
                })
        
        return results
    
    def delete_capsule(self, capsule_id: str) -> bool:
        """Delete a capsule."""
        if capsule_id not in self.capsules:
            return False
        
        del self.capsules[capsule_id]
        logger.info(f"Deleted skill capsule: {capsule_id}")
        return True

# Global skill capsule service instance
skill_capsule_service = SkillCapsuleService() 