from typing import Optional, List, Dict, Any
from db.connection import DatabaseConnection


class UserRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    async def get(self, user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
        return await self.db.execute_one(
            "SELECT * FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )

    async def register(self, user_id: int, guild_id: int):
        await self.db.execute_write(
            "INSERT OR REPLACE INTO users (user_id, guild_id, registered) VALUES (?, ?, 1)",
            (user_id, guild_id)
        )

    async def unregister(self, user_id: int, guild_id: int):
        await self.db.execute_write(
            "UPDATE users SET registered = 0 WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id)
        )

    async def get_all_registered(self, guild_id: int) -> List[Dict[str, Any]]:
        return await self.db.execute_many(
            "SELECT * FROM users WHERE guild_id = ? AND registered = 1",
            (guild_id,)
        )

    async def update_streak(self, user_id: int, guild_id: int, new_streak: int, last_completion: str):
        user = await self.get(user_id, guild_id)
        if not user:
            return
        
        longest = max(user['longest_streak'], new_streak)
        await self.db.execute_write(
            """UPDATE users 
               SET current_streak = ?, longest_streak = ?, last_completion_date = ?
               WHERE user_id = ? AND guild_id = ?""",
            (new_streak, longest, last_completion, user_id, guild_id)
        )

    async def update_session_streak(self, user_id: int, guild_id: int, new_streak: int):
        """Update the session-based streak for a user."""
        user = await self.get(user_id, guild_id)
        if not user:
            return
        
        longest = max(user.get('longest_session_streak', 0), new_streak)
        await self.db.execute_write(
            """UPDATE users 
               SET session_streak = ?, longest_session_streak = ?
               WHERE user_id = ? AND guild_id = ?""",
            (new_streak, longest, user_id, guild_id)
        )

    async def set_session_streak(self, user_id: int, guild_id: int, streak: int):
        """Manually set a user's session streak (admin command)."""
        user = await self.get(user_id, guild_id)
        if not user:
            # Create user if doesn't exist
            await self.register(user_id, guild_id)
        
        # Update longest if new streak is higher
        current_longest = user.get('longest_session_streak', 0) if user else 0
        longest = max(current_longest, streak)
        
        await self.db.execute_write(
            """UPDATE users 
               SET session_streak = ?, longest_session_streak = ?
               WHERE user_id = ? AND guild_id = ?""",
            (streak, longest, user_id, guild_id)
        )

    async def get_user_session_completions(self, user_id: int, guild_id: int) -> Dict[int, bool]:
        """Get dict of {session_id: is_late} for fully completed sessions."""
        rows = await self.db.execute_many(
            """SELECT c.session_id, MAX(c.is_late) as is_late
               FROM completions c
               JOIN daily_sessions ds ON c.session_id = ds.id
               WHERE c.user_id = ? AND c.guild_id = ?
               GROUP BY c.session_id
               HAVING COUNT(DISTINCT c.page_number) = (ds.end_page - ds.start_page + 1)""",
            (user_id, guild_id)
        )
        return {row['session_id']: bool(row['is_late']) for row in rows}


    async def clear_all(self, guild_id: int):
        await self.db.execute_write(
            "DELETE FROM users WHERE guild_id = ?",
            (guild_id,)
        )

    async def get_language_preference(self, user_id: int, guild_id: int) -> str:
        user = await self.get(user_id, guild_id)
        return user.get('language_preference', 'eng') if user else 'eng'

    async def set_language_preference(self, user_id: int, guild_id: int, language: str):
        await self.db.execute_write(
            "UPDATE users SET language_preference = ? WHERE user_id = ? AND guild_id = ?",
            (language, user_id, guild_id)
        )

    async def get_tafsir_preference(self, user_id: int, guild_id: int) -> str:
        user = await self.get(user_id, guild_id)
        return user.get('tafsir_preference', 'ar-tafsir-ibn-kathir') if user else 'ar-tafsir-ibn-kathir'

    async def set_tafsir_preference(self, user_id: int, guild_id: int, tafsir: str):
        await self.db.execute_write(
            "UPDATE users SET tafsir_preference = ? WHERE user_id = ? AND guild_id = ?",
            (tafsir, user_id, guild_id)
        )
