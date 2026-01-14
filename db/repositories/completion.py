from typing import List, Dict
from db.connection import DatabaseConnection


class CompletionRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    async def mark_complete(self, user_id: int, guild_id: int, page_number: int, date: str, session_id: int = None, is_late: bool = False):
        await self.db.execute_write(
            "INSERT INTO completions (user_id, guild_id, page_number, completion_date, session_id, is_late) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, guild_id, page_number, date, session_id, is_late)
        )

    async def get_user_completions_for_date(self, user_id: int, guild_id: int, date: str) -> List[int]:
        rows = await self.db.execute_many(
            "SELECT page_number FROM completions WHERE user_id = ? AND guild_id = ? AND completion_date = ?",
            (user_id, guild_id, date)
        )
        return [row['page_number'] for row in rows]

    async def get_user_completions_for_session(self, user_id: int, session_id: int) -> List[int]:
        """Get all pages completed by a user for a specific session."""
        rows = await self.db.execute_many(
            "SELECT page_number FROM completions WHERE user_id = ? AND session_id = ?",
            (user_id, session_id)
        )
        return [row['page_number'] for row in rows]

    async def get_all_completions_for_date(self, guild_id: int, date: str) -> Dict[int, List[int]]:
        rows = await self.db.execute_many(
            "SELECT user_id, page_number, is_late FROM completions WHERE guild_id = ? AND completion_date = ?",
            (guild_id, date)
        )
        
        completions = {}
        for row in rows:
            user_id = row['user_id']
            if user_id not in completions:
                completions[user_id] = []
            completions[user_id].append(row['page_number'])
        return completions

    async def get_late_completions_for_date(self, guild_id: int, date: str) -> List[int]:
        """Get list of user IDs who completed pages late on this date."""
        rows = await self.db.execute_many(
            "SELECT DISTINCT user_id FROM completions WHERE guild_id = ? AND completion_date = ? AND is_late = 1",
            (guild_id, date)
        )
        return [row['user_id'] for row in rows]
    
    async def get_late_completions_for_session(self, session_id: int) -> List[int]:
        """Get list of user IDs who completed pages late for a specific session."""
        rows = await self.db.execute_many(
            "SELECT DISTINCT user_id FROM completions WHERE session_id = ? AND is_late = 1",
            (session_id,)
        )
        return [row['user_id'] for row in rows]


    async def has_user_completed_session(self, user_id: int, session_id: int) -> bool:
        """Check if a user has completed all pages for a session."""
        # This will be used in conjunction with session page count
        completions = await self.get_user_completions_for_session(user_id, session_id)
        return len(completions) > 0  # Actual completion check happens in completion.py

    async def clear_all(self, guild_id: int):
        await self.db.execute_write(
            "DELETE FROM completions WHERE guild_id = ?",
            (guild_id,)
        )
