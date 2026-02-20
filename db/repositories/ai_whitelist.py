import logging
from database import db

logger = logging.getLogger(__name__)


async def load_whitelist() -> set[int]:
    """Load all whitelisted guild IDs from the database."""
    rows = await db.execute_many("SELECT guild_id FROM ai_code_whitelist", ())
    return {row['guild_id'] for row in rows}


async def add_to_whitelist(guild_id: int) -> None:
    """Add a guild to the persistent whitelist."""
    await db.execute_write(
        "INSERT OR IGNORE INTO ai_code_whitelist (guild_id) VALUES (?)",
        (guild_id,)
    )
    logger.info(f"AI whitelist: added guild {guild_id}")


async def remove_from_whitelist(guild_id: int) -> None:
    """Remove a guild from the persistent whitelist."""
    await db.execute_write(
        "DELETE FROM ai_code_whitelist WHERE guild_id = ?",
        (guild_id,)
    )
    logger.info(f"AI whitelist: removed guild {guild_id}")
