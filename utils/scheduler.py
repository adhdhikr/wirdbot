import logging

from utils.prayertimes import get_prayer_times  # noqa: F401 - re-exported

logger = logging.getLogger(__name__)


async def handle_schedule_time(interaction, time_value: str):
    from database import db
    try:
        hours, minutes = map(int, time_value.split(":"))
        
        if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
            await interaction.response.send_message("Invalid time format!", ephemeral=True)
            return
        
        await db.add_scheduled_time(interaction.guild_id, "custom", time_value)
        await interaction.response.send_message(f"✅ Added scheduled time: {time_value} UTC", ephemeral=True)
    except ValueError:
        await interaction.response.send_message("Invalid time format! Use HH:MM (e.g., 14:30)", ephemeral=True)
