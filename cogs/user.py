import discord
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
        try:
            user = await db.get_user(ctx.author.id, ctx.guild_id)
            if user and user['registered']:
                await ctx.respond("You're already registered!", ephemeral=True)
                return
        finally:
            await db.close()

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
        from main import db
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
            if user['current_streak'] > 1:
                embed.add_field(name="🔥 Current Streak", value=f"{user['current_streak']} days", inline=True)
            if user['longest_streak'] > 1:
                embed.add_field(name="🏆 Longest Streak", value=f"{user['longest_streak']} days", inline=True)
            embed.add_field(name="📖 Today's Progress", value=f"{len(completions)} pages", inline=True)
            if user['last_completion_date']:
                embed.add_field(name="📅 Last Completion", value=user['last_completion_date'], inline=False)
            await ctx.respond(embed=embed, ephemeral=True)
        finally:
            await db.close()


def setup(bot):
    bot.add_cog(UserCog(bot))
