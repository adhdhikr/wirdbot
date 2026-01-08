# At the end of the file, add the setup function for extension loading

def setup(bot):
    pass
import discord
from discord.ui import View, Button, Select
from database import Database
from typing import List, Dict, Any


class ScheduleMainView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.selected_schedule_id = None
        
    async def create_embed(self) -> discord.Embed:
        from main import db
        # ... code...
        
        scheduled_times = await db.get_scheduled_times(self.guild_id)
        guild_config = await db.get_guild_config(self.guild_id)
        timezone = guild_config.get('timezone', 'UTC') if guild_config else 'UTC'
        
        import pytz
        from datetime import datetime
        
        embed = discord.Embed(
            title="⏰ Schedule Management",
            description=f"Manage when pages are sent daily\n**Timezone:** {timezone}",
            color=discord.Color.blue()
        )
        
        if scheduled_times:
            times_list = []
            for st in scheduled_times:
                if st['time_type'] == 'custom':
                    # Convert UTC to local timezone
                    utc_time = datetime.strptime(st['time_value'], '%H:%M').replace(tzinfo=pytz.UTC)
                    local_tz = pytz.timezone(timezone)
                    local_time = utc_time.astimezone(local_tz)
                    # Format with hour without leading zero but keep minutes with leading zero
                    formatted_time = local_time.strftime('%I:%M %p')
                    if formatted_time[0] == '0':
                        formatted_time = formatted_time[1:]
                    times_list.append(f"🕐 **ID {st['id']}**: {formatted_time} ({timezone})")
                else:
                    times_list.append(f"🕌 **ID {st['id']}**: {st['time_type'].title()} prayer")
            
            embed.add_field(
                name=f"📋 Active Schedules ({len(scheduled_times)})",
                value="\n".join(times_list),
                inline=False
            )
        else:
            embed.add_field(
                name="📋 No Schedules",
                value="Click **Add Schedule** to create your first scheduled time!",
                inline=False
            )
        
        # Show current time in their timezone
        tz = pytz.timezone(timezone)
        current_time = datetime.now(tz).strftime('%I:%M %p')
        footer_text = f"Current time: {current_time} • Select schedule to delete • Click + to add"
        if scheduled_times and len(scheduled_times) > 1:
            footer_text += "\n⚠️ Multiple schedules per day are supported, but progress tracking for this is still a work in progress and will be added later."
        embed.set_footer(text=footer_text)
        return embed


    async def refresh_view(self, interaction: discord.Interaction):
        """Refresh the view with updated buttons and dropdown"""
        self.clear_items()
        await self.setup_items()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def setup_items(self):
        """Setup all buttons and dropdowns"""
        from main import db
        # ...existing code...
        
        scheduled_times = await db.get_scheduled_times(self.guild_id)
        
        # Add dropdown if there are schedules
        if scheduled_times:
            options = []
            for st in scheduled_times:
                if st['time_type'] == 'custom':
                    label = f"Custom: {st['time_value']} UTC"
                    emoji = "🕐"
                else:
                    label = f"{st['time_type'].title()} Prayer"
                    emoji = "🕌"
                
                options.append(discord.SelectOption(
                    label=label,
                    value=str(st['id']),
                    emoji=emoji,
                    description=f"ID: {st['id']}"
                ))
            
            select = Select(
                placeholder="Select a schedule to manage...",
                options=options,
                custom_id="schedule_select"
            )
            select.callback = self.schedule_selected
            self.add_item(select)
        
        # Add action buttons
        add_button = Button(
            label="Add Schedule",
            style=discord.ButtonStyle.success,
            emoji="➕",
            custom_id="add_schedule"
        )
        add_button.callback = self.add_schedule
        self.add_item(add_button)
        
        # Delete button (only if schedule is selected)
        if self.selected_schedule_id:
            delete_button = Button(
                label="Delete Selected",
                style=discord.ButtonStyle.danger,
                emoji="🗑️",
                custom_id="delete_schedule"
            )
            delete_button.callback = self.delete_schedule
            self.add_item(delete_button)
        
        # Clear all button (only if schedules exist)
        if scheduled_times:
            clear_button = Button(
                label="Clear All",
                style=discord.ButtonStyle.danger,
                    emoji="🗑️",
                    custom_id="clear_all"
                )
            clear_button.callback = self.clear_all
            self.add_item(clear_button)

    async def schedule_selected(self, interaction: discord.Interaction):
        """Handle schedule selection from dropdown"""
        self.selected_schedule_id = int(interaction.data['values'][0])
        await self.refresh_view(interaction)

    async def add_schedule(self, interaction: discord.Interaction):
        """Show add schedule type selection"""
        view = AddScheduleTypeView(self.guild_id)
        embed = discord.Embed(
            title="➕ Add Schedule",
            description="Choose the type of schedule to add:",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def delete_schedule(self, interaction: discord.Interaction):
        """Delete the selected schedule"""
        if not self.selected_schedule_id:
            await interaction.response.send_message("No schedule selected!", ephemeral=True)
            return
        
        from main import db
        
        await db.remove_scheduled_time(self.selected_schedule_id)
        self.selected_schedule_id = None
        await self.refresh_view(interaction)


    async def clear_all(self, interaction: discord.Interaction):
        """Clear all schedules"""
        from main import db
        # ...existing code...
        
        await db.clear_scheduled_times(self.guild_id)
        self.selected_schedule_id = None
        await self.refresh_view(interaction)



class AddScheduleTypeView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        
        # Prayer time button
        prayer_button = Button(
            label="Prayer Time",
            style=discord.ButtonStyle.primary,
            emoji="🕌",
            custom_id="prayer_time"
        )
        prayer_button.callback = self.prayer_time_selected
        self.add_item(prayer_button)
        
        # Custom time button
        custom_button = Button(
            label="Custom Time",
            style=discord.ButtonStyle.primary,
            emoji="🕐",
            custom_id="custom_time"
        )
        custom_button.callback = self.custom_time_selected
        self.add_item(custom_button)
        
        # Back button
        back_button = Button(
            label="Back",
            style=discord.ButtonStyle.secondary,
            emoji="◀️",
            custom_id="back"
        )
        back_button.callback = self.back
        self.add_item(back_button)

    async def prayer_time_selected(self, interaction: discord.Interaction):
        """Show prayer time selection"""
        view = PrayerTimeSelectView(self.guild_id)
        embed = discord.Embed(
            title="🕌 Select Prayer Time",
            description="Choose which prayer time to add to the schedule:",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=view)

    async def custom_time_selected(self, interaction: discord.Interaction):
        """Show custom time modal"""
        from views import ScheduleTimeModal
        modal = ScheduleTimeModal(self.guild_id)
        await interaction.response.send_modal(modal)

    async def back(self, interaction: discord.Interaction):
        """Go back to main schedule view"""
        view = ScheduleMainView(self.guild_id)
        await view.setup_items()
        embed = await view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PrayerTimeSelectView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        
        # Prayer selection dropdown
        prayers = [
            ("Fajr", "fajr", "🌅"),
            ("Dhuhr", "dhuhr", "☀️"),
            ("Asr", "asr", "🌤️"),
            ("Maghrib", "maghrib", "🌆"),
            ("Isha", "isha", "🌙")
        ]
        
        options = [
            discord.SelectOption(label=name, value=value, emoji=emoji)
            for name, value, emoji in prayers
        ]
        
        select = Select(
            placeholder="Select a prayer time...",
            options=options,
            custom_id="prayer_select"
        )
        select.callback = self.prayer_selected
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

    async def prayer_selected(self, interaction: discord.Interaction):
        """Add the selected prayer time"""
        prayer = interaction.data['values'][0]
        
        from main import db
        
        await db.add_scheduled_time(self.guild_id, prayer)
        
        # Go back to main view
        view = ScheduleMainView(self.guild_id)
        await view.setup_items()
        embed = await view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)


    async def back(self, interaction: discord.Interaction):
        """Go back to add type selection"""
        view = AddScheduleTypeView(self.guild_id)
        embed = discord.Embed(
            title="➕ Add Schedule",
            description="Choose the type of schedule to add:",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=view)
