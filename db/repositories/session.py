from typing import Optional, Dict, Any
from db.connection import DatabaseConnection


class SessionRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    async def update_message_ids(self, guild_id: int, session_date: str, message_ids: str):
        await self.db.execute_write(
            """UPDATE daily_sessions SET message_ids = ? WHERE guild_id = ? AND session_date = ?""",
            (message_ids, guild_id, session_date)
        )

    async def create(self, guild_id: int, session_date: str, start_page: int, end_page: int, message_ids: str):
        await self.db.execute_write(
            """INSERT INTO daily_sessions (guild_id, session_date, start_page, end_page, message_ids)
               VALUES (?, ?, ?, ?, ?)""",
            (guild_id, session_date, start_page, end_page, message_ids)
        )

    async def get_today(self, guild_id: int, session_date: str) -> Optional[Dict[str, Any]]:
        return await self.db.execute_one(
            """SELECT * FROM daily_sessions 
               WHERE guild_id = ? AND session_date = ?
               ORDER BY created_at DESC LIMIT 1""",
            (guild_id, session_date)
        )

    async def clear_all(self, guild_id: int):
        await self.db.execute_write(
            "DELETE FROM daily_sessions WHERE guild_id = ?",
            (guild_id,)
        )
