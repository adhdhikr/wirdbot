"""
Discord code execution tools for the AI cog.
This provides the execute_discord_code tool that runs Python with Discord context.

SECURITY LAYERS (Defense in Depth):
1. Permission-based access (Owner/Admin only)
2. Guild scoping (Admins restricted to their guild only)
3. Import blocking (All imports blocked for non-owners)
4. Restricted builtins (No __import__, eval, exec, getattr, setattr, etc.)
5. Pattern matching (Blocks dangerous code patterns via regex)
6. Module mutation prevention (Cannot modify pre-loaded module attributes)
7. User approval workflow (All code must be reviewed before execution)

NON-OWNER RESTRICTIONS:
- ❌ No import statements allowed (use pre-loaded modules only)
- ❌ No access to config, secrets, or internal modules
- ❌ No HTTP/network requests
- ❌ No file system access
- ❌ No introspection tools (getattr, setattr, globals, locals, etc.)
- ❌ No module attribute mutations
- ✅ Discord operations only (channels, roles, messages, moderation)
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
import re
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
    'os', 'sys', 'subprocess', 'pathlib', 'shutil', 'glob', 'token', 'inspect',
    'config', 'cogs', 'db', 'database', 'main'  # Block internal modules
]

# Security: Blocked URL patterns for non-owners
BLOCKED_URL_PATTERNS = ['http://', 'https://', 'ftp://']


async def execute_discord_code(code: str, **kwargs):
    """
    Propose Python code to execute with Discord context.
    Use this for Discord server interactions: managing channels, roles, sending messages, etc.
    
    WARNING: This will NOT execute immediately; the user will be asked to approve it.
    
    SECURITY NOTES:
    - Available to Bot Owner always
    - Available to Admins in whitelisted guilds only
    
    Args:
        code: The Python code to execute.
    """
    is_owner = kwargs.get('is_owner', False)
    is_admin = kwargs.get('is_admin', False)
    whitelisted_guild = kwargs.get('whitelisted_guild', False)
    
    # Owner always has access
    if is_owner:
        return "Code proposed. Waiting for user approval."
    
    # Admins only in whitelisted guilds
    if is_admin and whitelisted_guild:
        return "Code proposed. Waiting for user approval."
    
    # Everyone else is denied
    if is_admin and not whitelisted_guild:
        return "❌ Error: This guild is not whitelisted for admin code execution. Ask the bot owner to whitelist this server."
    
    return "❌ Error: Permission Denied. This tool is restricted to Bot Owner and Admins in whitelisted guilds."


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
        # CRITICAL: Block ALL import statements for non-owners
        # Only pre-approved modules in env{} are allowed
        import_check = re.compile(r'\b(import|from)\s+\w+', re.IGNORECASE)
        if import_check.search(code):
            return "❌ Security Error: Import statements are not allowed for non-owners. Use pre-loaded modules only (discord, asyncio, utils, db)."
        
        # Check for URL patterns (attempting to make requests)
        for pattern in BLOCKED_URL_PATTERNS:
            if pattern in code:
                return "❌ Security Error: HTTP/network requests are not allowed for non-owners. Only Discord operations are permitted."
        
        # Check for potentially dangerous patterns with regex word boundaries
        dangerous_patterns = [
            r'\bsubprocess\b', r'\bos\.system\b', r'\beval\s*\(', r'\bexec\s*\(', r'\b__import__\s*\(',
            r'\bopen\s*\(', r'\bwith\s+open\b', r'\bfile\s*\(', r'\binput\s*\(', r'\braw_input\s*\(',
            r'\bbot\.user\.edit\b', r'\bbot\.close\b', r'\bsys\.exit\b', r'\bquit\s*\(',
            r'\b__builtins__\b', r'\bgetattr\s*\(', r'\bsetattr\s*\(', r'\bdelattr\s*\(', r'\bcompile\s*\(',
            r'\bglobals\s*\(', r'\blocals\s*\(', r'\bvars\s*\(', r'\bdir\s*\(',
            r'\b__dict__\b', r'\b__class__\b', r'\b__bases__\b', r'\b__subclasses__\b',
            r'\btype\s*\(', r'\bisinstance\s*\(.*,\s*type\)',
            r'\.__(set|get|del)attr__\b',  # Dunder methods for attribute manipulation
            r'\bcogs\b', r'\bprompts\b', r'\bconfig\b', r'\bmain\b'  # Block internal module access
        ]
        for pattern in dangerous_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                return f"❌ Security Error: Pattern `{pattern}` is not allowed for non-owners."
        
        # CRITICAL: Block module attribute mutations (e.g., utils.something = value, discord.User.name = value)
        # This prevents runtime modification of imported modules
        module_mutation_pattern = r'(utils|discord|nextcord|asyncio|page_sender|tafsir|translation|quran|db|bot)\.\w+\s*='
        if re.search(module_mutation_pattern, code):
            return "❌ Security Error: Cannot modify attributes of pre-loaded modules. This is a security violation."

    # Build execution environment
    import utils
    from database import db
    
    # SECURITY: Create restricted builtins for non-owners
    if is_owner:
        # Owners get full access
        restricted_builtins = __builtins__
    else:
        # Non-owners get severely restricted builtins
        # Remove dangerous functions that could be used for introspection or execution
        safe_builtins = {
            'abs', 'all', 'any', 'ascii', 'bin', 'bool', 'bytearray', 'bytes',
            'chr', 'dict', 'divmod', 'enumerate', 'filter', 'float', 'format',
            'frozenset', 'hex', 'int', 'isinstance', 'iter', 'len', 'list',
            'map', 'max', 'min', 'next', 'oct', 'ord', 'pow', 'range',
            'reversed', 'round', 'set', 'slice', 'sorted', 'str', 'sum',
            'tuple', 'zip', 'True', 'False', 'None',
            'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
            'print'  # Allow print for debugging
        }
        restricted_builtins = {k: __builtins__[k] for k in safe_builtins if k in __builtins__}
    
    env = {
        '__builtins__': restricted_builtins,
        'discord': discord,
        'nextcord': discord,  # Allow explicit nextcord usage
        'asyncio': asyncio,
        'utils': utils,
        'page_sender': utils.page_sender,
        'tafsir': utils.tafsir, 
        'translation': utils.translation,
        'quran': utils.quran
    }
    
    # SECURITY: Only owners get config access
    if is_owner:
        env['config'] = __import__('config')
    
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
