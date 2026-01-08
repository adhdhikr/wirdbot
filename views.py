import discord
from typing import Optional


class CompletionButton(discord.ui.Button):
    def __init__(self, page_number: int):
        super().__init__(
            style=discord.ButtonStyle.success,
            label="Mark as Read",
            custom_id=f"complete_{page_number}"
        )
        self.page_number = page_number

    async def callback(self, interaction: discord.Interaction):
        from .utils.completion import handle_completion
        await handle_completion(interaction, self.page_number)


class PageView(discord.ui.View):
    def __init__(self, page_number: int):
        super().__init__(timeout=None)
        self.add_item(CompletionButton(page_number))


class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Yes, Register Me!", style=discord.ButtonStyle.success)
    async def register_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        from .utils.user_management import register_user_with_role
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
    def __init__(self):
        super().__init__(title="Add Scheduled Time")
        
        self.add_item(discord.ui.InputText(
            label="Time (HH:MM in UTC)",
            placeholder="e.g., 14:30 for 2:30 PM UTC",
            required=True
        ))

    async def callback(self, interaction: discord.Interaction):
        from .utils.scheduler import handle_schedule_time
        await handle_schedule_time(interaction, self.children[0].value)
