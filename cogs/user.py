import discord
from discord.ext import commands
from database import Database
from utils.user_management import assign_role, remove_role


class UserCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="register", description="Register for daily Wird tracking")
    async def register(self, ctx: discord.ApplicationContext):
        db = Database()
        await db.connect()
        
        try:
            user = await db.get_user(ctx.author.id, ctx.guild_id)
            
            if user and user['registered']:
                await ctx.respond("You're already registered!", ephemeral=True)
                return
            
            await db.register_user(ctx.author.id, ctx.guild_id)
            await assign_role(ctx.author, ctx.guild_id)
            
            await ctx.respond("✅ You've been registered for daily Wird tracking!", ephemeral=True)
        finally:
            await db.close()

    @discord.slash_command(name="unregister", description="Unregister from daily Wird tracking")
    async def unregister(self, ctx: discord.ApplicationContext):
        db = Database()
        await db.connect()
        
        try:
            user = await db.get_user(ctx.author.id, ctx.guild_id)
            
            if not user or not user['registered']:
                await ctx.respond("You're not registered!", ephemeral=True)
                return
            
            await db.unregister_user(ctx.author.id, ctx.guild_id)
            await remove_role(ctx.author, ctx.guild_id)
            
            await ctx.respond("✅ You've been unregistered from Wird tracking", ephemeral=True)
        finally:
            await db.close()

    @discord.slash_command(name="stats", description="View your Wird statistics")
    async def stats(self, ctx: discord.ApplicationContext):
        db = Database()
        await db.connect()
        
        try:
            user = await db.get_user(ctx.author.id, ctx.guild_id)
            
            if not user or not user['registered']:
                await ctx.respond("You're not registered! Use `/register` first.", ephemeral=True)
                return
            
            from datetime import datetime
            today = datetime.utcnow().strftime("%Y-%m-%d")
            completions = await db.get_user_completions_for_date(ctx.author.id, ctx.guild_id, today)
            
            embed = discord.Embed(title=f"📊 {ctx.author.display_name}'s Wird Stats", color=discord.Color.green())
            embed.add_field(name="🔥 Current Streak", value=f"{user['current_streak']} days", inline=True)
            embed.add_field(name="🏆 Longest Streak", value=f"{user['longest_streak']} days", inline=True)
            embed.add_field(name="📖 Today's Progress", value=f"{len(completions)} pages", inline=True)
            
            if user['last_completion_date']:
                embed.add_field(name="📅 Last Completion", value=user['last_completion_date'], inline=False)
            
            await ctx.respond(embed=embed, ephemeral=True)
        finally:
            await db.close()


def setup(bot):
    bot.add_cog(UserCog(bot))
