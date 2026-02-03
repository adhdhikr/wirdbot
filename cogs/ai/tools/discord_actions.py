"""
Discord code execution tools for the AI cog.
This provides the execute_discord_code tool that runs Python with Discord context.

SECURITY: Non-owners are blocked from HTTP/network requests.
"""
import nextcord as discord
import asyncio
import aiohttp
import io
import contextlib
import textwrap
import traceback
import logging
import inspect
from ..utils import ScopedBot

logger = logging.getLogger(__name__)


class ScopedDatabase:
    """
    A wrapper around the Database instance to restricting access to a specific guild_id.
    """
    def __init__(self, db_instance, guild_id: int):
        self._db = db_instance
        self._guild_id = guild_id

    def __getattr__(self, name):
        attr = getattr(self._db, name)
        
        if not callable(attr):
            return attr
            
        # Wrap methods to check for guild_id
        async def scoped_method(*args, **kwargs):
            # Inspect signature to find guild_id
            sig = inspect.signature(attr)
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            # Check arguments for guild_id
            if 'guild_id' in bound.arguments:
                arg_guild_id = bound.arguments['guild_id']
                if arg_guild_id != self._guild_id:
                     raise PermissionError(f"❌ Security Error: You cannot access data for guild {arg_guild_id}. You are restricted to guild {self._guild_id}.")
            
            return await attr(*args, **kwargs)
            
        return scoped_method


# Security: Blocked imports for non-owners
BLOCKED_IMPORTS_NON_OWNER = [
    'aiohttp', 'requests', 'urllib', 'httpx', 'socket', 
    'http.client', 'http.server', 'ftplib', 'smtplib', 'telnetlib',
    'os', 'sys', 'subprocess', 'pathlib', 'shutil', 'glob', 'token', 'inspect'
]

# Security: Blocked URL patterns for non-owners
BLOCKED_URL_PATTERNS = ['http://', 'https://', 'ftp://']


async def execute_discord_code(code: str, **kwargs):
    """
    Propose Python code to execute with Discord context.
    Use this for Discord server interactions: managing channels, roles, sending messages, etc.
    
    WARNING: This will NOT execute immediately; the user will be asked to approve it.
    
    SECURITY NOTES:
    - Only Bot Owner can use HTTP/network requests (aiohttp, requests, etc.)
    - Admins can only use Discord-related operations
    
    Args:
        code: The Python code to execute.
    """
    is_owner = kwargs.get('is_owner', False)
    is_admin = kwargs.get('is_admin', False)
    
    if not (is_owner or is_admin):
        return "❌ Error: Permission Denied. You must be an Admin or Bot Owner to use this tool."
        
    return "Code proposed. Waiting for user approval."


async def _execute_discord_code_internal(bot, code: str, ctx_data: dict) -> str:
    """
    Internal function to execute Python code safely with Discord context.
    
    Security checks:
    - Non-owners cannot use network/HTTP libraries
    - Non-owners cannot make external requests
    """
    # Clean up code
    code = code.strip().strip('`')
    if code.startswith('python\n'):
        code = code[7:]

    # Check for asyncio.run which would crash
    if 'asyncio.run' in code:
        return (
            "Error: You are already in an Async Event Loop. Do NOT use `asyncio.run()`. "
            "Use `await` directly on your coroutines.\n"
            "Example: `await my_async_function()` instead of `asyncio.run(my_async_function())`."
        )

    # Get author and check ownership
    author = ctx_data.get('author') or ctx_data.get('_author')
    is_owner = False
    if author:
        is_owner = await bot.is_owner(author)

    # === SECURITY CHECKS FOR NON-OWNERS ===
    if not is_owner:
        # Check for blocked imports
        for blocked in BLOCKED_IMPORTS_NON_OWNER:
            if f'import {blocked}' in code or f'from {blocked}' in code:
                return f"❌ Security Error: `{blocked}` is not allowed for non-owners. Only Discord operations are permitted."
        
        # Check for URL patterns (attempting to make requests)
        for pattern in BLOCKED_URL_PATTERNS:
            if pattern in code:
                return "❌ Security Error: HTTP/network requests are not allowed for non-owners. Only Discord operations are permitted."
        
        # Check for potentially dangerous patterns
        dangerous_patterns = [
            'subprocess', 'os.system', 'eval(', 'exec(', '__import__',
            'open(', 'with open', 'file(', 'input(', 'raw_input(',
            'bot.user.edit', 'bot.close', 'sys.exit', 'quit('
        ]
        for pattern in dangerous_patterns:
            if pattern in code:
                return f"❌ Security Error: `{pattern}` is not allowed for non-owners."

    # Build execution environment
    import utils
    from database import db
    
    env = {
        'discord': discord,
        'nextcord': discord,  # Allow explicit nextcord usage
        'asyncio': asyncio,
        'utils': utils,
        'page_sender': utils.page_sender,
        'tafsir': utils.tafsir, 
        'translation': utils.translation,
        'quran': utils.quran,
        'config': __import__('config')
    }
    
    # Inject Database with Scope check
    if is_owner:
         env['db'] = db
    else:
         guild = ctx_data.get('guild') or ctx_data.get('_guild')
         if guild:
             env['db'] = ScopedDatabase(db, guild.id)
         else:
             env['db'] = None
    
    # Add aiohttp only for owners
    if is_owner:
        env['aiohttp'] = aiohttp
    
    # Add context data
    env.update(ctx_data)
    
    # Force overwrite bot/ctx variables with Scoped variants if not owner
    if is_owner:
        env['bot'] = bot
        env['_bot'] = bot
    else:
        guild = ctx_data.get('guild') or ctx_data.get('_guild')
        if guild:
            scoped_bot = ScopedBot(bot, guild.id)
            env['bot'] = scoped_bot
            env['_bot'] = scoped_bot
        else:
            return "Error: Cannot execute code outside of a server context."
    
    # Execute the code
    body = f"async def func():\n{textwrap.indent(code, '  ')}"
    stdout = io.StringIO()
    stderr = io.StringIO()
    
    try:
        with contextlib.redirect_stderr(stderr):
            exec(body, env)
            
        func = env['func']
        
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            ret = await func()
            
    except Exception as e:
        logger.error(f"Discord Code Execution Error: {e}")
        return f"Error: {e.__class__.__name__}: {e}\n{traceback.format_exc()}"
    
    output = stdout.getvalue()
    errors = stderr.getvalue()
    result_str = ""
    if output:
        result_str += f"Output:\n{output}\n"
    if errors:
        result_str += f"Errors:\n{errors}\n"
    if ret is not None:
        result_str += f"Return:\n{ret}"
    
    logger.info(f"Discord Code Execution Result: {result_str[:200]}...")
    return result_str if result_str else "Executed successfully (No output)."


# Export list
async def search_channel_history(query: str, limit: int = 5, **kwargs) -> str:
    """
    Searches the channel's message history for a query.
    Use this when the user refers to past context that you don't recall.
    
    Args:
        query: The search term or phrase.
        limit: Number of matches to return (default 5).
        **kwargs: Injected context.
    """
    channel = kwargs.get('channel')
    if not channel: return "Error: Channel context missing."
    
    matches = []
    # Search last 500 messages
    async for msg in channel.history(limit=500):
        if query.lower() in msg.content.lower():
            auth = msg.author.display_name
            content = msg.content
            if msg.attachments:
                content += f" [Attachment: {msg.attachments[0].url}]"
            matches.append(f"[{msg.created_at.strftime('%m-%d %H:%M')}] {auth}: {content}")
            if len(matches) >= limit: break
            
    if not matches:
        return f"No matches found for '{query}' in the last 500 messages."
        
    return f"**Search Results for '{query}':**\n" + "\n".join(matches)

DISCORD_TOOLS = [
    execute_discord_code,
    search_channel_history
]
