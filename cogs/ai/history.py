import logging
import nextcord as discord
from google.genai import types

logger = logging.getLogger(__name__)

async def build_chat_history(bot: discord.Client, message: discord.Message, context_pruning_markers: dict) -> list:
    """
    Builds the chat history context for a given message.
    """
    reply_chain = []
    curr = message
    for _ in range(5):
        if not curr.reference:
            break

        if curr.reference.resolved and isinstance(curr.reference.resolved, discord.Message):
            curr = curr.reference.resolved
            reply_chain.append(curr)
        elif curr.reference.message_id:
            try:
                curr = await message.channel.fetch_message(curr.reference.message_id)
                reply_chain.append(curr)
            except Exception:
                break
        else:
            break
            
    is_dm = isinstance(message.channel, discord.DMChannel)
    char_limit = 14000 if is_dm else 6000
    
    current_chars = 0
    recent_msgs = []
    search_limit = 300 if is_dm else 100 
    
    async for msg in message.channel.history(limit=search_limit, before=message):
        if message.channel.id in context_pruning_markers:
            if msg.id <= context_pruning_markers[message.channel.id]:
                continue 
        if msg.id in [m.id for m in reply_chain] or msg.id == message.id:
            continue
        msg_len = len(msg.content)
        if current_chars + msg_len > char_limit:
             break
        
        current_chars += msg_len
        recent_msgs.append(msg)
    
    recent_msgs.reverse() 
    reply_chain.reverse() 
    full_context_msgs = recent_msgs + reply_chain
    
    history = []
    logger.info(f"Context Build: {current_chars} chars from {len(recent_msgs)} history msgs + {len(reply_chain)} replies.")
    
    for msg in full_context_msgs:
        role = "model" if msg.author.id == bot.user.id else "user"
        content = msg.content
        if msg.attachments:
            content += f"\\n[System: Attachment: {msg.attachments[0].url}]"

        if role == "user":
            text = f"User {msg.author.display_name} ({msg.author.id}): {content}"
        else:
            text = content
            
        history.append(types.Content(role=role, parts=[types.Part(text=text)]))
        
    return history
