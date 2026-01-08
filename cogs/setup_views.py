# At the end of the file, add the setup function for extension loading

def setup(bot):
    pass
import discord
from discord.ui import View, Button, Select, Modal, InputText
from database import db
from typing import Optional
import pytz
from datetime import datetime


# Common timezones organized by region with major cities
TIMEZONE_REGIONS = {
    "🌎 Americas": [
        ("New York, Toronto", "America/New_York"),
        ("Chicago, Mexico City", "America/Chicago"),
        ("Denver, Phoenix", "America/Denver"),
        ("Los Angeles, Vancouver", "America/Los_Angeles"),
        ("São Paulo, Buenos Aires", "America/Sao_Paulo"),
    ],
    "🌍 Europe & Africa": [
        ("London, Lisbon", "Europe/London"),
        ("Paris, Berlin, Rome", "Europe/Paris"),
        ("Cairo, Johannesburg", "Africa/Cairo"),
        ("Moscow, Istanbul", "Europe/Moscow"),
        ("Dubai, Abu Dhabi", "Asia/Dubai"),
    ],
    "🌏 Asia & Pacific": [
        ("Tokyo, Seoul", "Asia/Tokyo"),
        ("Singapore, Hong Kong", "Asia/Singapore"),
        ("Shanghai, Beijing", "Asia/Shanghai"),
        ("Mumbai, Delhi", "Asia/Kolkata"),
        ("Jakarta, Bangkok", "Asia/Jakarta"),
        ("Sydney, Melbourne", "Australia/Sydney"),
    ],
}


class SetupWizardView(View):
    """Main setup wizard view - Step 1: Welcome"""
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        
        start_button = Button(
            label="Start Setup",
            style=discord.ButtonStyle.success,
            emoji="▶️",
            custom_id="start_setup"
        )
        start_button.callback = self.start_setup
        self.add_item(start_button)
    
    async def start_setup(self, interaction: discord.Interaction):
        """Move to timezone selection"""
        view = TimezoneRegionView(self.guild_id)
        embed = discord.Embed(
            title="⚙️ Setup Wizard - Step 1/5",
            description="**Select Your Region**\n\nChoose the region where your community is located:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)


class TimezoneRegionView(View):
    """Step 2: Select timezone region"""
    def __init__(self, guild_id: int, setup_data: Optional[dict] = None):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.setup_data = setup_data or {}
        
        # Add region buttons
        for region, timezones in TIMEZONE_REGIONS.items():
            button = Button(
                label=region,
                style=discord.ButtonStyle.primary,
                custom_id=f"region_{region}"
            )
            button.callback = self.create_region_callback(region, timezones)
            self.add_item(button)
        
        # Add manual entry button
        manual_button = Button(
            label="Enter Manually",
            style=discord.ButtonStyle.secondary,
            emoji="✍️",
            custom_id="manual_tz"
        )
        manual_button.callback = self.manual_timezone
        self.add_item(manual_button)
    
    def create_region_callback(self, region: str, timezones: list):
        async def callback(interaction: discord.Interaction):
            view = TimezoneSelectView(self.guild_id, region, timezones, self.setup_data)
            embed = discord.Embed(
                title="⚙️ Setup Wizard - Step 1/5",
                description=f"**Select Your Timezone** ({region})\n\nChoose the city/timezone closest to you:",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=view)
        return callback
    
    async def manual_timezone(self, interaction: discord.Interaction):
        """Show modal for manual timezone entry"""
        modal = TimezoneManualModal(self.guild_id, self.setup_data)
        await interaction.response.send_modal(modal)


class TimezoneSelectView(View):
    """Step 2b: Select specific timezone from region"""
    def __init__(self, guild_id: int, region: str, timezones: list, setup_data: dict):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.region = region
        self.setup_data = setup_data
        
        # Create timezone options
        options = []
        for city, tz_name in timezones:
            tz = pytz.timezone(tz_name)
            now = datetime.now(tz)
            offset = now.strftime('%z')
            formatted_offset = f"UTC{offset[:3]}:{offset[3:]}"
            
            options.append(discord.SelectOption(
                label=f"{city}",
                value=tz_name,
                description=f"{formatted_offset}"
            ))
        
        select = Select(
            placeholder="Select your timezone...",
            options=options,
            custom_id="timezone_select"
        )
        select.callback = self.timezone_selected
        self.add_item(select)
        
        # Back button
        back_button = Button(
            label="Back",
            style=discord.ButtonStyle.secondary,
            emoji="◀️",
            custom_id="back"
        )
        back_button.callback = self.back
        self.add_item(back_button)
    
    async def timezone_selected(self, interaction: discord.Interaction):
        """Store timezone and move to channel selection"""
        timezone = interaction.data['values'][0]
        self.setup_data['timezone'] = timezone
        
        view = ChannelSelectView(self.guild_id, self.setup_data, interaction.guild)
        
        # Show current time in selected timezone
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz).strftime('%I:%M %p')
        
        embed = discord.Embed(
            title="⚙️ Setup Wizard - Step 2/5",
            description=f"**Select Channel**\n\n✅ Timezone set to: `{timezone}`\n🕐 Current time: {current_time}\n\nNow, select the channel where pages will be sent:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def back(self, interaction: discord.Interaction):
        """Go back to region selection"""
        view = TimezoneRegionView(self.guild_id, self.setup_data)
        embed = discord.Embed(
            title="⚙️ Setup Wizard - Step 1/5",
            description="**Select Your Region**\n\nChoose the region where your community is located:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)


class TimezoneManualModal(Modal):
    """Modal for manual timezone entry"""
    def __init__(self, guild_id: int, setup_data: dict):
        super().__init__(title="Enter Timezone")
        self.guild_id = guild_id
        self.setup_data = setup_data
        
        self.add_item(InputText(
            label="Timezone (e.g., America/New_York)",
            placeholder="Enter timezone name or search for your city",
            required=True
        ))
    
    async def callback(self, interaction: discord.Interaction):
        timezone_input = self.children[0].value.strip()
        
        # Try to find matching timezone
        try:
            # Direct match
            if timezone_input in pytz.all_timezones:
                timezone = timezone_input
            else:
                # Search for city name
                matches = [tz for tz in pytz.all_timezones if timezone_input.lower() in tz.lower()]
                if matches:
                    timezone = matches[0]
                else:
                    await interaction.response.send_message(
                        f"❌ Could not find timezone: `{timezone_input}`\n\n"
                        "Try formats like:\n"
                        "• `America/New_York`\n"
                        "• `Europe/London`\n"
                        "• `Asia/Tokyo`",
                        ephemeral=True
                    )
                    return
            
            self.setup_data['timezone'] = timezone
            
            view = ChannelSelectView(self.guild_id, self.setup_data)
            
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz).strftime('%I:%M %p')
            
            embed = discord.Embed(
                title="⚙️ Setup Wizard - Step 2/5",
                description=f"**Select Channel**\n\n✅ Timezone set to: `{timezone}`\n🕐 Current time: {current_time}\n\nNow, select the channel where pages will be sent:",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class ChannelSelectView(View):
    """Step 3: Select channel"""
    def __init__(self, guild_id: int, setup_data: dict, guild: discord.Guild):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.setup_data = setup_data
        
        # Get text channels from the guild
        text_channels = [ch for ch in guild.channels if isinstance(ch, discord.TextChannel)]
        
        # Create options from channels (limit to 25 for Discord's limit)
        options = []
        for channel in text_channels[:25]:
            options.append(discord.SelectOption(
                label=f"#{channel.name}",
                value=str(channel.id),
                description=f"ID: {channel.id}"
            ))
        
        if options:
            select = Select(
                placeholder="Select a channel...",
                options=options,
                custom_id="channel_select"
            )
            select.callback = self.channel_selected
            self.add_item(select)
        else:
            # Fallback: use a button to enter channel ID manually
            manual_button = Button(
                label="Enter Channel ID",
                style=discord.ButtonStyle.primary,
                emoji="✍️",
                custom_id="manual_channel"
            )
            manual_button.callback = self.manual_channel
            self.add_item(manual_button)
        
        back_button = Button(
            label="Back",
            style=discord.ButtonStyle.secondary,
            emoji="◀️",
            custom_id="back"
        )
        back_button.callback = self.back
        self.add_item(back_button)
    
    async def channel_selected(self, interaction: discord.Interaction):
        """Store channel and move to time selection"""
        channel_id = int(interaction.data['values'][0])
        self.setup_data['channel_id'] = channel_id
        
        view = InitialTimeView(self.guild_id, self.setup_data)
        embed = discord.Embed(
            title="⚙️ Setup Wizard - Step 3/5",
            description=f"**Set Initial Time**\n\n✅ Channel: <#{channel_id}>\n\nNow, set the first time when pages should be sent daily.\nThis time is in **your timezone** ({self.setup_data['timezone']}):",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def manual_channel(self, interaction: discord.Interaction):
        """Show modal for manual channel ID entry"""
        modal = ChannelManualModal(self.guild_id, self.setup_data)
        await interaction.response.send_modal(modal)
    
    async def back(self, interaction: discord.Interaction):
        """Go back to timezone selection"""
        view = TimezoneRegionView(self.guild_id, self.setup_data)
        embed = discord.Embed(
            title="⚙️ Setup Wizard - Step 1/5",
            description="**Select Your Region**\n\nChoose the region where your community is located:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)


class ChannelManualModal(Modal):
    """Modal for manual channel ID entry"""
    def __init__(self, guild_id: int, setup_data: dict):
        super().__init__(title="Enter Channel ID")
        self.guild_id = guild_id
        self.setup_data = setup_data
        
        self.add_item(InputText(
            label="Channel ID or #channel-mention",
            placeholder="Right-click channel → Copy ID, or type #channel",
            required=True
        ))
    
    async def callback(self, interaction: discord.Interaction):
        channel_input = self.children[0].value.strip()
        
        try:
            # Extract channel ID from mention format or use directly
            if channel_input.startswith('<#') and channel_input.endswith('>'):
                channel_id = int(channel_input[2:-1])
            else:
                channel_id = int(channel_input)
            
            # Verify channel exists
            channel = interaction.guild.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.TextChannel):
                await interaction.response.send_message(
                    "❌ Invalid channel! Please provide a valid text channel ID.",
                    ephemeral=True
                )
                return
            
            self.setup_data['channel_id'] = channel_id
            
            view = InitialTimeView(self.guild_id, self.setup_data)
            embed = discord.Embed(
                title="⚙️ Setup Wizard - Step 3/5",
                description=f"**Set Initial Time**\n\n✅ Channel: <#{channel_id}>\n\nNow, set the first time when pages should be sent daily.\nThis time is in **your timezone** ({self.setup_data['timezone']}):",
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(embed=embed, view=view)
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid format! Please provide a channel ID (e.g., 123456789) or mention (#channel).",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class InitialTimeView(View):
    """Step 4: Set initial time"""
    def __init__(self, guild_id: int, setup_data: dict):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.setup_data = setup_data
        
        time_button = Button(
            label="Enter Time",
            style=discord.ButtonStyle.success,
            emoji="🕐",
            custom_id="enter_time"
        )
        time_button.callback = self.enter_time
        self.add_item(time_button)
        
        back_button = Button(
            label="Back",
            style=discord.ButtonStyle.secondary,
            emoji="◀️",
            custom_id="back"
        )
        back_button.callback = self.back
        self.add_item(back_button)
    
    async def enter_time(self, interaction: discord.Interaction):
        """Show time entry modal"""
        modal = InitialTimeModal(self.guild_id, self.setup_data)
        await interaction.response.send_modal(modal)
    
    async def back(self, interaction: discord.Interaction):
        """Go back to channel selection"""
        view = ChannelSelectView(self.guild_id, self.setup_data)
        embed = discord.Embed(
            title="⚙️ Setup Wizard - Step 2/5",
            description=f"**Select Channel**\n\n✅ Timezone: `{self.setup_data['timezone']}`\n\nSelect the channel where pages will be sent:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)


class InitialTimeModal(Modal):
    """Modal for entering initial time"""
    def __init__(self, guild_id: int, setup_data: dict):
        super().__init__(title="Enter Time")
        self.guild_id = guild_id
        self.setup_data = setup_data
        
        self.add_item(InputText(
            label=f"Time in {setup_data.get('timezone', 'your timezone')}",
            placeholder="e.g., 8:00 AM or 20:30",
            required=True
        ))
    
    async def callback(self, interaction: discord.Interaction):
        time_input = self.children[0].value.strip()
        
        try:
            # Parse time input (support multiple formats)
            time_input_upper = time_input.upper()
            
            # Remove spaces
            time_input_upper = time_input_upper.replace(' ', '')
            
            # Handle AM/PM format
            if 'AM' in time_input_upper or 'PM' in time_input_upper:
                is_pm = 'PM' in time_input_upper
                time_part = time_input_upper.replace('AM', '').replace('PM', '')
                
                if ':' in time_part:
                    hours, minutes = map(int, time_part.split(':'))
                else:
                    hours = int(time_part)
                    minutes = 0
                
                if hours == 12:
                    hours = 0 if not is_pm else 12
                elif is_pm:
                    hours += 12
            else:
                # 24-hour format
                if ':' in time_input:
                    hours, minutes = map(int, time_input.split(':'))
                else:
                    hours = int(time_input)
                    minutes = 0
            
            # Validate
            if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                await interaction.response.send_message(
                    "❌ Invalid time! Use format like:\n• `8:00 AM`\n• `14:30`\n• `9 PM`",
                    ephemeral=True
                )
                return
            
            # Convert to UTC
            tz = pytz.timezone(self.setup_data['timezone'])
            local_time = datetime.now(tz).replace(hour=hours, minute=minutes, second=0, microsecond=0)
            utc_time = local_time.astimezone(pytz.UTC)
            
            time_value = f"{utc_time.hour:02d}:{utc_time.minute:02d}"
            self.setup_data['initial_time'] = time_value
            self.setup_data['initial_time_local'] = f"{hours:02d}:{minutes:02d}"
            
            # Show loading message while fetching mushafs
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="⚙️ Setup Wizard - Step 4/5",
                    description="Loading mushaf options...",
                    color=discord.Color.blue()
                ),
                view=None
            )
            
            view = MushafSelectView(self.guild_id, self.setup_data)
            await view.fetch_mushafs()
            
            embed = discord.Embed(
                title="⚙️ Setup Wizard - Step 4/5",
                description=f"**Select Mushaf Type**\n\n✅ Time set: {hours:02d}:{minutes:02d} ({self.setup_data['timezone']})\n\nChoose the Mushaf (Quran) style you prefer:",
                color=discord.Color.blue()
            )
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=view)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid time format! Use:\n• `8:00 AM` or `8 AM`\n• `14:30` or `2:30 PM`",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


class MushafSelectView(View):
    """Step 5: Select mushaf type"""
    def __init__(self, guild_id: int, setup_data: dict):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.setup_data = setup_data
        self.mushafs = []
    
    async def fetch_mushafs(self):
        """Fetch available mushaf types from the API"""
        import aiohttp
        from config import API_BASE_URL
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}/mushafs") as response:
                    if response.status == 200:
                        data = await response.json()
                        self.mushafs = data.get("mushafs", [])[:25]  # Discord limits to 25 options
        except Exception:
            pass
        
        # Fallback to defaults if API is unavailable
        if not self.mushafs:
            self.mushafs = ["madani", "uthmani", "indopak"]
        
        # Create select options
        options = []
        emoji_map = {
            "madani": "📖",
            "uthmani": "📕",
            "indopak": "📘",
        }
        
        for mushaf in self.mushafs:
            emoji = emoji_map.get(mushaf, "📚")
            options.append(discord.SelectOption(
                label=mushaf.replace("-", " ").title(),
                value=mushaf,
                emoji=emoji
            ))
        
        select = Select(
            placeholder="Select mushaf type...",
            options=options,
            custom_id="mushaf_select"
        )
        select.callback = self.mushaf_selected
        self.add_item(select)
        
        back_button = Button(
            label="Back",
            style=discord.ButtonStyle.secondary,
            emoji="◀️",
            custom_id="back"
        )
        back_button.callback = self.back
        self.add_item(back_button)
    
    async def mushaf_selected(self, interaction: discord.Interaction):
        """Store mushaf and move to final confirmation"""
        mushaf = interaction.data['values'][0]
        self.setup_data['mushaf'] = mushaf
        
        view = FinalConfigView(self.guild_id, self.setup_data)
        
        tz = self.setup_data['timezone']
        local_time = self.setup_data['initial_time_local']
        
        embed = discord.Embed(
            title="⚙️ Setup Wizard - Step 5/5",
            description="**Final Configuration**\n\nReview your settings and customize additional options:",
            color=discord.Color.blue()
        )
        embed.add_field(name="🌍 Timezone", value=tz, inline=True)
        embed.add_field(name="🕐 Initial Time", value=f"{local_time} ({tz})", inline=True)
        embed.add_field(name="📺 Channel", value=f"<#{self.setup_data['channel_id']}>", inline=True)
        embed.add_field(name="📖 Mushaf", value=mushaf.title(), inline=True)
        
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def back(self, interaction: discord.Interaction):
        """Go back to time selection"""
        view = InitialTimeView(self.guild_id, self.setup_data)
        embed = discord.Embed(
            title="⚙️ Setup Wizard - Step 3/5",
            description=f"**Set Initial Time**\n\n✅ Channel: <#{self.setup_data['channel_id']}>\n\nSet the first time when pages should be sent daily:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)


class FinalConfigView(View):
    """Step 6: Final configuration and confirmation"""
    def __init__(self, guild_id: int, setup_data: dict):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.setup_data = setup_data
        
        # Pages per day input
        pages_button = Button(
            label="Pages Per Day (Default: 1)",
            style=discord.ButtonStyle.secondary,
            emoji="📄",
            custom_id="pages"
        )
        pages_button.callback = self.set_pages
        self.add_item(pages_button)
        
        # Mosque ID input (optional)
        mosque_button = Button(
            label="Set Mosque ID (Optional)",
            style=discord.ButtonStyle.secondary,
            emoji="🕌",
            custom_id="mosque"
        )
        mosque_button.callback = self.set_mosque
        self.add_item(mosque_button)
        
        # Notification settings
        notifications_button = Button(
            label="Notification Settings",
            style=discord.ButtonStyle.secondary,
            emoji="🔔",
            custom_id="notifications"
        )
        notifications_button.callback = self.set_notifications
        self.add_item(notifications_button)
        
        # Finish button
        finish_button = Button(
            label="Complete Setup",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id="finish"
        )
        finish_button.callback = self.finish_setup
        self.add_item(finish_button)
        
        # Back button
        back_button = Button(
            label="Back",
            style=discord.ButtonStyle.secondary,
            emoji="◀️",
            custom_id="back"
        )
        back_button.callback = self.back
        self.add_item(back_button)
    
    async def set_pages(self, interaction: discord.Interaction):
        """Show modal for pages per day"""
        modal = PagesPerDayModal(self.guild_id, self.setup_data)
        await interaction.response.send_modal(modal)
    
    async def set_mosque(self, interaction: discord.Interaction):
        """Show modal for mosque ID"""
        modal = MosqueIdModal(self.guild_id, self.setup_data)
        await interaction.response.send_modal(modal)
    
    async def set_notifications(self, interaction: discord.Interaction):
        """Toggle notification settings"""
        view = NotificationSettingsView(self.guild_id, self.setup_data)
        embed = discord.Embed(
            title="🔔 Notification Settings",
            description="Choose when users receive notifications for button presses:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Show All Notifications",
            value="When enabled: Users get messages for every button press (marking pages complete, progress updates).\n\n"
                  "When disabled: Users only see completion celebrations when they finish all pages for the day, plus error messages and registration prompts.",
            inline=False
        )
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def finish_setup(self, interaction: discord.Interaction):
        """Save configuration to database"""
        # ...existing code...
        
        try:
            # Set defaults
            pages_per_day = self.setup_data.get('pages_per_day', 1)
            mosque_id = self.setup_data.get('mosque_id', 'cio-gatineau')
            
            # Create guild config
            await db.create_or_update_guild(
                self.guild_id,
                timezone=self.setup_data['timezone'],
                channel_id=self.setup_data['channel_id'],
                mushaf_type=self.setup_data['mushaf'],
                pages_per_day=pages_per_day,
                mosque_id=mosque_id,
                show_all_notifications=self.setup_data.get('show_all_notifications', False),
                configured=1
            )
            
            # Add initial scheduled time
            await db.add_scheduled_time(
                self.guild_id,
                "custom",
                self.setup_data['initial_time']
            )
            
            # Success embed
            embed = discord.Embed(
                title="✅ Setup Complete!",
                description="Your Wird bot has been successfully configured!",
                color=discord.Color.green()
            )
            embed.add_field(name="🌍 Timezone", value=self.setup_data['timezone'], inline=True)
            embed.add_field(name="🕐 Daily Time", value=f"{self.setup_data['initial_time_local']} ({self.setup_data['timezone']})", inline=True)
            embed.add_field(name="📺 Channel", value=f"<#{self.setup_data['channel_id']}>", inline=True)
            embed.add_field(name="📖 Mushaf", value=self.setup_data['mushaf'].title(), inline=True)
            embed.add_field(name="📄 Pages/Day", value=str(pages_per_day), inline=True)
            embed.add_field(name="🕌 Mosque ID", value=mosque_id, inline=True)
            embed.add_field(name="🔔 Notifications", value="Enabled" if self.setup_data.get('show_all_notifications', False) else "Completion Only", inline=True)
            embed.add_field(
                name="📌 Next Steps",
                value="• Use `/schedule` to add more times\n• Use `/config` to view settings\n• Pages will be sent automatically!",
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=None)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error during setup: {str(e)}", ephemeral=True)
    
    async def back(self, interaction: discord.Interaction):
        """Go back to mushaf selection"""
        view = MushafSelectView(self.guild_id, self.setup_data)
        embed = discord.Embed(
            title="⚙️ Setup Wizard - Step 4/5",
            description="**Select Mushaf Type**\n\nChoose the Mushaf (Quran) style you prefer:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)


class PagesPerDayModal(Modal):
    """Modal for setting pages per day"""
    def __init__(self, guild_id: int, setup_data: dict):
        super().__init__(title="Pages Per Day")
        self.guild_id = guild_id
        self.setup_data = setup_data
        
        self.add_item(InputText(
            label="Pages to send daily (1-20)",
            placeholder="1",
            value=str(setup_data.get('pages_per_day', 1)),
            required=True
        ))
    
    async def callback(self, interaction: discord.Interaction):
        try:
            pages = int(self.children[0].value)
            if pages < 1 or pages > 20:
                await interaction.response.send_message("❌ Pages must be between 1 and 20!", ephemeral=True)
                return
            
            self.setup_data['pages_per_day'] = pages
            
            view = FinalConfigView(self.guild_id, self.setup_data)
            
            embed = discord.Embed(
                title="⚙️ Setup Wizard - Step 5/5",
                description="**Final Configuration**\n\nReview your settings and customize additional options:",
                color=discord.Color.blue()
            )
            embed.add_field(name="🌍 Timezone", value=self.setup_data['timezone'], inline=True)
            embed.add_field(name="🕐 Initial Time", value=f"{self.setup_data['initial_time_local']} ({self.setup_data['timezone']})", inline=True)
            embed.add_field(name="📺 Channel", value=f"<#{self.setup_data['channel_id']}>", inline=True)
            embed.add_field(name="📖 Mushaf", value=self.setup_data['mushaf'].title(), inline=True)
            embed.add_field(name="📄 Pages/Day", value=str(pages), inline=True)
            
            await interaction.response.edit_message(embed=embed, view=view)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number!", ephemeral=True)


class MosqueIdModal(Modal):
    """Modal for setting mosque ID"""
    def __init__(self, guild_id: int, setup_data: dict):
        super().__init__(title="Mosque ID")
        self.guild_id = guild_id
        self.setup_data = setup_data
        
        self.add_item(InputText(
            label="Mosque ID for prayer times",
            placeholder="e.g., cio-gatineau",
            value=setup_data.get('mosque_id', 'cio-gatineau'),
            required=False
        ))
    
    async def callback(self, interaction: discord.Interaction):
        mosque_id = self.children[0].value.strip() or 'cio-gatineau'
        self.setup_data['mosque_id'] = mosque_id
        
        view = FinalConfigView(self.guild_id, self.setup_data)
        
        embed = discord.Embed(
            title="⚙️ Setup Wizard - Step 5/5",
            description="**Final Configuration**\n\nReview your settings and customize additional options:",
            color=discord.Color.blue()
        )
        embed.add_field(name="🌍 Timezone", value=self.setup_data['timezone'], inline=True)
        embed.add_field(name="🕐 Initial Time", value=f"{self.setup_data['initial_time_local']} ({self.setup_data['timezone']})", inline=True)
        embed.add_field(name="📺 Channel", value=f"<#{self.setup_data['channel_id']}>", inline=True)
        embed.add_field(name="📖 Mushaf", value=self.setup_data['mushaf'].title(), inline=True)
        embed.add_field(name="🕌 Mosque ID", value=mosque_id, inline=True)
        
        await interaction.response.edit_message(embed=embed, view=view)
