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
