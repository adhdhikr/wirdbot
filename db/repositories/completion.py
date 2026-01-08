from typing import List, Dict
from db.connection import DatabaseConnection


class CompletionRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db

    async def mark_complete(self, user_id: int, guild_id: int, page_number: int, date: str):
        await self.db.execute_write(
            "INSERT INTO completions (user_id, guild_id, page_number, completion_date) VALUES (?, ?, ?, ?)",
            (user_id, guild_id, page_number, date)
        )

    async def get_user_completions_for_date(self, user_id: int, guild_id: int, date: str) -> List[int]:
        rows = await self.db.execute_many(
            "SELECT page_number FROM completions WHERE user_id = ? AND guild_id = ? AND completion_date = ?",
            (user_id, guild_id, date)
        )
        return [row['page_number'] for row in rows]

    async def get_all_completions_for_date(self, guild_id: int, date: str) -> Dict[int, List[int]]:
        rows = await self.db.execute_many(
            "SELECT user_id, page_number FROM completions WHERE guild_id = ? AND completion_date = ?",
            (guild_id, date)
        )
        
        completions = {}
        for row in rows:
            user_id = row['user_id']
            if user_id not in completions:
                completions[user_id] = []
            completions[user_id].append(row['page_number'])
        return completions
