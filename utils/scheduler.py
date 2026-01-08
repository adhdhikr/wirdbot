import aiohttp
from datetime import datetime
from typing import Optional
import logging

from config import PRAYER_API_BASE_URL

logger = logging.getLogger(__name__)


async def get_prayer_times(mosque_id: str) -> Optional[dict]:
    now = datetime.utcnow()
    url = f"{PRAYER_API_BASE_URL}/{mosque_id}/{now.day}/{now.month}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.json()
    except Exception as e:
        logger.error(f"Error fetching prayer times: {e}")
    
    return None


async def handle_schedule_time(interaction, time_value: str):
    from database import db
    # ...existing code...
    
    try:
        hours, minutes = map(int, time_value.split(":"))
        
        if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
            await interaction.response.send_message("Invalid time format!", ephemeral=True)
            return
        
        await db.add_scheduled_time(interaction.guild_id, "custom", time_value)
        await interaction.response.send_message(f"✅ Added scheduled time: {time_value} UTC", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("Invalid time format! Use HH:MM (e.g., 14:30)", ephemeral=True)
    finally:
        # ...existing code...
