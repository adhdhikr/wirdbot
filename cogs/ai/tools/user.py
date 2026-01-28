"""
User-facing tools for the AI cog.
These are available to all users.
"""
import logging
from database import db

logger = logging.getLogger(__name__)


async def get_my_stats(**kwargs):
    """
    Get the caller's stats (streaks, etc).
    """
    message = kwargs.get('message')
    user_id = message.author.id if message else kwargs.get('user_id')
    guild_id = kwargs.get('guild_id')
    
    if not user_id or not guild_id:
        return "Error: User context missing."

    user_data = await db.get_user(user_id, guild_id)
    if user_data:
        if user_data.get('registered'):
            streak = user_data.get('session_streak', 0)
            longest = user_data.get('longest_session_streak', 0)
            emoji = user_data.get('streak_emoji', '🔥')
            return (
                f"**Your Stats:**\n"
                f"- Current Streak: {streak} {emoji}\n"
                f"- Longest Streak: {longest}\n"
                f"- Streak Emoji: {emoji}"
            )
        else:
            return "You are not registered! Use /register to get started."
    else:
        return "User not found in the database."


async def set_my_streak_emoji(emoji: str, **kwargs):
    """
    Update the caller's streak emoji.
    
    Args:
        emoji: The new emoji to use for streak display.
    """
    message = kwargs.get('message')
    user_id = message.author.id if message else kwargs.get('user_id')
    guild_id = kwargs.get('guild_id')
    
    if not user_id or not guild_id:
        return "Error: User context missing."
    
    user_data = await db.get_user(user_id, guild_id)
    if user_data and user_data.get('registered'):
        await db.set_user_streak_emoji(user_id, guild_id, emoji)
        return f"✅ Updated your streak emoji to {emoji}"
    else:
        return "You are not registered. Use /register first."


# Export list
USER_TOOLS = [
    get_my_stats,
    set_my_streak_emoji,
]
