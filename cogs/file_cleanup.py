"""
File Cleanup Cog
Background task that automatically cleans up stale files from user spaces.
"""
import logging

from nextcord.ext import commands, tasks

from database import db

logger = logging.getLogger(__name__)


class FileCleanupCog(commands.Cog):
    """Cog for periodic file cleanup tasks."""
    
    def __init__(self, bot):
        self.bot = bot
        self.cleanup_task.start()
    
    def cog_unload(self):
        self.cleanup_task.cancel()
    
    @tasks.loop(hours=24)
    async def cleanup_task(self):
        """Run cleanup once per day."""
        try:
            logger.info("Starting scheduled file cleanup...")
            preview = await db.file_storage.get_cleanup_preview()
            
            if preview['file_count'] == 0:
                logger.info("No stale files to clean up.")
                return
            
            logger.info(f"Found {preview['file_count']} stale files ({preview['total_formatted']}) from {preview['users_affected']} inactive users")
            result = await db.file_storage.cleanup_stale_files()
            
            logger.info(f"Cleanup complete: Deleted {result['deleted_count']} files, freed {result['freed_formatted']}")
            
            if result['errors']:
                logger.warning(f"Cleanup had {len(result['errors'])} errors: {result['errors'][:5]}")
                
        except Exception as e:
            logger.error(f"File cleanup task failed: {e}")
    
    @cleanup_task.before_loop
    async def before_cleanup_task(self):
        """Wait until bot is ready before starting cleanup."""
        await self.bot.wait_until_ready()
        import asyncio
        await asyncio.sleep(60)
    
    @commands.command(name="cleanup_preview", hidden=True)
    @commands.is_owner()
    async def cleanup_preview_cmd(self, ctx):
        """Preview what would be cleaned up (Owner only)."""
        preview = await db.file_storage.get_cleanup_preview()
        
        if preview['file_count'] == 0:
            await ctx.send("✅ No stale files to clean up!")
            return
        
        msg = "🗑️ **Cleanup Preview**\n"
        msg += f"Files: {preview['file_count']}\n"
        msg += f"Size: {preview['total_formatted']}\n"
        msg += f"Users affected: {preview['users_affected']}\n\n"
        
        if preview['files']:
            msg += "**Sample files:**\n"
            for f in preview['files'][:10]:
                msg += f"• `{f['filename']}` (user {f['user_id']}, last access: {f['last_accessed']})\n"
        
        await ctx.send(msg)
    
    @commands.command(name="cleanup_run", hidden=True)
    @commands.is_owner()
    async def cleanup_run_cmd(self, ctx):
        """Run cleanup now (Owner only)."""
        await ctx.send("🔄 Running cleanup...")
        
        result = await db.file_storage.cleanup_stale_files()
        
        msg = "✅ **Cleanup Complete**\n"
        msg += f"Deleted: {result['deleted_count']} files\n"
        msg += f"Freed: {result['freed_formatted']}"
        
        if result['errors']:
            msg += f"\n⚠️ Errors: {len(result['errors'])}"
        
        await ctx.send(msg)


def setup(bot):
    bot.add_cog(FileCleanupCog(bot))
