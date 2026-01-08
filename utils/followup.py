import discord
from database import Database
import logging

logger = logging.getLogger(__name__)


async def send_followup_message(guild_id: int, bot):
    db = Database()
    await db.connect()
    
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
        incomplete = []
        
        for user in registered_users:
            user_id = user['user_id']
            user_completions = all_completions.get(user_id, [])
            
            member = guild.get_member(user_id)
            if not member:
                continue
            
            if len(user_completions) >= total_pages:
                completed.append(f"✅ {member.mention} - {user['current_streak']}🔥")
            else:
                incomplete.append(f"⏳ {member.mention} - {len(user_completions)}/{total_pages} pages")
        
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
        
        if incomplete:
            embed.add_field(
                name=f"⏳ In Progress ({len(incomplete)})", 
                value="\n".join(incomplete[:10]), 
                inline=False
            )
            if len(incomplete) > 10:
                embed.add_field(name="", value=f"... and {len(incomplete) - 10} more", inline=False)
        
        if not completed and not incomplete:
            embed.description += "\n\nNo registered users yet!"
        
        await channel.send(embed=embed)
    except Exception as e:
        logger.error(f"Error sending followup: {e}")
    finally:
        await db.close()
