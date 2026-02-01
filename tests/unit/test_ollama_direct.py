import httpx
import asyncio

async def test_ollama():
    print("Testing Ollama direct...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "http://127.0.0.1:11434/api/generate",
            json={
                "model": "deepseek-r1:8b", 
                "prompt": "Say hello in one word",
                "stream": False
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")

if __name__ == "__main__":
    asyncio.run(test_ollama())
