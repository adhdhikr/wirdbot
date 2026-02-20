from typing import Any, Dict, List, Optional

from db.connection import DatabaseConnection


class ScheduleRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    async def add(self, guild_id: int, time_type: str, time_value: Optional[str] = None):
        await self.db.execute_write(
            "INSERT INTO scheduled_times (guild_id, time_type, time_value) VALUES (?, ?, ?)",
            (guild_id, time_type, time_value)
        )

    async def get_all(self, guild_id: int) -> List[Dict[str, Any]]:
        return await self.db.execute_many(
            "SELECT * FROM scheduled_times WHERE guild_id = ? AND enabled = 1",
            (guild_id,)
        )

    async def remove(self, time_id: int):
        await self.db.execute_write(
            "DELETE FROM scheduled_times WHERE id = ?", 
            (time_id,)
        )

    async def clear_all(self, guild_id: int):
        await self.db.execute_write(
            "DELETE FROM scheduled_times WHERE guild_id = ?", 
            (guild_id,)
        )
