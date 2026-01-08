import discord
from discord.ext import commands, tasks
from database import Database
from datetime import datetime
from utils.scheduler import get_prayer_times
from utils.page_sender import send_daily_pages
import logging

logger = logging.getLogger(__name__)


class SchedulerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.scheduler_loop.start()

    def cog_unload(self):
        self.scheduler_loop.cancel()

    @tasks.loop(minutes=1)
    async def scheduler_loop(self):
        now = datetime.utcnow()
        current_time = now.strftime("%H:%M")
        
        db = Database()
        await db.connect()
        
        try:
            guilds = await db.get_all_configured_guilds()
            
            for guild_config in guilds:
                guild_id = guild_config['guild_id']
                scheduled_times = await db.get_scheduled_times(guild_id)
                
                for st in scheduled_times:
                    should_send = False
                    
                    if st['time_type'] == 'custom':
                        if st['time_value'] == current_time:
                            should_send = True
                    else:
                        if guild_config['mosque_id']:
                            prayer_times = await get_prayer_times(guild_config['mosque_id'])
                            if prayer_times and st['time_type'] in prayer_times:
                                prayer_time_str = prayer_times[st['time_type']]
                                try:
                                    prayer_dt = datetime.fromisoformat(prayer_time_str.replace('Z', '+00:00'))
                                    if prayer_dt.strftime("%H:%M") == current_time:
                                        should_send = True
                                except Exception as e:
                                    logger.error(f"Error parsing prayer time: {e}")
                    
                    if should_send:
                        today = datetime.utcnow().strftime("%Y-%m-%d")
                        existing_session = await db.get_today_session(guild_id, today)
                        
                        if not existing_session:
                            await send_daily_pages(guild_id, self.bot)
                            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
        finally:
            await db.close()

    @scheduler_loop.before_loop
    async def before_scheduler(self):
        await self.bot.wait_until_ready()


def setup(bot):
    bot.add_cog(SchedulerCog(bot))
