import aiohttp
import asyncio

async def test():
    # URL from utils/translation.py
    # f"{TRANSLATION_API_BASE}/{edition}/pages/{page_number}.json"
    base = "https://cdn.jsdelivr.net/gh/fawazahmed0/quran-api@1/editions"
    edition = "eng-mustafakhattaba"
    page = 100
    url = f"{base}/{edition}/{page}.json" 
    # Wait, the code said "{edition}/pages/{page_number}.json"
    # But usually it is .../pages/{page}.json is not standard. 
    # Let's try what the code HAD:
    url_code = f"{base}/{edition}/pages/{page}.json"
    
    print(f"Testing URL: {url_code}")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url_code) as resp:
            print(f"Status: {resp.status}")
            if resp.status == 200:
                try:
                    data = await resp.json()
                    # The code expected data.get('pages') ?
                    # Let's see keys
                    if isinstance(data, dict):
                         print(f"Keys: {list(data.keys())}")
                         if 'result' in data: print("Found result key")
                         if 'pages' in data: 
                             print("Found pages key. Length:", len(data['pages']))
                         else:
                             print("Content (partial):", str(data)[:200])
                    elif isinstance(data, list):
                        print(f"Is List of length {len(data)}")
                        print("First item:", data[0])
                except Exception as e:
                    print(f"JSON Error: {e}")
            else:
                print("Failed.")

if __name__ == "__main__":
    asyncio.run(test())
