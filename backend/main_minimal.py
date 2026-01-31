"""
DEPRECATED: Use backend.main:app for full backend. Run: python -m uvicorn backend.main:app
Minimal backend entry point for debugging (kept for reference only).
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Daena Minimal Debug")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"status": "ok", "message": "Minimal backend running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/v1/founder/dashboard")
async def founder_dashboard():
    return {"success": True, "pending_approvals": 0, "learning_stats": {}}

@app.get("/api/v1/departments/")
async def departments():
    return [{"id": 1, "name": "Engineering", "slug": "engineering"}]

if __name__ == "__main__":
    import sys
    print("DEPRECATED: Use backend.main:app. Run: python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000", file=sys.stderr)
    sys.exit(1)
