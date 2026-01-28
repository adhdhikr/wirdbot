"""
Bot management tools for the AI cog.
These control bot status and configuration.
"""
import logging

logger = logging.getLogger(__name__)


async def force_bot_status(status_text: str, duration_minutes: int = 30, **kwargs):
    """
    Force the bot's status (activity) to a specific text for a set duration.
    Use this when you want to change what the bot is "doing" in Discord based on user request.
    
    Args:
        status_text: The text to display (e.g., "Reading Quran", "Coding").
        duration_minutes: How long to keep this status before resuming rotation. Default 30.
    """
    bot = kwargs.get('bot')
    if not bot:
        return "Error: Bot context missing."

    try:
        duration_minutes = int(float(duration_minutes))
    except (ValueError, TypeError):
        duration_minutes = 30
    
    status_cog = bot.get_cog('Status')
    if not status_cog:
        return "❌ Error: Status Cog is not loaded."
    
    await status_cog.force_status(status_text, duration_minutes)
    return f"✅ Forced status to '{status_text}' for {duration_minutes} minutes."


async def add_bot_status_option(status_text: str, **kwargs):
    """
    Add a new status option to the bot's rotation list.
    Use this when the user wants to add a new "fun" activity for the bot to do periodically.
    
    Args:
        status_text: The new status text to add.
    """
    bot = kwargs.get('bot')
    if not bot:
        return "Error: Bot context missing."

    status_cog = bot.get_cog('Status')
    if not status_cog:
        return "❌ Error: Status Cog is not loaded."
    
    if status_cog.add_status_option(status_text):
        return f"✅ Added '{status_text}' to the status rotation list."
    else:
        return f"'{status_text}' is already in the status rotation list."


# Export list
async def clear_context(confirmation: bool = True, **kwargs) -> str:
    """
    Clears the AI's short-term memory for this channel.
    Use this when a conversation topic terminates and you want to start fresh.
    
    Args:
        confirmation: Must be True to proceed.
        **kwargs: Injected context (cog, channel_id).
    """
    cog = kwargs.get('cog')
    channel = kwargs.get('channel')
    
    if not confirmation:
        return "Context clear cancelled (confirmation=False)."
        
    if not cog or not channel:
        return "Error: Internal context missing."
        
    try:
        # Clear in-memory history
        if channel.id in cog.chat_histories:
            del cog.chat_histories[channel.id]
            
        # Set pruning marker to ignore messages before NOW
        # We need the current message ID. 'message' is passed in kwargs.
        current_msg = kwargs.get('message')
        if current_msg:
             cog.context_pruning_markers[channel.id] = current_msg.id
             
        # Also remove active task if any (besides self)? No, just history.
        return "✅ Context cleared. I have forgotten previous messages in this session."
        
    except Exception as e:
        return f"Error clearing context: {e}"

BOT_MANAGEMENT_TOOLS = [
    force_bot_status,
    add_bot_status_option,
    clear_context
]
