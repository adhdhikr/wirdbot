import discord
import re
from discord import option
from discord.ext import commands
from main import db
from utils.user_management import assign_role, remove_role


class UserCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="help", description="Show all available commands")
    async def help(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(
            title="📖 Wird Bot Commands",
            description="Here are all available commands:",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="👥 User Commands",
            value=(
                "`/register` - Register for daily Wird tracking\n"
                "`/unregister` - Unregister from tracking\n"
                "`/stats` - View your statistics and streaks\n"
                "`/help` - Show this help message"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⚙️ Admin Commands (Requires Administrator)",
            value=(
                "`/setup` - Configure the bot (channel picker, mushaf dropdown)\n"
                "`/config` - View current server configuration\n"
                "`/schedule` - Add/list/clear scheduled times\n"
                "`/set_mushaf` - Change mushaf type\n"
                "`/set_pages` - Change pages per day\n"
                "`/set_channel` - Change wird channel\n"
                "`/set_mosque` - Change mosque ID\n"
                "`/set_followup_channel` - Set follow-up channel\n"
                "`/toggle_followup_on_completion` - Toggle instant follow-up\n"
                "`/set_role` - Set the Wird role\n"
                "`/send_now` - Manually send today's pages"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📌 Note",
            value="Admin commands only appear if you have Administrator permission in this server.",
            inline=False
        )
        
        embed.set_footer(text="Use /setup to get started! (Admin only)")
        
        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name="register", description="Register for daily Wird tracking")
    async def register(self, ctx: discord.ApplicationContext):
        # use shared db instance
        user = await db.get_user(ctx.author.id, ctx.guild_id)
        if user and user['registered']:
            await ctx.respond("You're already registered!", ephemeral=True)
            return

        # Use unified registration and role logic
        from utils.user_management import register_user_and_assign_role
        await register_user_and_assign_role(
            ctx.author,
            ctx.guild_id,
            respond_func=lambda msg: ctx.respond(msg, ephemeral=True)
        )
        # Update the followup/progress message after registration
        from utils.followup import send_followup_message
        await send_followup_message(ctx.guild_id, self.bot)

    @discord.slash_command(name="unregister", description="Unregister from daily Wird tracking")
    async def unregister(self, ctx: discord.ApplicationContext):
        from main import db
        user = await db.get_user(ctx.author.id, ctx.guild_id)
        if not user or not user['registered']:
            await ctx.respond("You're not registered!", ephemeral=True)
            return
        await db.unregister_user(ctx.author.id, ctx.guild_id)
        await remove_role(ctx.author, ctx.guild_id)
        await ctx.respond("✅ You've been unregistered from Wird tracking", ephemeral=True)

    @discord.slash_command(name="stats", description="View your Wird statistics")
    async def stats(self, ctx: discord.ApplicationContext):
        from main import db
        user = await db.get_user(ctx.author.id, ctx.guild_id)
        if not user or not user['registered']:
            await ctx.respond("You're not registered! Use `/register` first.", ephemeral=True)
            return
        from datetime import datetime
        
        # Get current active session
        active_session = await db.get_current_active_session(ctx.guild_id)
        if active_session:
            completions = await db.get_user_completions_for_session(ctx.author.id, active_session['id'])
            total_pages = active_session['end_page'] - active_session['start_page'] + 1
        else:
            completions = []
            total_pages = 0
        
        embed = discord.Embed(title=f"📊 {ctx.author.display_name}'s Wird Stats", color=discord.Color.green())
        
        # Show session-based streaks
        if user.get('session_streak', 0) > 1:
            streak_emoji = user.get('streak_emoji') or "🔥"
            embed.add_field(name=f"{streak_emoji} Current Streak", value=f"{user['session_streak']} sessions", inline=True)
        if user.get('longest_session_streak', 0) > 1:
            embed.add_field(name="🏆 Longest Streak", value=f"{user['longest_session_streak']} sessions", inline=True)
        
        # Show current session progress
        if active_session:
            embed.add_field(name="📖 Current Session Progress", value=f"{len(completions)}/{total_pages} pages", inline=True)
        
        if user['last_completion_date']:
            embed.add_field(name="📅 Last Completion", value=user['last_completion_date'], inline=False)
        
        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name="emoji", description="Set your personal streak emoji")
    @option("emoji", description="The emoji you want to use (e.g. 🔥)", required=True)
    async def emoji(self, ctx: discord.ApplicationContext, emoji: str):
        # Check if user is registered
        user = await db.get_user(ctx.author.id, ctx.guild_id)
        if not user or not user['registered']:
            await ctx.respond("You're not registered! Use `/register` first.", ephemeral=True)
            return

        # Validation logic
        # Custom Discord Emoji: <a:name:id> or <:name:id>
        # Or standard emoji (strict length 1 check as per user request "shouldnt be more than one char")
        custom_emoji_pattern = r"^<a?:[a-zA-Z0-9_]+:[0-9]+>$"
        is_custom = bool(re.match(custom_emoji_pattern, emoji))
        is_standard = len(emoji) == 1
        
        if not (is_custom or is_standard):
            await ctx.respond("❌ Invalid emoji! usage: `/emoji 🔥`\nMust be a single emoji or a valid custom Discord emoji.", ephemeral=True)
            return

        await db.set_user_streak_emoji(ctx.author.id, ctx.guild_id, emoji)
        await ctx.respond(f"✅ Your streak emoji has been set to {emoji}", ephemeral=True)



def setup(bot):
    bot.add_cog(UserCog(bot))
