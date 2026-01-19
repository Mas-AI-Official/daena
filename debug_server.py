"""Debug server with explicit exception handling"""
import sys
sys.path.insert(0, ".")

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback

app = FastAPI(title="Debug Server")

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all exceptions and print traceback"""
    tb = traceback.format_exc()
    print(f"EXCEPTION in {request.url}:")
    print(tb)
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "traceback": tb}
    )

@app.get("/test")
async def test():
    return {"status": "ok"}

@app.get("/api/v1/founder/dashboard")
async def founder():
    print("In founder/dashboard endpoint")
    from backend.routes.founder_api import get_founder_dashboard
    result = await get_founder_dashboard()
    print(f"Result: {result}")
    return result

if __name__ == "__main__":
    import uvicorn
    print("Starting debug server on port 8003...")
    uvicorn.run(app, host="127.0.0.1", port=8003)
