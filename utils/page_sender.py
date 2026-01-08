import discord
from database import Database
from datetime import datetime
from views import PageView
from config import API_BASE_URL, MAX_PAGES
import asyncio
import logging

logger = logging.getLogger(__name__)


async def send_daily_pages(guild_id: int, bot) -> bool:
    db = Database()
    await db.connect()
    
    try:
        guild_config = await db.get_guild_config(guild_id)
        if not guild_config or not guild_config['configured']:
            return False
        
        guild = bot.get_guild(guild_id)
        if not guild:
            return False
        
        channel = guild.get_channel(guild_config['channel_id'])
        if not channel:
            return False
        
        current_page = guild_config['current_page']
        pages_per_day = guild_config['pages_per_day']
        mushaf_type = guild_config['mushaf_type']
        
        message_ids = []
        today = datetime.utcnow().strftime("%Y-%m-%d")
        
        for i in range(pages_per_day):
            page_num = current_page + i
            if page_num > MAX_PAGES:
                page_num = page_num - MAX_PAGES
            
            image_url = f"{API_BASE_URL}/mushaf/{mushaf_type}/page/{page_num}"
            
            embed = discord.Embed(
                title=f"📖 Quran Page {page_num}",
                description=f"Page {i+1} of {pages_per_day} for today",
                color=discord.Color.green()
            )
            embed.set_image(url=image_url)
            embed.set_footer(text=f"{mushaf_type.title()} • {today}")
            
            try:
                view = PageView(page_num)
                msg = await channel.send(embed=embed, view=view)
                message_ids.append(str(msg.id))
            except Exception as e:
                logger.error(f"Error sending page {page_num}: {e}")
                return False
        
        new_page = current_page + pages_per_day
        if new_page > MAX_PAGES:
            new_page = new_page - MAX_PAGES
        
        await db.create_or_update_guild(guild_id, current_page=new_page)
        await db.create_daily_session(
            guild_id, today, current_page, current_page + pages_per_day - 1, ",".join(message_ids)
        )
        
        if guild_config['followup_after_send']:
            await asyncio.sleep(2)
            from .followup import send_followup_message
            await send_followup_message(guild_id, bot)
        
        return True
    finally:
        await db.close()
