import httpx
import asyncio

async def test_chat():
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "http://127.0.0.1:8000/api/v1/daena/chat",
            json={"message": "Hello, tell me about your department structure"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_chat())
