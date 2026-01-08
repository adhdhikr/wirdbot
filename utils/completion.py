import discord
from database import db
from views import RegistrationView
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


async def handle_completion(interaction: discord.Interaction, page_number: int):
    guild_config = await db.get_guild_config(interaction.guild_id)
    if not guild_config:
        await interaction.response.send_message("Server not configured!", ephemeral=True)
        return
    
    user = await db.get_user(interaction.user.id, interaction.guild_id)
    
    if not user or not user['registered']:
        from views import RegistrationView
        view = RegistrationView()
        await interaction.response.send_message(
            "👋 Welcome! Would you like to register for daily Wird tracking?",
            view=view,
            ephemeral=True
        )
        return
    
    today = datetime.utcnow().strftime("%Y-%m-%d")
    completions = await db.get_user_completions_for_date(interaction.user.id, interaction.guild_id, today)
    
    if page_number in completions:
        if guild_config.get('show_all_notifications', False):
            await interaction.response.send_message("✅ You already marked this page as read!", ephemeral=True)
        return
    
    await db.mark_page_complete(interaction.user.id, interaction.guild_id, page_number, today)
    completions.append(page_number)

    session = await db.get_today_session(interaction.guild_id, today)
    total_pages = session['end_page'] - session['start_page'] + 1 if session else 1

    # Edit the original message to show it's been marked as read
    try:
        original_content = interaction.message.content
        if "✅" not in original_content:
            await interaction.message.edit(content=f"✅ {original_content}")
    except:
        pass  # If we can't edit, that's okay

    from utils.followup import send_followup_message
    if len(completions) >= total_pages:
        # Only now update the streak
        current_streak = await calculate_streak(user, today)
        await db.update_streak(interaction.user.id, interaction.guild_id, current_streak, today)

        if guild_config.get('show_all_notifications', False):
            streak_line = f"🔥 Current streak: {current_streak} days" if current_streak > 1 else ""
            await interaction.response.send_message(
                f"✅ Page {page_number} marked as complete!\n"
                f"🎉 You've completed all pages for today!\n"
                f"{streak_line}",
                ephemeral=True
            )
        else:
            # When notifications disabled, only show completion celebration
            streak_line = f"🔥 Current streak: {current_streak} days" if current_streak > 1 else ""
            await interaction.response.send_message(
                f"🎉 You've completed all pages for today!\n"
                f"{streak_line}",
                ephemeral=True
            )

        if guild_config['followup_on_completion']:
            # Send a simple followup message: "x completed the wird (+ streak if there is)"
            channel_id = guild_config.get('followup_channel_id') or guild_config.get('channel_id')
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                streak_text = f" (+{current_streak}🔥)" if current_streak > 1 else ""
                await channel.send(f"✅ {interaction.user.mention} completed the wird{streak_text}")
    else:
        # Don't update streak if not all pages are done
        if guild_config.get('show_all_notifications', False):
            await interaction.response.send_message(
                f"✅ Page {page_number} marked as complete!\n"
                f"📖 Progress: {len(completions)}/{total_pages} pages",
                ephemeral=True
            )
    # Always update the summary embed (progress message) when a user completes all their pages for the day
    await send_followup_message(interaction.guild_id, interaction.client)


async def calculate_streak(user: dict, today: str) -> int:
    if user['last_completion_date'] == today:
        return user['current_streak']
    
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    if user['last_completion_date'] == yesterday:
        return user['current_streak'] + 1
    else:
        return 1
