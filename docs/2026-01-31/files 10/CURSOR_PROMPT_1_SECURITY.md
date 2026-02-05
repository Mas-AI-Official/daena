# CURSOR PROMPT 1: SECURITY HARDENING

You are working in the Mas-AI-Official/daena repository. Fix the critical security issues identified in the gap analysis.

## GOAL
1. Enable authentication properly
2. Enforce execution token requirement  
3. Restrict shell commands to safe operations only
4. Update CORS to include frontend origin
5. Add JWT_SECRET and FOUNDER_APPROVAL_TOKEN to .env
6. Create a secure key vault (Windows Credential Manager integration)

## ACTIONS

### A) Update .env:
```env
# Authentication
DISABLE_AUTH=0
EXECUTION_TOKEN_REQUIRED=true
JWT_SECRET=<generate 64-character random hex string>
FOUNDER_APPROVAL_TOKEN=<generate 64-character random hex string>

# Shell command whitelist (safe operations only)
ALLOWED_SHELL_COMMANDS=dir,ls,cat,type,echo,git,status,log,diff,show

# CORS (include frontend origins)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000

# Governance enforcement
GOVERNANCE_AUTO_APPROVE_LOW_RISK=true
GOVERNANCE_AUTO_APPROVE_MEDIUM_RISK=false  # Changed from true
GOVERNANCE_BLOCK_CRITICAL_RISK=true

# Security
SESSION_TIMEOUT_MINUTES=60
MAX_LOGIN_ATTEMPTS=5
RATE_LIMIT_PER_MINUTE=100
```

### B) Update backend/main.py:
Add authentication middleware to ALL routes:
```python
from backend.security.auth import verify_jwt_token, require_founder_approval

# Add middleware
@app.middleware("http")
async def authenticate_request(request: Request, call_next):
    if request.url.path.startswith("/api/") and not request.url.path.startswith("/api/v1/auth/"):
        token = request.headers.get("Authorization")
        if not token or not verify_jwt_token(token.replace("Bearer ", "")):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized - Invalid or missing token"}
            )
    response = await call_next(request)
    return response
```

### C) Update backend/services/tool_broker.py:
Enforce execution token checks:
```python
async def execute_tool(self, tool_request: ToolRequest, executor_identity: str):
    # 1. Check if execution token is required
    if os.getenv("EXECUTION_TOKEN_REQUIRED") == "true":
        if not tool_request.execution_token:
            raise PermissionError("Execution token required but not provided")
        
        # Verify founder approval token for HIGH/CRITICAL risk
        if tool_request.risk_level in ["HIGH", "CRITICAL"]:
            if tool_request.execution_token != os.getenv("FOUNDER_APPROVAL_TOKEN"):
                raise PermissionError("Founder approval required for HIGH/CRITICAL risk tasks")
    
    # 2. Always block CRITICAL
    if tool_request.risk_level == "CRITICAL":
        raise PermissionError("CRITICAL risk tasks are always blocked")
    
    # 3. Check auto-approval settings
    if tool_request.risk_level == "MEDIUM":
        if os.getenv("GOVERNANCE_AUTO_APPROVE_MEDIUM_RISK") != "true":
            # Add to approval queue
            return await self.queue_for_approval(tool_request)
    
    # 4. Proceed with execution
    return await self._execute(tool_request)
```

### D) Create backend/security/credential_vault.py:
```python
import keyring
from cryptography.fernet import Fernet
import os

class CredentialVault:
    """
    Secure credential storage using Windows Credential Manager (keyring library)
    Never stores passwords in plain text
    """
    
    SERVICE_NAME = "Daena-AI"
    
    @staticmethod
    def store_secret(key: str, value: str):
        """Store a secret securely"""
        keyring.set_password(CredentialVault.SERVICE_NAME, key, value)
    
    @staticmethod
    def get_secret(key: str) -> str:
        """Retrieve a secret"""
        return keyring.get_password(CredentialVault.SERVICE_NAME, key)
    
    @staticmethod
    def delete_secret(key: str):
        """Delete a secret"""
        keyring.delete_password(CredentialVault.SERVICE_NAME, key)
    
    @staticmethod
    def encrypt_data(data: str, key: bytes) -> bytes:
        """Encrypt sensitive data at rest"""
        f = Fernet(key)
        return f.encrypt(data.encode())
    
    @staticmethod
    def decrypt_data(encrypted_data: bytes, key: bytes) -> str:
        """Decrypt sensitive data"""
        f = Fernet(key)
        return f.decrypt(encrypted_data).decode()
    
    @classmethod
    def migrate_env_secrets_to_vault(cls):
        """
        Migrate secrets from .env to credential vault
        Call this once during setup
        """
        secrets_to_migrate = [
            "JWT_SECRET",
            "FOUNDER_APPROVAL_TOKEN",
            "DAENABOT_HANDS_TOKEN",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY"
        ]
        
        for secret_name in secrets_to_migrate:
            value = os.getenv(secret_name)
            if value:
                cls.store_secret(secret_name, value)
                print(f"✓ Migrated {secret_name} to vault")

# Usage in backend:
# Instead of: os.getenv("JWT_SECRET")
# Use: CredentialVault.get_secret("JWT_SECRET")
```

### E) Create backend/security/auth.py:
```python
import jwt
from datetime import datetime, timedelta
from backend.security.credential_vault import CredentialVault

def generate_jwt_token(user_id: str, role: str) -> str:
    """Generate JWT token for authenticated user"""
    secret = CredentialVault.get_secret("JWT_SECRET")
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def verify_jwt_token(token: str) -> dict:
    """Verify JWT token"""
    try:
        secret = CredentialVault.get_secret("JWT_SECRET")
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_founder_approval(token: str) -> bool:
    """Check if token is the founder approval token"""
    founder_token = CredentialVault.get_secret("FOUNDER_APPROVAL_TOKEN")
    return token == founder_token
```

### F) Create backend/routes/auth.py:
```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.security.auth import generate_jwt_token

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
async def login(request: LoginRequest):
    # TODO: Implement proper user authentication
    # For now, hardcode founder credentials (replace with database lookup)
    if request.username == "founder" and request.password == os.getenv("FOUNDER_PASSWORD"):
        token = generate_jwt_token(user_id="founder", role="founder")
        return {"token": token, "role": "founder"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

@router.post("/logout")
async def logout():
    # JWT tokens are stateless, so logout is client-side (delete token)
    return {"message": "Logged out successfully"}
```

## CONSTRAINTS
- Do NOT delete or break existing functionality
- Add proper error messages when auth fails
- Log all security events to audit trail in backend/logs/security.log
- Generate strong secrets (use `secrets.token_hex(32)` in Python)

## DELIVERABLE
Provide:
1. List of all changed files with brief description of changes
2. Confirmation that no plain-text secrets remain in code
3. Instructions for running the migration script
4. Test results showing unauthorized access is blocked

## TESTING CHECKLIST
After implementing:
- [ ] Start backend with DISABLE_AUTH=0
- [ ] Try accessing /api/v1/agents without token → Should get 401 Unauthorized
- [ ] Login as founder → Should get JWT token
- [ ] Access /api/v1/agents with token → Should work
- [ ] Try executing HIGH risk tool without founder approval token → Should be queued for approval
- [ ] Execute LOW risk tool → Should auto-approve
- [ ] Check that secrets are in credential vault, not .env
