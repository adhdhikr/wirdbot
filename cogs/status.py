import nextcord as discord
from nextcord.ext import commands, tasks
import logging
import random
import asyncio

logger = logging.getLogger(__name__)

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.status_options = [
            "Reading Wird",
            "Learning Quran",
            "Reviewing Tafsir",
            "Memorizing Ayahs",
            "Reflecting on Verses",
            "Helping Users",
            "Reciting Quran"
        ]
        self.current_forced_status = None
        self._reset_task = None
        self.rotate_status.start()

    def cog_unload(self):
        self.rotate_status.cancel()
        if self._reset_task:
            self._reset_task.cancel()

    @tasks.loop(minutes=10)
    async def rotate_status(self):
        if self.current_forced_status:
            return  # Don't rotate if forced

        status_text = random.choice(self.status_options)
        await self.bot.change_presence(activity=discord.Game(name=status_text))
        logger.info(f"Rotated status to: {status_text}")

    @rotate_status.before_loop
    async def before_rotate_status(self):
        await self.bot.wait_until_ready()

    async def force_status(self, text: str, duration_minutes: int):
        """Forces a status for a set duration."""
        self.current_forced_status = text
        await self.bot.change_presence(activity=discord.Game(name=text))
        logger.info(f"Forced status to: {text} for {duration_minutes} minutes")
        
        # Cancel existing reset task if any
        if self._reset_task:
            self._reset_task.cancel()
        
        # Schedule the reset
        self._reset_task = self.bot.loop.create_task(self._reset_status_after(duration_minutes))

    async def _reset_status_after(self, minutes: int):
        try:
            await asyncio.sleep(minutes * 60)
            self.current_forced_status = None
            self._reset_task = None
            logger.info("Forced status expired. Resuming rotation.")
            # Trigger rotation immediately
            if self.rotate_status.is_running():
                # We can't restart the loop easily without stopping it, so we just run the routine once
                new_status = random.choice(self.status_options)
                await self.bot.change_presence(activity=discord.Game(name=new_status))
        except asyncio.CancelledError:
            pass # Task was cancelled, likely by a new force_status call

    def add_status_option(self, text: str):
        if text not in self.status_options:
            self.status_options.append(text)
            return True
        return False

def setup(bot):
    bot.add_cog(Status(bot))
