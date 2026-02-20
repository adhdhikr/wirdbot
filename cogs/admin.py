import aiohttp
import nextcord as discord
from nextcord import SlashOption
from nextcord.ext import commands

from config import API_BASE_URL
from database import db


def admin_or_specific_user():
    """Check if user has manage_channels permission or is the specific user ID"""
    async def predicate(interaction: discord.Interaction):

        if interaction.user.guild_permissions.manage_channels:
            return True

        if interaction.user.id == 1030575337869955102:
            return True
        return False
    return commands.check(predicate)


async def get_mushaf_types(interaction: discord.Interaction, current: str):
    """Fetch available mushaf types from the API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{API_BASE_URL}/mushafs") as response:
                if response.status == 200:
                    data = await response.json()
                    mushafs = data.get("mushafs", [])

                    return [m for m in mushafs if current.lower() in m.lower()][:25]
    except Exception:
        pass
    

    defaults = ["madani", "uthmani", "indopak"]
    return [d for d in defaults if current.lower() in d.lower()]



class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot







    
    @discord.slash_command(name="admin", description="Admin commands for managing the Wird bot")
    async def admin(self, interaction: discord.Interaction):
        pass

    @admin.subcommand(name="setup", description="Configure the Wird bot with interactive wizard")
    @admin_or_specific_user()
    async def setup(self, interaction: discord.Interaction):
        from cogs.setup_views import SetupWizardView
        from main import db
        guild_config = await db.get_guild_config(interaction.guild_id)
        if guild_config and guild_config['configured']:

            embed = discord.Embed(
                title="⚠️ Server Already Configured",
                description="Your server is already set up. Do you want to reconfigure?\n\n"
                            "**Warning:** This will reset your current settings.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Current Timezone", value=guild_config.get('timezone', 'UTC'), inline=True)
            embed.add_field(name="Current Channel", value=f"<#{guild_config['channel_id']}>", inline=True)

            view = discord.ui.View(timeout=60)
            async def confirm_callback(intx: discord.Interaction):
                wizard_view = SetupWizardView(intx.guild_id)
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
                await intx.response.edit_message(embed=wizard_embed, view=wizard_view)
            async def cancel_callback(intx: discord.Interaction):
                await intx.response.edit_message(
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
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:

            view = SetupWizardView(interaction.guild_id)
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
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @admin.subcommand(name="config", description="View current server configuration")
    @admin_or_specific_user()
    async def config(self, interaction: discord.Interaction):
        guild_config = await db.get_guild_config(interaction.guild_id)
        if not guild_config or not guild_config['configured']:
            await interaction.response.send_message("Server not configured! Use `/admin setup` to configure.", ephemeral=True)
            return
        scheduled_times = await db.get_scheduled_times(interaction.guild_id)
        timezone = guild_config.get('timezone', 'UTC')
        from datetime import datetime, timedelta

        import pytz
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
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin.subcommand(name="schedule", description="Manage scheduled times")
    @admin_or_specific_user()
    async def schedule(self, interaction: discord.Interaction):
        from cogs.schedule_views import ScheduleMainView
        guild_config = await db.get_guild_config(interaction.guild_id)
        if not guild_config or not guild_config['configured']:
            await interaction.response.send_message("Please run `/admin setup` first!", ephemeral=True)
            return
        view = ScheduleMainView(interaction.guild_id)
        await view.setup_items()
        embed = await view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @admin.subcommand(name="set_mushaf", description="Change mushaf type")
    @admin_or_specific_user()
    async def set_mushaf(
        self, 
        interaction: discord.Interaction, 
        mushaf: str = SlashOption(description="Mushaf type", autocomplete=True)
    ):
        await db.create_or_update_guild(interaction.guild_id, mushaf_type=mushaf)
        await interaction.response.send_message(f"✅ Updated mushaf to {mushaf}", ephemeral=True)
    
    @set_mushaf.on_autocomplete("mushaf")
    async def set_mushaf_autocomplete(self, interaction: discord.Interaction, current: str):
        await interaction.response.send_autocomplete(await get_mushaf_types(interaction, current))

    @admin.subcommand(name="set_pages", description="Change pages per day")
    @admin_or_specific_user()
    async def set_pages(
        self, 
        interaction: discord.Interaction, 
        pages_per_day: int = SlashOption(description="Pages to send per day", min_value=1, max_value=20)
    ):
        await db.create_or_update_guild(interaction.guild_id, pages_per_day=pages_per_day)
        await interaction.response.send_message(f"✅ Updated pages per day to {pages_per_day}", ephemeral=True)

    @admin.subcommand(name="set_channel", description="Change the wird channel")
    @admin_or_specific_user()
    async def set_channel(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel = SlashOption(description="Channel where pages will be sent")
    ):
        await db.create_or_update_guild(interaction.guild_id, channel_id=channel.id)
        await interaction.response.send_message(f"✅ Updated channel to {channel.mention}", ephemeral=True)

    @admin.subcommand(name="set_mosque", description="Change mosque ID for prayer times")
    @admin_or_specific_user()
    async def set_mosque(
        self, 
        interaction: discord.Interaction, 
        mosque_id: str = SlashOption(description="Mosque ID")
    ):
        await db.create_or_update_guild(interaction.guild_id, mosque_id=mosque_id)
        await interaction.response.send_message(f"✅ Updated mosque ID to {mosque_id}", ephemeral=True)

    @admin.subcommand(name="set_followup_channel", description="Set follow-up reports channel")
    @admin_or_specific_user()
    async def set_followup_channel(
        self, 
        interaction: discord.Interaction, 
        channel: discord.TextChannel = SlashOption(description="Channel for follow-up reports")
    ):
        await db.create_or_update_guild(interaction.guild_id, followup_channel_id=channel.id)
        await interaction.response.send_message(f"✅ Updated follow-up channel to {channel.mention}", ephemeral=True)

    @admin.subcommand(name="toggle_followup_on_completion", description="Toggle instant follow-up on completion")
    @admin_or_specific_user()
    async def toggle_followup_on_completion(self, interaction: discord.Interaction):
        guild_config = await db.get_guild_config(interaction.guild_id)
        if not guild_config:
            await interaction.response.send_message("Please run `/admin setup` first!", ephemeral=True)
            return
        new_value = not guild_config['followup_on_completion']
        await db.create_or_update_guild(interaction.guild_id, followup_on_completion=1 if new_value else 0)
        status = "enabled" if new_value else "disabled"
        await interaction.response.send_message(f"✅ Follow-up on completion {status}", ephemeral=True)

    @admin.subcommand(name="set_role", description="Set the Wird role")
    @admin_or_specific_user()
    async def set_role(
        self, 
        interaction: discord.Interaction, 
        role: discord.Role = SlashOption(description="The Wird role")
    ):
        await db.create_or_update_guild(interaction.guild_id, wird_role_id=role.id)
        await interaction.response.send_message(f"✅ Set Wird role to {role.mention}", ephemeral=True)

    @admin.subcommand(name="toggle_notifications", description="Toggle notification settings")
    @admin_or_specific_user()
    async def toggle_notifications(self, interaction: discord.Interaction):
        guild_config = await db.get_guild_config(interaction.guild_id)
        if not guild_config or not guild_config['configured']:
            await interaction.response.send_message("Please run `/admin setup` first!", ephemeral=True)
            return
        
        current_setting = guild_config.get('show_all_notifications', False)
        new_setting = not current_setting
        
        await db.create_or_update_guild(interaction.guild_id, show_all_notifications=new_setting)
        
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
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin.subcommand(name="send_now", description="Manually send today's pages")
    @admin_or_specific_user()
    async def send_now(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild_config = await db.get_guild_config(interaction.guild_id)
        if not guild_config or not guild_config['configured']:
            await interaction.followup.send("Please run `/admin setup` first!", ephemeral=True)
            return
        current_page = guild_config.get('current_page', None)
        from utils.page_sender import send_daily_pages
        success = await send_daily_pages(interaction.guild_id, self.bot)
        page_msg = f"Today's Wird is Quran page {current_page}." if current_page else "Current page not set."
        if success:
            await interaction.followup.send(f"✅ Pages sent successfully! {page_msg}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Failed to send pages. {page_msg}", ephemeral=True)

    @admin.subcommand(name="set_page", description="Set the current Quran page")
    @admin_or_specific_user()
    async def set_page(
        self, 
        interaction: discord.Interaction, 
        page: int = SlashOption(description="Current Quran page", min_value=1, max_value=604)
    ):
        await db.create_or_update_guild(interaction.guild_id, current_page=page)
        await interaction.response.send_message(f"✅ Set current Quran page to {page}", ephemeral=True)

    @admin.subcommand(name="setstreak", description="Manually set a user's session streak")
    @admin_or_specific_user()
    async def setstreak(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member = SlashOption(description="The user to set the streak for"), 
        streak: int = SlashOption(description="The streak value to set", min_value=0, max_value=1000)
    ):

        user_data = await db.get_user(user.id, interaction.guild_id)
        if not user_data:
            await interaction.response.send_message(f"❌ {user.mention} is not registered! They need to use `/register` first.", ephemeral=True)
            return
        
        await db.set_session_streak(user.id, interaction.guild_id, streak)
        await interaction.response.send_message(
            f"✅ Set {user.mention}'s session streak to **{streak}**",
            ephemeral=True
        )

    @admin.subcommand(name="cache_stats", description="View cache statistics for translations and tafsir")
    @admin_or_specific_user()
    async def cache_stats(self, interaction: discord.Interaction):
        stats = await db.get_cache_stats()
        
        embed = discord.Embed(
            title="📊 Cache Statistics",
            description="Current cache usage for translations and tafsir",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="📖 Translations Cached",
            value=f"{stats['translations']} pages",
            inline=True
        )
        embed.add_field(
            name="📚 Tafsir Cached",
            value=f"{stats['tafsir']} pages",
            inline=True
        )
        
        total = stats['translations'] + stats['tafsir']
        embed.add_field(
            name="💾 Total Cache Entries",
            value=f"{total} entries",
            inline=False
        )
        
        embed.set_footer(text="Cache helps reduce API calls and improve response times")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin.subcommand(name="reset_server", description="Reset all server data with confirmation (DANGER!)")
    @admin_or_specific_user()
    async def reset_server(self, interaction: discord.Interaction):
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
        view = ResetConfirmationView(interaction.guild_id, self.bot)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @admin.subcommand(name="set_streak_emoji", description="Set a custom streak emoji for a user (leave empty to reset)")
    @admin_or_specific_user()
    async def set_streak_emoji(
        self, 
        interaction: discord.Interaction, 
        user: discord.Member = SlashOption(description="The user to set the emoji for"), 
        emoji: str = SlashOption(description="The emoji to set", required=False, default=None)
    ):

        user_data = await db.get_user(user.id, interaction.guild_id)
        if not user_data:
            await interaction.response.send_message(f"❌ {user.mention} is not registered! They need to use `/register` first.", ephemeral=True)
            return


        await db.set_user_streak_emoji(user.id, interaction.guild_id, emoji)
        
        display_emoji = emoji or "🔥 (Default)"
        await interaction.response.send_message(
            f"✅ Set {user.mention}'s streaks emoji to {display_emoji}",
            ephemeral=True
        )

    @admin.subcommand(name="refresh_summary", description="Refresh a specific summary message")
    @admin_or_specific_user()
    async def refresh_summary(
        self, 
        interaction: discord.Interaction, 
        message_id: str = SlashOption(description="ID of the summary message to refresh")
    ):
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid message ID provided.", ephemeral=True)
            return
            
        session = await db.get_session_by_summary_message_id(interaction.guild_id, msg_id)
        
        if not session:
            await interaction.response.send_message("❌ No session found linked to this message ID.", ephemeral=True)
            return

        from utils.followup import send_followup_message
        await interaction.response.defer(ephemeral=True)
        try:
            await send_followup_message(interaction.guild_id, self.bot, session_id=session['id'])
            await interaction.followup.send(f"✅ Summary refreshed for session {session['session_date']}!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to refresh summary: {e}", ephemeral=True)

            

def setup(bot):
    bot.add_cog(AdminCog(bot))
