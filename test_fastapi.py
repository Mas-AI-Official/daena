"""Test FastAPI directly to capture any exceptions"""
import sys
print(f"Python: {sys.version}")
print(f"Path: {sys.executable}")

try:
    import fastapi
    print(f"FastAPI version: {fastapi.__version__}")
except Exception as e:
    print(f"FastAPI import error: {e}")

try:
    import starlette
    print(f"Starlette version: {starlette.__version__}")
except Exception as e:
    print(f"Starlette import error: {e}")

try:
    import uvicorn
    print(f"Uvicorn version: {uvicorn.__version__}")
except Exception as e:
    print(f"Uvicorn import error: {e}")

print("\nCreating minimal app...")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Test")

print("Adding CORS middleware...")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
print("CORS added successfully")

@app.get("/")
async def root():
    return {"status": "ok"}

print("\nRunning test request simulation...")
from starlette.testclient import TestClient

try:
    client = TestClient(app)
    response = client.get("/")
    print(f"Response status: {response.status_code}")
    print(f"Response body: {response.json()}")
except Exception as e:
    print(f"Test client error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
