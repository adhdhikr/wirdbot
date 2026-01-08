import discord
from database import Database
from views import RegistrationView
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


async def handle_completion(interaction: discord.Interaction, page_number: int):
    db = Database()
    await db.connect()
    
    try:
        guild_config = await db.get_guild_config(interaction.guild_id)
        if not guild_config:
            await interaction.response.send_message("Server not configured!", ephemeral=True)
            return
        
        user = await db.get_user(interaction.user.id, interaction.guild_id)
        
        if not user:
            view = RegistrationView()
            await interaction.response.send_message(
                "👋 Welcome! Would you like to register for daily Wird tracking?",
                view=view,
                ephemeral=True
            )
            return
        
        if not user['registered']:
            await interaction.response.send_message("You are not registered for Wird tracking!", ephemeral=True)
            return
        
        today = datetime.utcnow().strftime("%Y-%m-%d")
        completions = await db.get_user_completions_for_date(interaction.user.id, interaction.guild_id, today)
        
        if page_number in completions:
            await interaction.response.send_message("✅ You already marked this page as read!", ephemeral=True)
            return
        
        await db.mark_page_complete(interaction.user.id, interaction.guild_id, page_number, today)
        completions.append(page_number)
        
        current_streak = await calculate_streak(db, user, today)
        await db.update_streak(interaction.user.id, interaction.guild_id, current_streak, today)
        
        session = await db.get_today_session(interaction.guild_id, today)
        total_pages = session['end_page'] - session['start_page'] + 1 if session else 1
        
        if len(completions) >= total_pages:
            await interaction.response.send_message(
                f"✅ Page {page_number} marked as complete!\n"
                f"🎉 You've completed all pages for today!\n"
                f"🔥 Current streak: {current_streak} days",
                ephemeral=True
            )
            
            if guild_config['followup_on_completion']:
                from .followup import send_followup_message
                await send_followup_message(interaction.guild_id, interaction.client)
        else:
            await interaction.response.send_message(
                f"✅ Page {page_number} marked as complete!\n"
                f"📖 Progress: {len(completions)}/{total_pages} pages\n"
                f"🔥 Current streak: {current_streak} days",
                ephemeral=True
            )
    finally:
        await db.close()


async def calculate_streak(db: Database, user: dict, today: str) -> int:
    if user['last_completion_date'] == today:
        return user['current_streak']
    
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    if user['last_completion_date'] == yesterday:
        return user['current_streak'] + 1
    else:
        return 1
