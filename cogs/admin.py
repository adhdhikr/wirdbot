import discord
from discord.ext import commands
from discord import option
from typing import Optional
from views import SetupModal, ScheduleTimeModal
from database import Database
from utils.user_management import assign_role, remove_role


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="setup", description="Configure the Wird bot (Admin only)")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx: discord.ApplicationContext):
        modal = SetupModal()
        await ctx.send_modal(modal)

    @discord.slash_command(name="config", description="View current server configuration")
    async def config(self, ctx: discord.ApplicationContext):
        db = Database()
        await db.connect()
        
        try:
            guild_config = await db.get_guild_config(ctx.guild_id)
            
            if not guild_config or not guild_config['configured']:
                await ctx.respond("Server not configured! Use `/setup` to configure.", ephemeral=True)
                return
            
            scheduled_times = await db.get_scheduled_times(ctx.guild_id)
            
            times_str = ""
            for st in scheduled_times:
                if st['time_type'] == 'custom':
                    times_str += f"• Custom: {st['time_value']} UTC\n"
                else:
                    times_str += f"• Prayer: {st['time_type'].title()}\n"
            
            if not times_str:
                times_str = "No scheduled times set"
            
            embed = discord.Embed(title="⚙️ Server Configuration", color=discord.Color.blue())
            embed.add_field(name="Mosque ID", value=guild_config['mosque_id'] or "Not set", inline=True)
            embed.add_field(name="Mushaf Type", value=guild_config['mushaf_type'], inline=True)
            embed.add_field(name="Pages/Day", value=guild_config['pages_per_day'], inline=True)
            embed.add_field(name="Channel", value=f"<#{guild_config['channel_id']}>", inline=True)
            embed.add_field(name="Current Page", value=guild_config['current_page'], inline=True)
            embed.add_field(name="Wird Role", value=f"<@&{guild_config['wird_role_id']}>" if guild_config['wird_role_id'] else "Not set", inline=True)
            embed.add_field(name="Scheduled Times", value=times_str, inline=False)
            embed.add_field(name="Follow-up Channel", value=f"<#{guild_config['followup_channel_id']}>" if guild_config['followup_channel_id'] else "Same as main channel", inline=True)
            embed.add_field(name="Follow-up on Completion", value="✅" if guild_config['followup_on_completion'] else "❌", inline=True)
            
            await ctx.respond(embed=embed, ephemeral=True)
        finally:
            await db.close()

    @discord.slash_command(name="schedule", description="Manage scheduled times (Admin only)")
    @commands.has_permissions(administrator=True)
    @option("action", choices=["add_time", "add_prayer", "list", "clear"])
    @option("prayer", choices=["fajr", "dhuhr", "asr", "maghrib", "isha"], required=False)
    async def schedule(self, ctx: discord.ApplicationContext, action: str, prayer: Optional[str] = None):
        db = Database()
        await db.connect()
        
        try:
            guild_config = await db.get_guild_config(ctx.guild_id)
            if not guild_config or not guild_config['configured']:
                await ctx.respond("Please run `/setup` first!", ephemeral=True)
                return
            
            if action == "add_time":
                modal = ScheduleTimeModal()
                await ctx.send_modal(modal)
            
            elif action == "add_prayer":
                if not prayer:
                    await ctx.respond("Please specify a prayer time!", ephemeral=True)
                    return
                
                await db.add_scheduled_time(ctx.guild_id, prayer)
                await ctx.respond(f"✅ Added {prayer.title()} prayer time to schedule", ephemeral=True)
            
            elif action == "list":
                scheduled_times = await db.get_scheduled_times(ctx.guild_id)
                if not scheduled_times:
                    await ctx.respond("No scheduled times set!", ephemeral=True)
                    return
                
                times_list = []
                for st in scheduled_times:
                    if st['time_type'] == 'custom':
                        times_list.append(f"ID {st['id']}: Custom time {st['time_value']} UTC")
                    else:
                        times_list.append(f"ID {st['id']}: {st['time_type'].title()} prayer")
                
                await ctx.respond("**Scheduled Times:**\n" + "\n".join(times_list), ephemeral=True)
            
            elif action == "clear":
                await db.clear_scheduled_times(ctx.guild_id)
                await ctx.respond("✅ Cleared all scheduled times", ephemeral=True)
        finally:
            await db.close()

    @discord.slash_command(name="update", description="Update specific configuration (Admin only)")
    @commands.has_permissions(administrator=True)
    @option("setting", choices=["mushaf", "pages_per_day", "channel", "mosque_id", "followup_channel", "followup_on_completion"])
    @option("value", description="New value for the setting")
    async def update(self, ctx: discord.ApplicationContext, setting: str, value: str):
        db = Database()
        await db.connect()
        
        try:
            guild_config = await db.get_guild_config(ctx.guild_id)
            if not guild_config:
                await ctx.respond("Please run `/setup` first!", ephemeral=True)
                return
            
            if setting == "pages_per_day":
                from config import MIN_PAGES_PER_DAY, MAX_PAGES_PER_DAY
                value = int(value)
                if value < MIN_PAGES_PER_DAY or value > MAX_PAGES_PER_DAY:
                    await ctx.respond(f"Pages per day must be between {MIN_PAGES_PER_DAY} and {MAX_PAGES_PER_DAY}!", ephemeral=True)
                    return
            elif setting == "channel" or setting == "followup_channel":
                value = int(value)
                if not ctx.guild.get_channel(value):
                    await ctx.respond("Invalid channel ID!", ephemeral=True)
                    return
                setting = setting + "_id"
            elif setting == "followup_on_completion":
                value = 1 if value.lower() in ['true', 'yes', '1'] else 0
            
            await db.create_or_update_guild(ctx.guild_id, **{setting: value})
            await ctx.respond(f"✅ Updated {setting} to {value}", ephemeral=True)
        except ValueError:
            await ctx.respond("Invalid value!", ephemeral=True)
        finally:
            await db.close()

    @discord.slash_command(name="set_role", description="Set the Wird role (Admin only)")
    @commands.has_permissions(administrator=True)
    async def set_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        db = Database()
        await db.connect()
        
        try:
            await db.create_or_update_guild(ctx.guild_id, wird_role_id=role.id)
            await ctx.respond(f"✅ Set Wird role to {role.mention}", ephemeral=True)
        finally:
            await db.close()

    @discord.slash_command(name="send_now", description="Manually send today's pages (Admin only)")
    @commands.has_permissions(administrator=True)
    async def send_now(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        
        db = Database()
        await db.connect()
        
        try:
            guild_config = await db.get_guild_config(ctx.guild_id)
            if not guild_config or not guild_config['configured']:
                await ctx.respond("Please run `/setup` first!", ephemeral=True)
                return
        finally:
            await db.close()
        
        from utils.page_sender import send_daily_pages
        success = await send_daily_pages(ctx.guild_id, self.bot)
        
        if success:
            await ctx.respond("✅ Pages sent successfully!", ephemeral=True)
        else:
            await ctx.respond("❌ Failed to send pages", ephemeral=True)


def setup(bot):
    bot.add_cog(AdminCog(bot))
