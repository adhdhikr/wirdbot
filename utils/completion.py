import logging
from datetime import datetime

import nextcord as discord

from database import db

logger = logging.getLogger(__name__)


async def handle_completion(interaction: discord.Interaction, page_number: int):

    await interaction.response.defer(ephemeral=True)
    
    guild_config = await db.get_guild_config(interaction.guild_id)
    if not guild_config:
        await interaction.followup.send("Server not configured!", ephemeral=True)
        return
    
    user = await db.get_user(interaction.user.id, interaction.guild_id)
    
    if not user or not user['registered']:
        from views import RegistrationView
        view = RegistrationView()
        await interaction.followup.send(
            "👋 Welcome! Would you like to register for daily Wird tracking?",
            view=view,
            ephemeral=True
        )
        return
    

    active_session = await db.get_current_active_session(interaction.guild_id)
    
    if not active_session:
        await interaction.followup.send("❌ No active session found!", ephemeral=True)
        return
    

    is_late = False
    target_session = active_session
    
    if page_number < active_session['start_page'] or page_number > active_session['end_page']:

        previous_session = await db.get_session_for_page(interaction.guild_id, page_number)
        if previous_session and previous_session['id'] != active_session['id']:
            target_session = previous_session


            is_late = target_session['created_at'] < active_session['created_at']
        else:
            await interaction.followup.send(
                f"❌ Page {page_number} is not part of any valid session!",
                ephemeral=True
            )
            return

    

    today = datetime.utcnow().strftime("%Y-%m-%d")
    completions = await db.get_user_completions_for_session(interaction.user.id, target_session['id'])
    
    if page_number in completions:
        if guild_config.get('show_all_notifications', False):
            await interaction.followup.send("✅ You already marked this page as read!", ephemeral=True)

        return
    

    await db.mark_page_complete(
        interaction.user.id, 
        interaction.guild_id, 
        page_number, 
        today,
        session_id=target_session['id'], 
        is_late=is_late
    )
    completions.append(page_number)


    total_pages = target_session['end_page'] - target_session['start_page'] + 1

    from utils.followup import send_followup_message
    if len(completions) >= total_pages:

        await db.mark_session_completed(target_session['id'])
        

        if target_session['id'] == active_session['id']:
             current_streak = await update_streak_incrementally(user, interaction.guild_id, active_session['id'], is_late)
        else:
             current_streak = await update_streak_incrementally(user, interaction.guild_id, target_session['id'], is_late)

        if guild_config.get('show_all_notifications', False):
            late_text = " (Completed Late)" if is_late else ""
            streak_emoji = user.get('streak_emoji') or "🔥"
            streak_line = f"{streak_emoji} Current streak: {current_streak} sessions" if current_streak > 1 and not is_late else ""
            await interaction.followup.send(
                f"✅ Page {page_number} marked as complete!{late_text}\n"
                f"🎉 You've completed all pages for this session!\n"
                f"{streak_line}",
                ephemeral=True
            )


        if guild_config['followup_on_completion'] and not is_late:

            channel_id = guild_config.get('followup_channel_id') or guild_config.get('channel_id')
            channel = interaction.guild.get_channel(channel_id)
            if channel:
                streak_emoji = user.get('streak_emoji') or "🔥"
                streak_text = f" (+{current_streak}{streak_emoji})" if current_streak > 1 else ""
                await channel.send(f"✅ {interaction.user.mention} completed the wird{streak_text}")
    else:

        if guild_config.get('show_all_notifications', False):
            late_text = " (Late)" if is_late else ""
            await interaction.followup.send(
                f"✅ Page {page_number} marked as complete!{late_text}\n"
                f"📖 Progress: {len(completions)}/{total_pages} pages",
                ephemeral=True
            )

    


    await send_followup_message(interaction.guild_id, interaction.client, session_id=target_session['id'])


async def update_streak_incrementally(user: dict, guild_id: int, current_session_id: int, is_late: bool):
    """
    Update streak incrementally O(1).
    - If completing late: Streak does not change.
    - If completing on time:
      - Check if previous session (N-1) was completed ON TIME.
      - If yes: New Streak = User's Stored Streak + 1.
      - If no: New Streak = 1.
    """
    if is_late:
        return user.get('session_streak', 0)


    previous_session = await db.get_previous_session(guild_id, current_session_id)
    
    new_streak = 1
    
    if previous_session:

        status = await db.get_session_completion_status(user['user_id'], previous_session['id'])
        
        if status and not status['is_late']:

            current_stored = user.get('session_streak', 0)
            new_streak = current_stored + 1
        else:

            new_streak = 1
    else:

        new_streak = 1
        

    await db.update_session_streak(user['user_id'], guild_id, new_streak)
    return new_streak
