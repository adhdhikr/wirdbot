import discord
from typing import Optional, List


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

        from utils.interaction_handlers import handle_translation
        await handle_translation(interaction, page_number)


class TafsirButton(discord.ui.Button):
    def __init__(self, page_number: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="📚 Tafsir",
            custom_id=f"tafsir_{page_number}"
        )

    async def callback(self, interaction: discord.Interaction):
        # Parse page number from custom_id
        custom_id = interaction.data.get('custom_id', '')
        try:
            page_number = int(custom_id.split('_')[1])
        except (ValueError, IndexError):
            await interaction.response.send_message("Invalid button interaction!", ephemeral=True)
            return

        from utils.interaction_handlers import handle_tafsir
        await handle_tafsir(interaction, page_number)


class TafsirView(discord.ui.View):
    def __init__(self, page_number: int, current_edition: str, pages: List[str], current_page: int = 0, ayah_count: int = 0):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.page_number = page_number
        self.current_edition = current_edition
        self.pages = pages
        self.current_page = current_page
        self.ayah_count = ayah_count

        # Add tafsir edition select
        self.add_item(TafsirSelect(page_number, current_edition))

        # Add pagination buttons if multiple pages
        if len(pages) > 1:
            self.add_item(TafsirPrevButton(page_number, current_edition, pages, current_page, ayah_count))
            self.add_item(TafsirNextButton(page_number, current_edition, pages, current_page, ayah_count))


class TafsirSelect(discord.ui.Select):
    def __init__(self, page_number: int, current_edition: str):
        from utils.tafsir import TAFSIR_EDITIONS

        options = []
        for edition_key, display_name in TAFSIR_EDITIONS.items():
            options.append(discord.SelectOption(
                label=display_name,
                value=edition_key,
                default=(edition_key == current_edition)
            ))

        super().__init__(
            placeholder="Choose Tafsir Edition...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"tafsir_select_{page_number}"
        )

    async def callback(self, interaction: discord.Interaction):
        # Parse page number from custom_id
        custom_id = interaction.data.get('custom_id', '')
        try:
            page_number = int(custom_id.split('_')[2])
        except (ValueError, IndexError):
            await interaction.response.send_message("Invalid select interaction!", ephemeral=True)
            return

        selected_edition = self.values[0]

        from database import db
        from utils.tafsir import fetch_page_tafsir, format_tafsir
        from utils.pagination import paginate_text

        # Update user's tafsir preference
        await db.set_user_tafsir_preference(interaction.user.id, interaction.guild_id, selected_edition)

        # Fetch tafsir in new edition
        tafsir_data = await fetch_page_tafsir(page_number, selected_edition)
        if tafsir_data is None:
            await interaction.response.send_message("❌ Failed to fetch tafsir. Please try again later.", ephemeral=True)
            return

        formatted_text = await format_tafsir(tafsir_data)
        pages = paginate_text(formatted_text)

        # Update the view with new edition selection
        view = TafsirView(page_number, selected_edition, pages, 0, len(tafsir_data))

        embed = discord.Embed(
            title=f"📚 Page {page_number} Tafsir ({len(tafsir_data)} ayahs)",
            description=pages[0],
            color=discord.Color.green()
        )
        if len(pages) > 1:
            embed.set_footer(text=f"Page 1 of {len(pages)}")

        await interaction.response.edit_message(embed=embed, view=view)


class TafsirPrevButton(discord.ui.Button):
    def __init__(self, page_number: int, current_edition: str, pages: List[str], current_page: int, ayah_count: int):
        disabled = (current_page == 0)
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="◀ Prev",
            disabled=disabled,
            custom_id=f"tafsir_prev_{page_number}_{current_edition}_{current_page}"
        )
        self.page_number = page_number
        self.current_edition = current_edition
        self.pages = pages
        self.current_page = current_page
        self.ayah_count = ayah_count

    async def callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            new_page = self.current_page - 1
            view = TafsirView(self.page_number, self.current_edition, self.pages, new_page, self.ayah_count)

            embed = discord.Embed(
                title=f"📚 Page {self.page_number} Tafsir ({self.ayah_count} ayahs)",
                description=self.pages[new_page],
                color=discord.Color.green()
            )
            if len(self.pages) > 1:
                embed.set_footer(text=f"Page {new_page + 1} of {len(self.pages)}")

            await interaction.response.edit_message(embed=embed, view=view)


class TafsirNextButton(discord.ui.Button):
    def __init__(self, page_number: int, current_edition: str, pages: List[str], current_page: int, ayah_count: int):
        disabled = (current_page == len(pages) - 1)
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Next ▶",
            disabled=disabled,
            custom_id=f"tafsir_next_{page_number}_{current_edition}_{current_page}"
        )
        self.page_number = page_number
        self.current_edition = current_edition
        self.pages = pages
        self.current_page = current_page
        self.ayah_count = ayah_count

    async def callback(self, interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            new_page = self.current_page + 1
            view = TafsirView(self.page_number, self.current_edition, self.pages, new_page, self.ayah_count)

            embed = discord.Embed(
                title=f"📚 Page {self.page_number} Tafsir ({self.ayah_count} ayahs)",
                description=self.pages[new_page],
                color=discord.Color.green()
            )
            if len(self.pages) > 1:
                embed.set_footer(text=f"Page {new_page + 1} of {len(self.pages)}")

            await interaction.response.edit_message(embed=embed, view=view)


class TranslationView(discord.ui.View):
    def __init__(self, page_number: int, current_language: str, pages: List[str], current_page: int = 0):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.page_number = page_number
        self.current_language = current_language
        self.pages = pages
        self.current_page = current_page

        # Add language buttons
        self.add_item(LanguageButton(page_number, 'eng', 'English', current_language == 'eng'))
        self.add_item(LanguageButton(page_number, 'fra', 'Français', current_language == 'fra'))

        # Add pagination buttons if multiple pages
        if len(pages) > 1:
            self.add_item(TranslationPrevButton(page_number, current_language, pages, current_page))
            self.add_item(TranslationNextButton(page_number, current_language, pages, current_page))


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
        from utils.pagination import paginate_text

        # Update user's language preference
        await db.set_user_language_preference(interaction.user.id, interaction.guild_id, language)

        # Fetch translations in new language
        translations = await fetch_page_translations(page_number, language)
        if translations is None:
            await interaction.response.send_message("❌ Failed to fetch translations. Please try again later.", ephemeral=True)
            return

        formatted_text = await format_translations(translations)
        pages = paginate_text(formatted_text)

        # Update the view with new language selection
        view = TranslationView(page_number, language, pages, 0)

        embed = discord.Embed(
            title=f"📖 Page {page_number} Translation",
            description=pages[0],
            color=discord.Color.blue()
        )
        if len(pages) > 1:
            embed.set_footer(text=f"Page 1 of {len(pages)}")

        await interaction.response.edit_message(embed=embed, view=view)

class TranslationPrevButton(discord.ui.Button):
    def __init__(self, page_number: int, current_language: str, pages: List[str], current_page: int):
        disabled = (current_page == 0)
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="◀ Prev",
            disabled=disabled,
            custom_id=f"trans_prev_{page_number}_{current_language}_{current_page}"
        )
        self.page_number = page_number
        self.current_language = current_language
        self.pages = pages
        self.current_page = current_page

    async def callback(self, interaction: discord.Interaction):
        if self.current_page > 0:
            new_page = self.current_page - 1
            view = TranslationView(self.page_number, self.current_language, self.pages, new_page)

            embed = discord.Embed(
                title=f"📖 Page {self.page_number} Translation",
                description=self.pages[new_page],
                color=discord.Color.blue()
            )
            if len(self.pages) > 1:
                embed.set_footer(text=f"Page {new_page + 1} of {len(self.pages)}")

            await interaction.response.edit_message(embed=embed, view=view)


class TranslationNextButton(discord.ui.Button):
    def __init__(self, page_number: int, current_language: str, pages: List[str], current_page: int):
        disabled = (current_page == len(pages) - 1)
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Next ▶",
            disabled=disabled,
            custom_id=f"trans_next_{page_number}_{current_language}_{current_page}"
        )
        self.page_number = page_number
        self.current_language = current_language
        self.pages = pages
        self.current_page = current_page

    async def callback(self, interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            new_page = self.current_page + 1
            view = TranslationView(self.page_number, self.current_language, self.pages, new_page)

            embed = discord.Embed(
                title=f"📖 Page {self.page_number} Translation",
                description=self.pages[new_page],
                color=discord.Color.blue()
            )
            if len(self.pages) > 1:
                embed.set_footer(text=f"Page {new_page + 1} of {len(self.pages)}")

            await interaction.response.edit_message(embed=embed, view=view)

class PageView(discord.ui.View):
    def __init__(self, page_number: int):
        super().__init__(timeout=None)  # Views persist until bot restart
        self.add_item(CompletionButton(page_number))
        self.add_item(TranslationButton(page_number))
        self.add_item(TafsirButton(page_number))


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


class PaginatedView(discord.ui.View):
    def __init__(self, pages: List[str], title: str, color: discord.Color, current_page: int = 0):
        super().__init__(timeout=300)
        self.pages = pages
        self.title = title
        self.color = color
        self.current_page = current_page
        self.update_buttons()

    def update_buttons(self):
        # Clear existing items
        self.clear_items()

        # Previous button
        prev_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="◀ Previous",
            disabled=(self.current_page == 0)
        )
        prev_button.callback = self.previous_page
        self.add_item(prev_button)

        # Page indicator
        page_indicator = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label=f"Page {self.current_page + 1}/{len(self.pages)}",
            disabled=True
        )
        self.add_item(page_indicator)

        # Next button
        next_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="Next ▶",
            disabled=(self.current_page == len(self.pages) - 1)
        )
        next_button.callback = self.next_page
        self.add_item(next_button)

    async def previous_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()

            embed = discord.Embed(
                title=self.title,
                description=self.pages[self.current_page],
                color=self.color
            )
            embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)}")

            await interaction.response.edit_message(embed=embed, view=self)

    async def next_page(self, interaction: discord.Interaction):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()

            embed = discord.Embed(
                title=self.title,
                description=self.pages[self.current_page],
                color=self.color
            )
            embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.pages)}")

            await interaction.response.edit_message(embed=embed, view=self)

