
import asyncio
import aiohttp
import json

async def check_skills_debug():
    url = "http://127.0.0.1:8000/api/v1/skills/debug"
    print(f"Checking {url}...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    print(f"❌ Status: {resp.status}")
                    text = await resp.text()
                    print(text)
                    return
                
                data = await resp.json()
                print("✅ Debug Response:")
                print(json.dumps(data, indent=2))
                
                if data.get("success"):
                     stats = data.get("stats", {})
                     total = stats.get("total", 0)
                     print(f"Total Skills: {total}")
                     if total == 0:
                         print("⚠️  No skills found! Check logs.")
                     else:
                         print("✅ Skills are loaded.")
                else:
                    print("❌ Debug call returned success=False")

    except Exception as e:
        print(f"❌ Failed to connect: {e}")

if __name__ == "__main__":
    asyncio.run(check_skills_debug())
