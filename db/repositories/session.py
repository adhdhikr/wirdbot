from typing import Any, Dict, List, Optional

from db.connection import DatabaseConnection


class SessionRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    async def update_message_ids(self, guild_id: int, session_date: str, message_ids: str):
        await self.db.execute_write(
            """UPDATE daily_sessions SET message_ids = ? WHERE guild_id = ? AND session_date = ?""",
            (message_ids, guild_id, session_date)
        )
    
    async def update_summary_message_id(self, session_id: int, message_id: int):
        """Update the summary message ID for a session."""
        await self.db.execute_write(
            """UPDATE daily_sessions SET summary_message_id = ? WHERE id = ?""",
            (message_id, session_id)
        )

    async def get_session_by_summary_message_id(self, guild_id: int, message_id: int) -> Optional[Dict[str, Any]]:
        """Get session by its summary message ID."""
        return await self.db.execute_one(
            """SELECT * FROM daily_sessions WHERE guild_id = ? AND summary_message_id = ?""",
            (guild_id, message_id)
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

    async def get_current_active_session(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get the most recent session for this guild (the current active one)."""
        return await self.db.execute_one(
            """SELECT * FROM daily_sessions 
               WHERE guild_id = ?
               ORDER BY created_at DESC LIMIT 1""",
            (guild_id,)
        )
    
    async def get_session_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific session by its ID."""
        return await self.db.execute_one(
            """SELECT * FROM daily_sessions WHERE id = ?""",
            (session_id,)
        )

    async def get_previous_session(self, guild_id: int, current_session_id: int) -> Optional[Dict[str, Any]]:
        """Get the session immediately preceding the current one."""
        current = await self.get_session_by_id(current_session_id)
        if not current:
            return None
            
        return await self.db.execute_one(
            """SELECT * FROM daily_sessions 
               WHERE guild_id = ? AND created_at < ?
               ORDER BY created_at DESC LIMIT 1""",
            (guild_id, current['created_at'])
        )


    async def get_session_for_page(self, guild_id: int, page_number: int) -> Optional[Dict[str, Any]]:
        """Find which session a specific page belongs to."""
        return await self.db.execute_one(
            """SELECT * FROM daily_sessions 
               WHERE guild_id = ? 
               AND start_page <= ? 
               AND end_page >= ?
               ORDER BY created_at DESC LIMIT 1""",
            (guild_id, page_number, page_number)
        )

    async def mark_session_completed(self, session_id: int):
        """Mark a session as completed."""
        await self.db.execute_write(
            """UPDATE daily_sessions 
               SET is_completed = 1, completed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (session_id,)
        )

    async def get_completed_sessions_for_guild(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all completed sessions for a guild, ordered by creation date."""
        return await self.db.execute_many(
            """SELECT * FROM daily_sessions 
               WHERE guild_id = ? AND is_completed = 1
               ORDER BY created_at ASC""",
            (guild_id,)
        )

    async def get_all_sessions_for_guild(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all sessions for a guild, ordered by creation date."""
        return await self.db.execute_many(
            """SELECT * FROM daily_sessions 
               WHERE guild_id = ?
               ORDER BY created_at ASC""",
            (guild_id,)
        )

    async def clear_all(self, guild_id: int):
        await self.db.execute_write(
            "DELETE FROM daily_sessions WHERE guild_id = ?",
            (guild_id,)
        )
