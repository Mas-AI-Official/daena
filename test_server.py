"""Minimal test server to isolate the startup issue"""
import sys
sys.path.insert(0, ".")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app_test = FastAPI(title="Test Server")

app_test.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Just include founder_api router
print("Importing founder_api...")
from backend.routes.founder_api import router
app_test.include_router(router)
print("Founder API router included!")

@app_test.get("/test")
async def test():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    print("Starting minimal test server on port 8002...")
    uvicorn.run(app_test, host="127.0.0.1", port=8002)
