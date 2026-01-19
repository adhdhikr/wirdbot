import discord
from database import db
from views import RegistrationView
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


async def handle_completion(interaction: discord.Interaction, page_number: int):
    guild_config = await db.get_guild_config(interaction.guild_id)
    if not guild_config:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("Server not configured!", ephemeral=True)
        return
    
    user = await db.get_user(interaction.user.id, interaction.guild_id)
    
    if not user or not user['registered']:
        await interaction.response.defer(ephemeral=True)
        from views import RegistrationView
        view = RegistrationView()
        await interaction.followup.send(
            "👋 Welcome! Would you like to register for daily Wird tracking?",
            view=view,
            ephemeral=True
        )
        return
    
    # Get the current active session (most recent session)
    active_session = await db.get_current_active_session(interaction.guild_id)
    
    if not active_session:
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("❌ No active session found!", ephemeral=True)
        return
    
    # Check if page belongs to active session OR a previous session (late completion)
    is_late = False
    target_session = active_session
    
    if page_number < active_session['start_page'] or page_number > active_session['end_page']:
        # Check if it belongs to a previous session
        previous_session = await db.get_session_for_page(interaction.guild_id, page_number)
        if previous_session and previous_session['id'] != active_session['id']:
            target_session = previous_session
            is_late = True
        else:
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send(
                f"❌ Page {page_number} is not part of any valid session!",
                ephemeral=True
            )
            return
    
    # Check if already completed
    today = datetime.utcnow().strftime("%Y-%m-%d")
    completions = await db.get_user_completions_for_session(interaction.user.id, target_session['id'])
    
    if page_number in completions:
        if guild_config.get('show_all_notifications', False):
            await interaction.response.defer(ephemeral=True)
            await interaction.followup.send("✅ You already marked this page as read!", ephemeral=True)
        else:
            await interaction.response.defer(ephemeral=True)
        return
    
    # Mark completion with session_id and late flag
    await db.mark_page_complete(
        interaction.user.id, 
        interaction.guild_id, 
        page_number, 
        today,
        session_id=target_session['id'], 
        is_late=is_late
    )
    completions.append(page_number)

    # Edit the original message to show it's been marked as read
    try:
        original_content = interaction.message.content
        if "✅" not in original_content:
            late_marker = " ⏰" if is_late else ""
            await interaction.message.edit(content=f"✅{late_marker} {original_content}")
    except:
        pass  # If we can't edit, that's okay

    total_pages = target_session['end_page'] - target_session['start_page'] + 1

    from utils.followup import send_followup_message
    if len(completions) >= total_pages:
        # Session complete!
        await db.mark_session_completed(target_session['id'])
        
        # Only update streak if completing current session on time (not late)
        if not is_late and target_session['id'] == active_session['id']:
            current_streak = await calculate_session_streak(user, interaction.guild_id, active_session['id'])
            await db.update_session_streak(interaction.user.id, interaction.guild_id, current_streak)
        else:
            current_streak = user.get('session_streak', 0)

        if guild_config.get('show_all_notifications', False):
            await interaction.response.defer(ephemeral=True)
            late_text = " (Completed Late)" if is_late else ""
            streak_line = f"🔥 Current streak: {current_streak} sessions" if current_streak > 1 and not is_late else ""
            await interaction.followup.send(
                f"✅ Page {page_number} marked as complete!{late_text}\n"
                f"🎉 You've completed all pages for this session!\n"
                f"{streak_line}",
                ephemeral=True
            )
        else:
            await interaction.response.defer(ephemeral=True)

        if guild_config['followup_on_completion'] and not is_late:
            # Send a simple followup message for on-time completions
            channel_id = guild_config.get('followup_channel_id') or guild_config.get('channel_id')
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                streak_text = f" (+{current_streak}🔥)" if current_streak > 1 else ""
                await channel.send(f"✅ {interaction.user.display_name} completed the wird{streak_text}")
    else:
        # Partial completion
        if guild_config.get('show_all_notifications', False):
            await interaction.response.defer(ephemeral=True)
            late_text = " (Late)" if is_late else ""
            await interaction.followup.send(
                f"✅ Page {page_number} marked as complete!{late_text}\n"
                f"📖 Progress: {len(completions)}/{total_pages} pages",
                ephemeral=True
            )
        else:
            await interaction.response.defer(ephemeral=True)
    
    # Always update the summary embed (progress message)
    await send_followup_message(interaction.guild_id, interaction.client)


async def calculate_session_streak(user: dict, guild_id: int, current_session_id: int) -> int:
    """
    Calculate streak based on consecutive completed sessions.
    A session must be completed to count toward the streak.
    """
    # Get all completed sessions for this guild, ordered by creation date
    all_sessions = await db.get_completed_sessions_for_guild(guild_id)
    
    # Get user's completed session IDs
    user_completed_sessions = await db.get_user_session_completions(user['user_id'], guild_id)
    
    # Calculate consecutive sessions completed (working backwards from most recent)
    streak = 0
    for session in reversed(all_sessions):
        if session['id'] in user_completed_sessions:
            streak += 1
        else:
            break  # Streak broken
    
    return max(streak, 1)  # Minimum streak is 1 when completing a session
