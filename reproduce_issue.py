
import asyncio
import aiosqlite
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reproduce():
    db = await aiosqlite.connect(":memory:")
    await db.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
    await db.close()
    
    try:
        await db.execute("SELECT * FROM test")
    except Exception as e:
        logger.error(f"Error caught: {e}")

if __name__ == "__main__":
    asyncio.run(reproduce())
