"""
Demo Authentication for Live Demo
Provides simple PIN-based access control for hackathon demos
"""
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Depends, Request, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import logging

logger = logging.getLogger(__name__)

# Demo configuration
DEMO_PIN = os.getenv("DEMO_PIN", "AI2026")  # Override via environment
DEMO_TOKEN_DURATION_HOURS = int(os.getenv("DEMO_TOKEN_DURATION", "4"))  # Demo session length
DEMO_ENABLED = os.getenv("DEMO_AUTH_ENABLED", "false").lower() == "true"

# Simple token storage (in-memory for demo)
_demo_sessions = {}

security = HTTPBasic()


class DemoSession:
    """Simple demo session"""
    def __init__(self, token: str):
        self.token = token
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(hours=DEMO_TOKEN_DURATION_HOURS)
        self.access_count = 0
        self.last_access = None
    
    def is_valid(self) -> bool:
        return datetime.utcnow() < self.expires_at
    
    def touch(self):
        self.last_access = datetime.utcnow()
        self.access_count += 1


def create_demo_token() -> str:
    """Generate a unique demo session token"""
    token = secrets.token_urlsafe(16)
    _demo_sessions[token] = DemoSession(token)
    logger.info(f"📱 Created demo session token (expires in {DEMO_TOKEN_DURATION_HOURS}h)")
    return token


def validate_demo_token(token: str) -> bool:
    """Check if a demo token is valid"""
    session = _demo_sessions.get(token)
    if session and session.is_valid():
        session.touch()
        return True
    return False


async def verify_demo_pin(credentials: HTTPBasicCredentials = Depends(security)) -> bool:
    """Verify demo PIN (username ignored, password = PIN)"""
    if credentials.password == DEMO_PIN:
        return True
    raise HTTPException(
        status_code=401,
        detail="Invalid demo PIN",
        headers={"WWW-Authenticate": "Basic"}
    )


def get_demo_token_from_cookie(request: Request) -> Optional[str]:
    """Extract demo token from cookie"""
    return request.cookies.get("demo_token")


async def require_demo_auth(request: Request):
    """
    Middleware-style dependency that enforces demo authentication.
    Skip if DEMO_AUTH_ENABLED is false.
    """
    if not DEMO_ENABLED:
        return True
    
    # Check cookie token first
    token = get_demo_token_from_cookie(request)
    if token and validate_demo_token(token):
        return True
    
    # Check Authorization header (Bearer token)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        if validate_demo_token(token):
            return True
    
    raise HTTPException(
        status_code=401,
        detail="Demo authentication required. Please enter the demo PIN.",
        headers={"WWW-Authenticate": "Bearer"}
    )


def set_demo_cookie(response: Response, token: str):
    """Set demo session cookie"""
    response.set_cookie(
        key="demo_token",
        value=token,
        max_age=DEMO_TOKEN_DURATION_HOURS * 3600,
        httponly=True,
        samesite="lax"
    )


# FastAPI routes for demo auth
def register_demo_auth_routes(app):
    """Register demo authentication routes"""
    from fastapi import Form
    from fastapi.responses import HTMLResponse, RedirectResponse
    
    @app.get("/demo/login", response_class=HTMLResponse)
    async def demo_login_page():
        """Show demo login form"""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Daena Demo Access</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: system-ui, -apple-system, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
        }
        .card {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            padding: 40px;
            width: 100%;
            max-width: 400px;
            backdrop-filter: blur(10px);
        }
        h1 {
            font-size: 28px;
            margin-bottom: 8px;
            background: linear-gradient(to right, #fbbf24, #f59e0b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        p { color: #94a3b8; margin-bottom: 24px; }
        label { display: block; margin-bottom: 8px; color: #cbd5e1; }
        input {
            width: 100%;
            padding: 12px 16px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            background: rgba(0, 0, 0, 0.3);
            color: white;
            font-size: 18px;
            letter-spacing: 4px;
            text-align: center;
            margin-bottom: 24px;
        }
        input:focus { outline: none; border-color: #fbbf24; }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(to right, #fbbf24, #f59e0b);
            color: black;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover { transform: scale(1.02); }
        .logo { font-size: 48px; margin-bottom: 16px; }
        .error { color: #f87171; margin-bottom: 16px; text-align: center; }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🏛️</div>
        <h1>Daena Demo</h1>
        <p>Enter the demo access PIN</p>
        <form method="post" action="/demo/login">
            <label for="pin">Demo PIN</label>
            <input type="password" name="pin" id="pin" placeholder="• • • • • •" 
                   pattern="[A-Za-z0-9]+" required autofocus>
            <button type="submit">Enter Demo →</button>
        </form>
    </div>
</body>
</html>
        """
    
    @app.post("/demo/login")
    async def demo_login(response: Response, pin: str = Form(...)):
        """Handle demo login"""
        if pin == DEMO_PIN:
            token = create_demo_token()
            redirect = RedirectResponse(url="/demo", status_code=303)
            set_demo_cookie(redirect, token)
            return redirect
        else:
            return HTMLResponse(
                content="""
                <script>
                    alert('Invalid PIN. Please try again.');
                    window.location.href = '/demo/login';
                </script>
                """,
                status_code=401
            )
    
    @app.get("/demo/logout")
    async def demo_logout(request: Request):
        """Log out of demo"""
        token = get_demo_token_from_cookie(request)
        if token and token in _demo_sessions:
            del _demo_sessions[token]
        
        response = RedirectResponse(url="/demo/login", status_code=303)
        response.delete_cookie("demo_token")
        return response
    
    logger.info("✅ Demo authentication routes registered")
