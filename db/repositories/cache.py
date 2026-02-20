import json
from typing import Any, Dict, List, Optional

from db.connection import DatabaseConnection


class CacheRepository:
    def __init__(self, db: DatabaseConnection):
        self.db = db
    async def get_translation_cache(self, page_number: int, language: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached translation data for a page and language."""
        result = await self.db.execute_one(
            """SELECT data FROM translation_cache 
               WHERE page_number = ? AND language = ?""",
            (page_number, language)
        )
        if result:
            return json.loads(result['data'])
        return None

    async def set_translation_cache(self, page_number: int, language: str, data: List[Dict[str, Any]]):
        """Cache translation data for a page and language."""
        json_data = json.dumps(data)
        await self.db.execute_write(
            """INSERT OR REPLACE INTO translation_cache (page_number, language, data)
               VALUES (?, ?, ?)""",
            (page_number, language, json_data)
        )
    async def get_tafsir_cache(self, page_number: int, edition: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached tafsir data for a page and edition."""
        result = await self.db.execute_one(
            """SELECT data FROM tafsir_cache 
               WHERE page_number = ? AND edition = ?""",
            (page_number, edition)
        )
        if result:
            return json.loads(result['data'])
        return None

    async def set_tafsir_cache(self, page_number: int, edition: str, data: List[Dict[str, Any]]):
        """Cache tafsir data for a page and edition."""
        json_data = json.dumps(data)
        await self.db.execute_write(
            """INSERT OR REPLACE INTO tafsir_cache (page_number, edition, data)
               VALUES (?, ?, ?)""",
            (page_number, edition, json_data)
        )
    async def clear_translation_cache(self):
        """Clear all translation cache."""
        await self.db.execute_write("DELETE FROM translation_cache")

    async def clear_tafsir_cache(self):
        """Clear all tafsir cache."""
        await self.db.execute_write("DELETE FROM tafsir_cache")

    async def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about cache usage."""
        translation_count = await self.db.execute_one(
            "SELECT COUNT(*) as count FROM translation_cache"
        )
        tafsir_count = await self.db.execute_one(
            "SELECT COUNT(*) as count FROM tafsir_cache"
        )
        
        return {
            'translations': translation_count['count'] if translation_count else 0,
            'tafsir': tafsir_count['count'] if tafsir_count else 0
        }
