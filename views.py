import discord
from typing import Optional


class CompletionButton(discord.ui.Button):
    def __init__(self, page_number: int):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Mark as Read",
            custom_id=f"complete_{page_number}"
        )
        # Don't store page_number - we'll parse it from custom_id in callback

    async def callback(self, interaction: discord.Interaction):
        # Parse page number from custom_id
        custom_id = interaction.data.get('custom_id', '')
        try:
            page_number = int(custom_id.split('_')[1])
        except (ValueError, IndexError):
            await interaction.response.send_message("Invalid button interaction!", ephemeral=True)
            return
        
        from utils.completion import handle_completion
        await handle_completion(interaction, page_number)


class TranslationButton(discord.ui.Button):
    def __init__(self, page_number: int):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label="📖 Translate",
            custom_id=f"translate_{page_number}"
        )

    async def callback(self, interaction: discord.Interaction):
        # Parse page number from custom_id
        custom_id = interaction.data.get('custom_id', '')
        try:
            page_number = int(custom_id.split('_')[1])
        except (ValueError, IndexError):
            await interaction.response.send_message("Invalid button interaction!", ephemeral=True)
            return

        from database import db
        from utils.translation import fetch_page_translations, format_translations

        # Get user's language preference
        language = await db.get_user_language_preference(interaction.user.id, interaction.guild_id)

        # Fetch translations
        translations = await fetch_page_translations(page_number, language)
        if translations is None:
            await interaction.response.send_message("❌ Failed to fetch translations. Please try again later.", ephemeral=True)
            return

        formatted_text = await format_translations(translations)

        # Create the translation view with language switch buttons
        view = TranslationView(page_number, language)

        embed = discord.Embed(
            title=f"📖 Page {page_number} Translation",
            description=formatted_text[:4000],  # Discord embed description limit
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class TranslationView(discord.ui.View):
    def __init__(self, page_number: int, current_language: str):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.page_number = page_number
        self.current_language = current_language

        # Add language buttons
        self.add_item(LanguageButton(page_number, 'eng', 'English', current_language == 'eng'))
        self.add_item(LanguageButton(page_number, 'fra', 'Français', current_language == 'fra'))


class LanguageButton(discord.ui.Button):
    def __init__(self, page_number: int, language: str, label: str, disabled: bool = False):
        super().__init__(
            style=discord.ButtonStyle.secondary if not disabled else discord.ButtonStyle.success,
            label=label,
            disabled=disabled,
            custom_id=f"lang_{language}_{page_number}"
        )

    async def callback(self, interaction: discord.Interaction):
        # Parse language and page number from custom_id
        custom_id = interaction.data.get('custom_id', '')
        parts = custom_id.split('_')
        if len(parts) < 3:
            await interaction.response.send_message("Invalid button interaction!", ephemeral=True)
            return

        language = parts[1]
        try:
            page_number = int(parts[2])
        except ValueError:
            await interaction.response.send_message("Invalid button interaction!", ephemeral=True)
            return

        from database import db
        from utils.translation import fetch_page_translations, format_translations

        # Update user's language preference
        await db.set_user_language_preference(interaction.user.id, interaction.guild_id, language)

        # Fetch translations in new language
        translations = await fetch_page_translations(page_number, language)
        if translations is None:
            await interaction.response.send_message("❌ Failed to fetch translations. Please try again later.", ephemeral=True)
            return

        formatted_text = await format_translations(translations)

        # Update the view with new language selection
        view = TranslationView(page_number, language)

        embed = discord.Embed(
            title=f"📖 Page {page_number} Translation",
            description=formatted_text[:4000],
            color=discord.Color.blue()
        )

        await interaction.response.edit_message(embed=embed, view=view)


class PageView(discord.ui.View):
    def __init__(self, page_number: int):
        super().__init__(timeout=None)  # Views persist until bot restart
        self.add_item(CompletionButton(page_number))
        self.add_item(TranslationButton(page_number))


class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Yes, Register Me!", style=discord.ButtonStyle.success)
    async def register_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        from utils.user_management import register_user_with_role
        await register_user_with_role(interaction)

    @discord.ui.button(label="No, Thanks", style=discord.ButtonStyle.secondary)
    async def decline_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.edit_message(
            content="No problem! You can register later using `/register`.",
            view=None
        )


class SetupModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Configure Wird Bot")
        
        self.add_item(discord.ui.InputText(
            label="Mosque ID",
            placeholder="Enter your mosque ID for prayer times",
            required=True
        ))
        
        self.add_item(discord.ui.InputText(
            label="Mushaf Type",
            placeholder="e.g., madani, uthmani, indopak",
            value="madani",
            required=True
        ))
        
        self.add_item(discord.ui.InputText(
            label="Pages Per Day",
            placeholder="How many pages to send daily (1-20)",
            value="1",
            required=True
        ))
        
        self.add_item(discord.ui.InputText(
            label="Channel ID",
            placeholder="Channel ID where pages will be sent",
            required=True
        ))

    async def callback(self, interaction: discord.Interaction):
        from .utils.config import handle_setup
        await handle_setup(interaction, self.children)


class ScheduleTimeModal(discord.ui.Modal):
    def __init__(self, guild_id: int):
        super().__init__(title="Add Custom Time")
        self.guild_id = guild_id
        
        self.add_item(discord.ui.InputText(
            label="Time (in your timezone)",
            placeholder="e.g., 8:00 AM, 14:30, or 2:30 PM",
            required=True
        ))

    async def callback(self, interaction: discord.Interaction):
        from database import db
        import pytz
        from datetime import datetime
        
        try:
            # Get guild timezone
            guild_config = await db.get_guild_config(self.guild_id)
            timezone = guild_config.get('timezone', 'UTC') if guild_config else 'UTC'
            
            time_input = self.children[0].value.strip()
            
            # Parse time input (support multiple formats)
            time_input_upper = time_input.upper().replace(' ', '')
            
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
            
            if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                await interaction.response.send_message("Invalid time format!", ephemeral=True)
                return
            
            # Convert to UTC
            tz = pytz.timezone(timezone)
            local_time = datetime.now(tz).replace(hour=hours, minute=minutes, second=0, microsecond=0)
            utc_time = local_time.astimezone(pytz.UTC)
            
            time_value = f"{utc_time.hour:02d}:{utc_time.minute:02d}"
            
            await db.add_scheduled_time(self.guild_id, "custom", time_value)
            
            # Refresh the schedule view
            from cogs.schedule_views import ScheduleMainView
            view = ScheduleMainView(self.guild_id)
            await view.setup_items()
            embed = await view.create_embed()
            await interaction.response.edit_message(embed=embed, view=view)
        except ValueError:
            await interaction.response.send_message("Invalid time format! Use HH:MM (e.g., 14:30) or 12-hour (e.g., 8:00 AM)", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)
        # ...existing code...


class ResetConfirmationView(discord.ui.View):
    def __init__(self, guild_id: int, bot):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.bot = bot

    @discord.ui.button(label="Yes, Reset Everything", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_reset(self, button: discord.ui.Button, interaction: discord.Interaction):
        # Disable buttons to prevent double-clicks
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            from database import db
            await db.reset_guild_data(self.guild_id)
            
            embed = discord.Embed(
                title="🗑️ Server Data Reset Complete",
                description="All Wird bot data for this server has been permanently deleted:\n\n"
                            "• Guild configuration\n"
                            "• User registrations and streaks\n"
                            "• Completion records\n"
                            "• Scheduled times\n"
                            "• Daily sessions\n\n"
                            "The bot is now unconfigured. Use `/setup` to start fresh.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed, view=None)
        except Exception as e:
            await interaction.edit_original_response(
                content=f"❌ Error during reset: {str(e)}",
                embed=None,
                view=None
            )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel_reset(self, button: discord.ui.Button, interaction: discord.Interaction):
        embed = discord.Embed(
            title="✅ Reset Cancelled",
            description="Server data has not been modified.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)

