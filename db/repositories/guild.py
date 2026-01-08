from typing import Optional, Dict, Any
from db.connection import DatabaseConnection


class GuildRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    async def get(self, guild_id: int) -> Optional[Dict[str, Any]]:
        return await self.db.execute_one(
            "SELECT * FROM guilds WHERE guild_id = ?", (guild_id,)
        )

    async def create(self, guild_id: int, **kwargs):
        columns = ["guild_id"] + list(kwargs.keys())
        placeholders = ", ".join(["?" for _ in columns])
        values = [guild_id] + list(kwargs.values())
        
        await self.db.execute_write(
            f"INSERT INTO guilds ({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values)
        )

    async def update(self, guild_id: int, **kwargs):
        if not kwargs:
            return
        
        set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
        values = list(kwargs.values()) + [guild_id]
        
        await self.db.execute_write(
            f"UPDATE guilds SET {set_clause} WHERE guild_id = ?", 
            tuple(values)
        )

    async def create_or_update(self, guild_id: int, **kwargs):
        existing = await self.get(guild_id)
        if existing:
            await self.update(guild_id, **kwargs)
        else:
            await self.create(guild_id, **kwargs)

    async def get_all_configured(self):
        return await self.db.execute_many(
            "SELECT * FROM guilds WHERE configured = 1"
        )

    async def delete(self, guild_id: int):
        await self.db.execute_write(
            "DELETE FROM guilds WHERE guild_id = ?",
            (guild_id,)
        )
