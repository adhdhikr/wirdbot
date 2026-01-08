import discord
from database import db
import logging

logger = logging.getLogger(__name__)


async def send_followup_message(guild_id: int, bot):
    # ...existing code...
    
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
        all_completions = await db.get_all_completions_for_date(guild_id, today)

        session = await db.get_today_session(guild_id, today)
        if not session:
            return

        total_pages = session['end_page'] - session['start_page'] + 1

        completed = []
        in_progress = []
        not_started = []

        for user in registered_users:
            user_id = user['user_id']
            user_completions = all_completions.get(user_id, [])
            member = guild.get_member(user_id)
            if not member:
                continue
            count = len(user_completions)
            if count == 0:
                not_started.append(f"❌ {member.mention}")
            elif count >= total_pages:
                # Only show streak if > 1
                streak = f" - {user['current_streak']}🔥" if user['current_streak'] > 1 else ""
                completed.append(f"✅ {member.mention}{streak}")
            else:
                in_progress.append(f"⏳ {member.mention} - {count}/{total_pages} pages")

        embed = discord.Embed(
            title="📊 Daily Wird Progress",
            description=f"**Date:** {today}\n**Pages Today:** {total_pages}",
            color=discord.Color.blue()
        )

        if completed:
            embed.add_field(
                name=f"✅ Completed ({len(completed)})", 
                value="\n".join(completed[:10]), 
                inline=False
            )
            if len(completed) > 10:
                embed.add_field(name="", value=f"... and {len(completed) - 10} more", inline=False)

        if in_progress:
            embed.add_field(
                name=f"⏳ In Progress ({len(in_progress)})", 
                value="\n".join(in_progress[:10]), 
                inline=False
            )
            if len(in_progress) > 10:
                embed.add_field(name="", value=f"... and {len(in_progress) - 10} more", inline=False)

        if not_started:
            embed.add_field(
                name=f"❌ Not Started ({len(not_started)})", 
                value="\n".join(not_started[:10]), 
                inline=False
            )
            if len(not_started) > 10:
                embed.add_field(name="", value=f"... and {len(not_started) - 10} more", inline=False)

        if not completed and not in_progress and not not_started:
            embed.description += "\n\nNo registered users yet!"

        # Try to edit the previous followup message if it exists, otherwise send a new one and update the session
        message_id = None
        if session.get('message_ids'):
            ids = [mid for mid in session['message_ids'].split(',') if mid.strip()]
            if ids:
                try:
                    message_id = int(ids[-1])
                    msg = await channel.fetch_message(message_id)
                    await msg.edit(embed=embed)
                    return
                except Exception as e:
                    logger.warning(f"Could not edit last page message for summary: {e}")
        # If we couldn't edit, send a new summary message and update the session's message_ids
        new_msg = await channel.send(embed=embed)
        # Update the session's message_ids to only point to the new summary message
        await db.update_session_message_ids(guild_id, today, str(new_msg.id))
    except Exception as e:
        logger.error(f"Error sending followup: {e}")
