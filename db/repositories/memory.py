from datetime import datetime
from ..connection import DatabaseConnection

class MemoryRepository:
    def __init__(self, connection: DatabaseConnection):
        self.connection = connection
        # Table created via migration 010

    async def add_memory(self, user_id: int, guild_id: int, content: str):
        query = """
        INSERT INTO user_memories (user_id, guild_id, content)
        VALUES (?, ?, ?)
        """
        # execute_write returns None, but we want the ID...
        # DatabaseConnection doesn't expose a way to get last row ID easily with execute_write because it commits.
        # But for UI purposes, we just need to confirm it worked.
        
        await self.connection.execute_write(query, (user_id, guild_id, content))
        
        # Fetch the ID separately (race condition possible but low risk for user memory)
        # OR just query for the latest for this user
        row = await self.connection.execute_one(
            "SELECT id FROM user_memories WHERE user_id = ? AND guild_id = ? ORDER BY id DESC LIMIT 1",
            (user_id, guild_id)
        )
        return row

    async def get_memories(self, user_id: int, guild_id: int, limit: int = 10):
        query = """
        SELECT id, content, created_at 
        FROM user_memories 
        WHERE user_id = ? AND guild_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """
        rows = await self.connection.execute_many(query, (user_id, guild_id, limit))
        return rows

    async def search_memories(self, user_id: int, guild_id: int, search_term: str, limit: int = 5):
        query = """
        SELECT id, content, created_at
        FROM user_memories
        WHERE user_id = ? AND guild_id = ? AND content LIKE ?
        ORDER BY created_at DESC
        LIMIT ?
        """
        # execute_many expects tuple for params
        return await self.connection.execute_many(query, (user_id, guild_id, f"%{search_term}%", limit))

    async def delete_memory(self, memory_id: int, user_id: int):
        query = """
        DELETE FROM user_memories WHERE id = ? AND user_id = ?
        """
        await self.connection.execute_write(query, (memory_id, user_id))
