import socket
import asyncio
import httpx
import sys

async def test_connect():
    print(f"Python version: {sys.version}")
    
    # 1. Test DNS resolution via socket
    print("\n1. Testing DNS resolution for api.notion.com...")
    try:
        ip = socket.gethostbyname("api.notion.com")
        print(f"   Success: Resolved to {ip}")
    except Exception as e:
        print(f"   Failed: {e}")

    # 2. Test HTTP connection via httpx (async)
    print("\n2. Testing HTTPS connection to api.notion.com (httpx)...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("https://api.notion.com/v1/users/me") # Expect 401 but connection should work
            print(f"   Success: Status {resp.status_code}")
    except Exception as e:
        print(f"   Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connect())
