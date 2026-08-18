import logging
import re

import nextcord as discord

from config import (
    AI_BACKLOG_CHARS_DM,
    AI_BACKLOG_CHARS_GUILD,
    AI_BACKLOG_MESSAGES_DM,
    AI_BACKLOG_MESSAGES_GUILD,
)

from .llm import types

logger = logging.getLogger(__name__)

# Everything the handler decorates a bot message with, so it can be taken back
# off before the message is shown to the model as its own past turn.
_SUBTEXT_LINE = re.compile(r'^[ \t]*-#.*$', re.MULTILINE)          # tool status lines
_MODEL_HEADER = re.compile(r'^\*\*Using [^\n*]*\*\*\s*', re.MULTILINE)  # "**Using kimi-k2.5 🧠**"
_INTERRUPTED = re.compile(r'🛑 \*\*(?:Interrupted by|Auto-Rejected)[^\n]*', re.MULTILINE)
_BLANK_RUN = re.compile(r'\n{3,}')


def clean_bot_message(content: str) -> str:
    """Strip handler-added decoration from a bot message: status lines, the
    model header, interruption notices."""
    for pattern in (_SUBTEXT_LINE, _MODEL_HEADER, _INTERRUPTED):
        content = pattern.sub('', content)
    return _BLANK_RUN.sub('\n\n', content).strip()

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
    char_limit = AI_BACKLOG_CHARS_DM if is_dm else AI_BACKLOG_CHARS_GUILD
    
    current_chars = 0
    recent_msgs = []
    search_limit = AI_BACKLOG_MESSAGES_DM if is_dm else AI_BACKLOG_MESSAGES_GUILD
    
    async for msg in message.channel.history(limit=search_limit, before=message):
        if message.channel.id in context_pruning_markers:
            if msg.id <= context_pruning_markers[message.channel.id]:
                break
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
            for att in msg.attachments:
                content += f"\n[System: Attachment: {att.url}]"

        if role == "model":
            # The bot's own turns go back verbatim, minus everything the bot
            # itself added to them. Metadata prefixes and tool status lines are
            # written by the handler, not the model — feeding them back reads
            # as "this is how I write", and the model starts producing its own
            # fake "-# 🛠️ Running ..." lines and [Replying to ID: ...] headers.
            text = clean_bot_message(content)
            if not text:
                continue
        else:
            time_str = msg.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            prefix = f"[{time_str}] [Message ID: {msg.id}]"
            if msg.reference and msg.reference.message_id:
                prefix += f" [Replying to ID: {msg.reference.message_id}]"
            text = f"{prefix} User {msg.author.display_name} ({msg.author.id}): {content}"

        history.append(types.Content(role=role, parts=[types.Part(text=text)]))

    return history
