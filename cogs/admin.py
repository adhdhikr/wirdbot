import discord
from discord.ext import commands
from discord import option
from views import ScheduleTimeModal
from database import db
from utils.user_management import assign_role, remove_role
import aiohttp
from config import API_BASE_URL


async def get_mushaf_types(ctx: discord.AutocompleteContext):
    """Fetch available mushaf types from the API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/mushafs") as response:
                if response.status == 200:
                    data = await response.json()
                    mushafs = data.get("mushafs", [])
                    return mushafs[:25]  # Discord limits to 25 options
    except Exception:
        pass
    
    # Fallback to defaults if API is unavailable
    return ["madani", "uthmani", "indopak"]



class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.slash_command(name="setup", description="Configure the Wird bot with interactive wizard (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    async def setup(self, ctx: discord.ApplicationContext):
        from cogs.setup_views import SetupWizardView
        from main import db
        guild_config = await db.get_guild_config(ctx.guild_id)
        if guild_config and guild_config['configured']:
            # Show reconfiguration warning
            embed = discord.Embed(
                title="⚠️ Server Already Configured",
                description="Your server is already set up. Do you want to reconfigure?\n\n"
                            "**Warning:** This will reset your current settings.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Current Timezone", value=guild_config.get('timezone', 'UTC'), inline=True)
            embed.add_field(name="Current Channel", value=f"<#{guild_config['channel_id']}>", inline=True)
            # Add confirmation view
            view = discord.ui.View(timeout=60)
            async def confirm_callback(interaction: discord.Interaction):
                wizard_view = SetupWizardView(ctx.guild_id)
                wizard_embed = discord.Embed(
                    title="⚙️ Setup Wizard",
                    description="Welcome to the Wird Bot Setup Wizard! 🎉\n\n"
                                "This interactive guide will help you configure:\n"
                                "• 🌍 Your timezone\n"
                                "• 🕐 Daily schedule time\n"
                                "• 📺 Channel for pages\n"
                                "• 📖 Mushaf style\n"
                                "• ⚙️ Additional settings\n\n"
                                "Let's get started!",
                    color=discord.Color.blurple()
                )
                await interaction.response.edit_message(embed=wizard_embed, view=wizard_view)
            async def cancel_callback(interaction: discord.Interaction):
                await interaction.response.edit_message(
                    content="Setup cancelled. Your current configuration is unchanged.",
                    embed=None,
                    view=None
                )
            confirm_btn = discord.ui.Button(label="Reconfigure", style=discord.ButtonStyle.danger)
            confirm_btn.callback = confirm_callback
            cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
            cancel_btn.callback = cancel_callback
            view.add_item(confirm_btn)
            view.add_item(cancel_btn)
            await ctx.respond(embed=embed, view=view, ephemeral=True)
        else:
            # Start fresh setup
            view = SetupWizardView(ctx.guild_id)
            embed = discord.Embed(
                title="⚙️ Setup Wizard",
                description="Welcome to the Wird Bot Setup Wizard! 🎉\n\n"
                            "This interactive guide will help you configure:\n"
                            "• 🌍 Your timezone\n"
                            "• 🕐 Daily schedule time\n"
                            "• 📺 Channel for pages\n"
                            "• 📖 Mushaf style\n"
                            "• ⚙️ Additional settings\n\n"
                            "Let's get started!",
                color=discord.Color.blurple()
            )
            await ctx.respond(embed=embed, view=view, ephemeral=True)
        guild_config = await db.get_guild_config(ctx.guild_id)
        if not guild_config or not guild_config['configured']:
            await ctx.respond("Server not configured! Use `/setup` to configure.", ephemeral=True)
            return
        scheduled_times = await db.get_scheduled_times(ctx.guild_id)
        timezone = guild_config.get('timezone', 'UTC')
        import pytz
        from datetime import datetime, timedelta
        times_str = ""
        next_schedule_dt = None
        for st in scheduled_times:
            if st['time_type'] == 'custom':
                utc_time = datetime.strptime(st['time_value'], '%H:%M').replace(tzinfo=pytz.UTC)
                local_tz = pytz.timezone(timezone)
                local_time = utc_time.astimezone(local_tz)
                formatted_time = local_time.strftime('%I:%M %p')
                if formatted_time[0] == '0':
                    formatted_time = formatted_time[1:]
                times_str += f"• Custom: {formatted_time} ({timezone})\n"
                now = datetime.now(local_tz)
                next_time = local_time.replace(year=now.year, month=now.month, day=now.day)
                if next_time < now:
                    next_time += timedelta(days=1)
                if not next_schedule_dt or next_time < next_schedule_dt:
                    next_schedule_dt = next_time
            else:
                times_str += f"• Prayer: {st['time_type'].title()}\n"
        if not times_str:
            times_str = "No scheduled times set"
        embed = discord.Embed(title="⚙️ Server Configuration", color=discord.Color.blue())
        embed.add_field(name="🌍 Timezone", value=timezone, inline=True)
        embed.add_field(name="🕌 Mosque ID", value=guild_config['mosque_id'] or "Not set", inline=True)
        embed.add_field(name="📖 Mushaf Type", value=guild_config['mushaf_type'], inline=True)
        embed.add_field(name="📄 Pages/Day", value=guild_config['pages_per_day'], inline=True)
        embed.add_field(name="📺 Channel", value=f"<#{guild_config['channel_id']}>", inline=True)
        embed.add_field(name="📊 Current Page", value=guild_config['current_page'], inline=True)
        embed.add_field(name="🎭 Wird Role", value=f"<@&{guild_config['wird_role_id']}>" if guild_config['wird_role_id'] else "Not set", inline=True)
        embed.add_field(name="💬 Follow-up Channel", value=f"<#{guild_config['followup_channel_id']}>" if guild_config['followup_channel_id'] else "Same as main channel", inline=True)
        embed.add_field(name="✅ Follow-up on Completion", value="✅" if guild_config['followup_on_completion'] else "❌", inline=True)
        embed.add_field(name="🔔 Show All Notifications", value="✅" if guild_config.get('show_all_notifications', False) else "❌", inline=True)
        embed.add_field(name="⏰ Scheduled Times", value=times_str, inline=False)
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz).strftime('%I:%M %p, %B %d, %Y')
        if next_schedule_dt:
            unix_ts = int(next_schedule_dt.timestamp())
            embed.set_footer(text=f"Current time in {timezone}: {current_time} | Next scheduled: <t:{unix_ts}:R>")
        else:
            embed.set_footer(text=f"Current time in {timezone}: {current_time}")
        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name="schedule", description="Manage scheduled times (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    async def schedule(self, ctx: discord.ApplicationContext):
        from cogs.schedule_views import ScheduleMainView
        guild_config = await db.get_guild_config(ctx.guild_id)
        if not guild_config or not guild_config['configured']:
            await ctx.respond("Please run `/setup` first!", ephemeral=True)
            return
        view = ScheduleMainView(ctx.guild_id)
        await view.setup_items()
        embed = await view.create_embed()
        await ctx.respond(embed=embed, view=view, ephemeral=True)

    @discord.slash_command(name="set_mushaf", description="Change mushaf type (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    @option("mushaf", description="Mushaf type", autocomplete=get_mushaf_types)
    async def set_mushaf(self, ctx: discord.ApplicationContext, mushaf: str):
        await db.create_or_update_guild(ctx.guild_id, mushaf_type=mushaf)
        await ctx.respond(f"✅ Updated mushaf to {mushaf}", ephemeral=True)

    @discord.slash_command(name="set_pages", description="Change pages per day (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    @option("pages_per_day", description="Pages to send per day", min_value=1, max_value=20)
    async def set_pages(self, ctx: discord.ApplicationContext, pages_per_day: int):
        await db.create_or_update_guild(ctx.guild_id, pages_per_day=pages_per_day)
        await ctx.respond(f"✅ Updated pages per day to {pages_per_day}", ephemeral=True)

    @discord.slash_command(name="set_channel", description="Change the wird channel (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    @option("channel", description="Channel where pages will be sent", type=discord.TextChannel)
    async def set_channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        await db.create_or_update_guild(ctx.guild_id, channel_id=channel.id)
        await ctx.respond(f"✅ Updated channel to {channel.mention}", ephemeral=True)

    @discord.slash_command(name="set_mosque", description="Change mosque ID for prayer times (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    @option("mosque_id", description="Mosque ID")
    async def set_mosque(self, ctx: discord.ApplicationContext, mosque_id: str):
        await db.create_or_update_guild(ctx.guild_id, mosque_id=mosque_id)
        await ctx.respond(f"✅ Updated mosque ID to {mosque_id}", ephemeral=True)

    @discord.slash_command(name="set_followup_channel", description="Set follow-up reports channel (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    @option("channel", description="Channel for follow-up reports", type=discord.TextChannel)
    async def set_followup_channel(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        await db.create_or_update_guild(ctx.guild_id, followup_channel_id=channel.id)
        await ctx.respond(f"✅ Updated follow-up channel to {channel.mention}", ephemeral=True)

    @discord.slash_command(name="toggle_followup_on_completion", description="Toggle instant follow-up on completion (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    async def toggle_followup_on_completion(self, ctx: discord.ApplicationContext):
        guild_config = await db.get_guild_config(ctx.guild_id)
        if not guild_config:
            await ctx.respond("Please run `/setup` first!", ephemeral=True)
            return
        new_value = not guild_config['followup_on_completion']
        await db.create_or_update_guild(ctx.guild_id, followup_on_completion=1 if new_value else 0)
        status = "enabled" if new_value else "disabled"
        await ctx.respond(f"✅ Follow-up on completion {status}", ephemeral=True)

    @discord.slash_command(name="update", description="[DEPRECATED] Use specific set_ commands instead")
    @commands.has_permissions(manage_channels=True)
    @option("setting", choices=["mushaf", "pages_per_day", "channel", "mosque_id", "followup_channel", "followup_on_completion"])
    @option("value", description="New value for the setting")
    async def update(self, ctx: discord.ApplicationContext, setting: str, value: str):
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

    @discord.slash_command(name="set_role", description="Set the Wird role (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    async def set_role(self, ctx: discord.ApplicationContext, role: discord.Role):
        await db.create_or_update_guild(ctx.guild_id, wird_role_id=role.id)
        await ctx.respond(f"✅ Set Wird role to {role.mention}", ephemeral=True)

    @discord.slash_command(name="toggle_notifications", description="Toggle notification settings (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    async def toggle_notifications(self, ctx: discord.ApplicationContext):
        guild_config = await db.get_guild_config(ctx.guild_id)
        if not guild_config or not guild_config['configured']:
            await ctx.respond("Please run `/setup` first!", ephemeral=True)
            return
        
        current_setting = guild_config.get('show_all_notifications', False)
        new_setting = not current_setting
        
        await db.create_or_update_guild(ctx.guild_id, show_all_notifications=new_setting)
        
        status = "enabled" if new_setting else "disabled"
        description = (
            "Users will now receive notifications for **all button presses** (marking pages complete, progress updates, etc.)"
            if new_setting else
            "Users will now only receive notifications for **completion celebrations** when they finish all pages for the day, plus error messages and registration prompts."
        )
        
        embed = discord.Embed(
            title="🔔 Notification Settings Updated",
            description=f"**Show all notifications:** {status}\n\n{description}",
            color=discord.Color.green() if new_setting else discord.Color.blue()
        )
        
        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name="send_now", description="Manually send today's pages (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    async def send_now(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)
        guild_config = await db.get_guild_config(ctx.guild_id)
        if not guild_config or not guild_config['configured']:
            await ctx.respond("Please run `/setup` first!", ephemeral=True)
            return
        current_page = guild_config.get('current_page', None)
        from utils.page_sender import send_daily_pages
        success = await send_daily_pages(ctx.guild_id, self.bot)
        page_msg = f"Today's Wird is Quran page {current_page}." if current_page else "Current page not set."
        if success:
            await ctx.respond(f"✅ Pages sent successfully! {page_msg}", ephemeral=True)
        else:
            await ctx.respond(f"❌ Failed to send pages. {page_msg}", ephemeral=True)

    @discord.slash_command(name="set_page", description="Set the current Quran page (Manage Channels permission required)")
    @commands.has_permissions(manage_channels=True)
    @option("page", description="Current Quran page", min_value=1, max_value=604)
    async def set_page(self, ctx: discord.ApplicationContext, page: int):
        await db.create_or_update_guild(ctx.guild_id, current_page=page)
        await ctx.respond(f"✅ Set current Quran page to {page}", ephemeral=True)

    @discord.slash_command(name="reset_server", description="Reset all server data with confirmation (Admin only - DANGER!)")
    @commands.has_permissions(manage_channels=True)
    async def reset_server(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(
            title="⚠️ DANGER: Reset Server Data",
            description="This will **permanently delete** ALL Wird bot data for this server:\n\n"
                        "• Guild configuration and settings\n"
                        "• All user registrations and streaks\n"
                        "• All completion records and progress\n"
                        "• Scheduled times and automation\n"
                        "• Daily session history\n\n"
                        "**This action cannot be undone!**\n\n"
                        "Are you absolutely sure you want to reset everything?",
            color=discord.Color.red()
        )
        
        from views import ResetConfirmationView
        view = ResetConfirmationView(ctx.guild_id, self.bot)
        await ctx.respond(embed=embed, view=view, ephemeral=True)
            

def setup(bot):
    bot.add_cog(AdminCog(bot))
