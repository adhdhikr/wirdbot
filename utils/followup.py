import discord
from database import db
import logging

logger = logging.getLogger(__name__)


async def send_followup_message(guild_id: int, bot, session_id: int = None):
    """
    Send or update the progress summary message for a session.
    If session_id is None, uses the current active session.
    """
    
    try:
        guild_config = await db.get_guild_config(guild_id)
        if not guild_config:
            return
        
        guild = bot.get_guild(guild_id)
        if not guild:
            return
        
        followup_channel_id = guild_config['followup_channel_id'] or guild_config['channel_id']
        channel = guild.get_channel(followup_channel_id)
        if not channel:
            return

        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")

        registered_users = await db.get_registered_users(guild_id)

        # Get the session to update (either specified or current active)
        if session_id:
            session = await db.get_session_by_id(session_id)
        else:
            session = await db.get_current_active_session(guild_id)
        
        if not session:
            return

        total_pages = session['end_page'] - session['start_page'] + 1

        completed = []
        in_progress = []
        not_started = []
        late_completions_list = []

        # Get users who completed THIS session late
        late_user_ids = await db.get_late_completions_for_session(session['id'])

        for user in registered_users:
            user_id = user['user_id']
            # Get completions for THIS specific session
            user_completions = await db.get_user_completions_for_session(user_id, session['id'])
            member = guild.get_member(user_id)
            if not member:
                continue
            
            count = len(user_completions)
            
            if count == 0:
                not_started.append(f"**{member.display_name}**")
            elif count >= total_pages:
                # User completed all pages for this session
                # Check if they completed it late
                if user_id in late_user_ids:
                    # Completed late - show in late section
                    late_completions_list.append(f"**{member.display_name}**")
                else:
                    # Completed on time - show in completed section
                    streak_emoji = user.get('streak_emoji') or "🔥"
                    streak = f" - {user.get('session_streak', 0)}{streak_emoji}" if user.get('session_streak', 0) > 1 else ""
                    completed.append(f"**{member.display_name}**{streak}")
            else:
                # Still in progress (whether late or not)
                in_progress.append(f"**{member.display_name}** - {count}/{total_pages} pages")


        # Format the session date nicely
        session_date = session.get('session_date', today)
        embed = discord.Embed(
            title="📊 Daily Wird Progress",
            description=f"**Date:** {session_date}\n**Pages:** {total_pages}",
            color=discord.Color.blue()
        )

        # Prioritize: completed first, then in_progress, then late_completions, then not_started, up to 30 total lines
        total_limit = 30
        shown_completed = completed[:total_limit]
        remaining = total_limit - len(shown_completed)
        shown_in_progress = in_progress[:remaining]
        remaining -= len(shown_in_progress)
        shown_late_completions = late_completions_list[:remaining]
        remaining -= len(shown_late_completions)
        shown_not_started = not_started[:remaining]

        total_hidden = (len(completed) - len(shown_completed)) + (len(in_progress) - len(shown_in_progress)) + (len(late_completions_list) - len(shown_late_completions)) + (len(not_started) - len(shown_not_started))

        if shown_completed:
            embed.add_field(
                name=f"✅ Completed ({len(completed)})", 
                value="\n".join(shown_completed), 
                inline=False
            )

        if shown_in_progress:
            embed.add_field(
                name=f"⏳ In Progress ({len(in_progress)})", 
                value="\n".join(shown_in_progress), 
                inline=False
            )

        # Add late completions section BEFORE not started
        if shown_late_completions:
            embed.add_field(
                name=f"⏰ Completed Late ({len(late_completions_list)})",
                value="\n".join(shown_late_completions),
                inline=False
            )

        if shown_not_started:
            embed.add_field(
                name=f"❌ Not Started ({len(not_started)})", 
                value="\n".join(shown_not_started), 
                inline=False
            )

        if total_hidden > 0:
            embed.add_field(name="", value=f"... and {total_hidden} more", inline=False)

        if not completed and not in_progress and not not_started:
            embed.description += "\n\nNo registered users yet!"


        # Try to edit the previous summary message if it exists, otherwise send a new one
        summary_message_id = session.get('summary_message_id')
        if summary_message_id:
            try:
                msg = await channel.fetch_message(summary_message_id)
                await msg.edit(embed=embed)
                return
            except Exception as e:
                logger.warning(f"Could not edit summary message: {e}")
        
        # If we couldn't edit, send a new summary message and store its ID
        new_msg = await channel.send(embed=embed)
        await db.update_session_summary_message_id(session['id'], new_msg.id)

    except Exception as e:
        logger.error(f"Error sending followup: {e}")
