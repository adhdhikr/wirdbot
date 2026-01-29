import logging
from typing import Any, List, Optional, Dict

logger = logging.getLogger(__name__)

class ScopedDatabase:
    """
    A wrapper around the database connection that logs access
    and encourages guild-scoped queries.
    
    This does not strictly enforce SQL parsing (which is complex and error-prone),
    but provides a layer of auditory safety and context injection.
    """
    def __init__(self, db, guild_id: int):
        self._db = db
        self.guild_id = guild_id

    async def execute_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        self._log_query(query, params)
        # Optional: Add strict check for guild_id usage?
        # For now, we trust the agent/user but log it heavily.
        return await self._db.execute_one(query, params)

    async def execute_many(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        self._log_query(query, params)
        return await self._db.execute_many(query, params)

    async def execute_write(self, query: str, params: tuple = ()):
        self._log_query(query, params)
        return await self._db.execute_write(query, params)
        
    async def execute(self, query: str, params: tuple = ()):
        # Passthrough for raw cursor access if needed, but not encouraged
        self._log_query(query, params)
        return await self._db.execute(query, params)

    def _log_query(self, query: str, params: tuple):
        logger.info(f"[ScopedDB: {self.guild_id}] Query: {query} | Params: {params}")
        
    def __getattr__(self, name):
        # Allow access to other methods if necessary, but warn
        logger.warning(f"[ScopedDB: {self.guild_id}] Accessing direct DB method: {name}")
        return getattr(self._db, name)
