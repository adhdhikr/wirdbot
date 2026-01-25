import nextcord as discord
import google.generativeai as genai
import logging
import io
import contextlib
import textwrap
import traceback
import aiohttp
import os
import time
import asyncio
from config import GEMINI_API_KEY, API_BASE_URL, VALID_MUSHAF_TYPES, TOOL_LOG_CHANNEL_ID
from utils.tafsir import fetch_tafsir_for_ayah
from utils.translation import fetch_page_translations
from utils.quran import get_ayah, get_page, search_quran
from database import db
from .utils import ScopedBot

logger = logging.getLogger(__name__)

async def lookup_quran_page(page_number: int):
    """
    Get the English translation/text for a specific Quran page.
    Args:
        page_number: The page number (1-604).
    """
    try:
        page_number = int(float(page_number))
    except ValueError:
        return "Invalid page number."

    translations = await fetch_page_translations(page_number, 'eng')
    if not translations:
        return "Page not found or error fetching."
    

    result = ""
    for v in translations:
        result += f"[{v.get('chapter')}:{v.get('verse')}] {v.get('text')}\n"
    return result

async def lookup_tafsir(surah: int, ayah: int, edition: str = 'en-tafisr-ibn-kathir', segment: int = 0):
    """
    Get the Tafsir (exegesis) for a specific verse.
    Args:
        surah: Surah number.
        ayah: Ayah number.
        edition: 'en-tafisr-ibn-kathir' (default), 'ar-tafsir-ibn-kathir', 'en-al-jalalayn', or 'en-tafsir-maarif-ul-quran'.
        segment: The part number to retrieve (default 0). If text is long, request segment=1, 2, etc.
    """
    try:
        surah = int(float(surah))
        ayah = int(float(ayah))
        segment = int(float(segment))
    except (ValueError, TypeError):
        return "Invalid input parameters."

    try:
        text = await fetch_tafsir_for_ayah(edition, surah, ayah)
    except Exception as e:
        return f"Error calling fetch_tafsir_for_ayah: {e}"

    if not text:
        return "Tafsir not found."


    from utils.tafsir import TAFSIR_EDITIONS
    edition_name = TAFSIR_EDITIONS.get(edition, edition)
    attribution = f"\n\n**Source:** {edition_name}"


    full_text = text + attribution

    chunk_size = 1800
    chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
    
    if segment >= len(chunks):
        return "No more text available in this tafsir."
        
    result = chunks[segment]
    
    if segment < len(chunks) - 1:
        result += f"\n\n[SYSTEM: This is part {segment+1} of {len(chunks)}. To read the next part, call lookup_tafsir(..., segment={segment+1}). Tell the user there is more.]"
        
    return result

async def show_quran_page(page_number: int):
    """
    Uploads the image of a specific Quran page to the chat.
    Use this when the user asks to SEE the page.
    
    Args:
        page_number: The page number (1-604).
    """
    try:
        page_number = int(float(page_number))
    except (ValueError, TypeError):
        return "Invalid page number."

    return "Image uploaded."

async def execute_sql(query: str):
    """
    Execute a read-only SQL query (SELECT) immediately.
    Use this to inspect data without waiting for approval.
    
    Args:
        query: The SQL SELECT statement.
    """

    return "SQL_EXEC_PLACEHOLDER"

async def execute_python(code: str):
    """
    Propose Python code to execute.
    WARNING: Use this ONLY as a fallback capability when specialized tools (like get_ayah, read_file, update_server_config) cannot perform the task.
    This will NOT execute immediately; the user will be asked to approve it.
    
    Args:
        code: The Python code to execute.
    """
    return "Code proposed. Waiting for user approval."

async def search_codebase(query: str, is_regex: bool = False):
    """
    Search for a text pattern in the codebase.
    Returns file paths and line numbers where the pattern is found.
    
    Args:
        query: The string or regex pattern to search for.
        is_regex: If True, treats query as regex. Default False.
    """
    import re
    
    base_path = os.getcwd()
    allowed_extensions = ('.py', '.md', '.txt', '.json', '.sql')
    results = []
    
    try:
        if is_regex:
             pattern = re.compile(query, re.IGNORECASE)
    except re.error as e:
        return f"Invalid Regex: {e}"

    count = 0
    MAX_RESULTS = 50

    for root, dirs, files in os.walk(base_path):

        if any(x in root for x in ['.git', '__pycache__', 'venv', 'node_modules', '.gemini']):
             continue
            
        for file in files:
            if not file.endswith(allowed_extensions): continue
            if file == '.env': continue
            
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, base_path)
            
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    
                for i, line in enumerate(lines, 1):
                    match = False
                    if is_regex:
                        if pattern.search(line): match = True
                    else:
                        if query.lower() in line.lower(): match = True
                    
                    if match:
                        results.append(f"{rel_path}:{i}: {line.strip()[:200]}")
                        count += 1
                        if count >= MAX_RESULTS:
                             return "\n".join(results) + "\n... (More results truncated, refine search)"
            except Exception:
                continue
                
    return "\n".join(results) if results else "No matches found."

async def read_file(filename: str, start_line: int = 1, end_line: int = 100):
    """
    Read a file from the bot's codebase. 
    Reads first 100 lines by default. Specify lines to read more.
    
    Args:
        filename: Relative path to the file.
        start_line: Start line number (1-indexed). Default 1.
        end_line: End line number (inclusive). Default 100.
    """
    try:
        start_line = int(float(start_line))
        end_line = int(float(end_line))
    except (ValueError, TypeError):
        return "Invalid line numbers."


    allowed_extensions = ('.py', '.md', '.txt', '.json', '.sql')
    

    base_path = os.getcwd() # Should be bot root
    full_path = os.path.normpath(os.path.join(base_path, filename))
    
    if not full_path.startswith(base_path):
        return "Error: Cannot access files outside the bot directory."
        
    if not filename.endswith(allowed_extensions) or '.env' in filename:
         return "Error: File type not allowed or restricted."

    try:
        if not os.path.exists(full_path):
             return f"Error: File '{filename}' not found."
             
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        total_lines = len(lines)
        if start_line < 1: start_line = 1
        if end_line > total_lines: end_line = total_lines
        

        selected_lines = lines[start_line-1:end_line]
        content = "".join(selected_lines)
        
        result = f"File: {filename} (Lines {start_line}-{end_line} of {total_lines})\n\n{content}"
        
        if end_line < total_lines:
            result += f"\n... (Total {total_lines} lines. Read more with read_file(filename, start_line={end_line+1}, end_line={min(end_line+100, total_lines)}))"
            
        return result
    except Exception as e:
        return f"Error reading file: {e}"

async def get_db_schema():
    """
    Get the current database schema (CREATE TABLE statements).
    Use this to understand table names, columns, and relationships.
    """
    try:
        from database import db

        tables = await db.connection.execute_many("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        
        if not tables:
            return "No tables found in the database."
            
        result = "## Database Schema\n"
        for row in tables:
            name = row['name']
            sql = row['sql']
            result += f"### Table: {name}\n```sql\n{sql}\n```\n"
            
        return result
    except Exception as e:
        return f"Error fetching schema: {e}"

async def _get_ayah_safe(surah: int, ayah: int, edition: str = 'quran-uthmani'):
    """
    Get a specific Ayah (Verse). Wrapper for type safety.
    Args:
        surah: Surah number.
        ayah: Ayah number.
        edition: The edition/translation (default 'quran-uthmani').
    """
    try:
        surah = int(float(surah))
        ayah = int(float(ayah))
        ref = f"{surah}:{ayah}"
        try:
             return await get_ayah(ref, edition)
        except Exception as e:
             return f"Error calling get_ayah('{ref}', '{edition}'): {e}"
    except (ValueError, TypeError):
        return "Invalid Surah or Ayah number."

async def _get_page_safe(page: int, edition: str = 'quran-uthmani'):
    """
    Get a full Quran page text. Wrapper for type safety.
    Args:
        page: Page number (1-604).
        edition: Edition to retrieve.
    """
    try:
        page = int(float(page))
        return await get_page(page, edition)
    except (ValueError, TypeError):
        return "Invalid page number."

async def _search_quran_safe(keyword: str, surah: str = 'all', edition: str = 'quran-uthmani', language: str = 'en'):
    """
    Search the Quran. Wrapper to clean inputs.
    """
    if str(surah).lower() != 'all':
        try:
           surah = str(int(float(surah)))
        except:
           pass # Keep as is if not a number
           
    return await search_quran(keyword, surah, edition, language)

async def get_my_stats(user_id: str): # Gemini passes string usually
    """Get the caller's stats (streaks, etc)."""

    return "STATS_PLACEHOLDER"

async def set_my_streak_emoji(emoji: str):
    """Update the caller's streak emoji."""

    return "EMOJI_PLACEHOLDER"

async def update_server_config(setting: str, value: str):
    """
    Update a specific server configuration setting. (Admin Only).
    
    Args:
        setting: The setting to change. Allowed values:
                 - 'mushaf_type': (e.g. 'madani', 'tajweed', '13-line')
                 - 'pages_per_day': (Number 1-20)
                 - 'channel_id': (Resolution handled internally)
                 - 'mosque_id': (String ID)
                 - 'followup_on_completion': ('true' or 'false')
        value: The new value to set.
    """
    return "CONFIG_UPDATED"

async def _execute_python_internal(bot, code: str, ctx_data: dict) -> str:
    """Internal header to execute python code safely."""
    

    code = code.strip().strip('`')
    if code.startswith('python\n'):
        code = code[7:]


    if 'asyncio.run' in code:
            return "Error: You are already in an Async Event Loop. Do NOT use `asyncio.run()`. Use `await` directly on your coroutines. \nExample: `await my_async_function()` instead of `asyncio.run(my_async_function())`."


    author = ctx_data.get('author') or ctx_data.get('_author')
    is_owner = False
    if author:
            is_owner = await bot.is_owner(author)



    import utils
    from database import db
    
    env = {
        'discord': discord,
        'nextcord': discord, # Allow explicit nextcord usage
        'asyncio': asyncio,
        'aiohttp': aiohttp,
        'utils': utils, # Base utils

        'page_sender': utils.page_sender,
        'tafsir': utils.tafsir, 
        'translation': utils.translation,
        'quran': utils.quran,
        'db': db,
        'config': __import__('config')
    }
    

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

    env.update(ctx_data)
    

        
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
        logger.error(f"Python Execution Error: {e}")
        return f"Error: {e.__class__.__name__}: {e}\n{traceback.format_exc()}"
    
    output = stdout.getvalue()
    errors = stderr.getvalue()
    result_str = ""
    if output: result_str += f"Output:\n{output}\n"
    if errors: result_str += f"Errors:\n{errors}\n"
    if ret is not None: result_str += f"Return:\n{ret}"
    
    logger.info(f"Python Execution Result: {result_str[:200]}...") # Log brief result
    return result_str if result_str else "Executed successfully (No output)."

ALL_TOOLS = [
    lookup_quran_page,
    lookup_tafsir,
    show_quran_page,
    execute_python,
    get_my_stats,
    set_my_streak_emoji,
    read_file,
    search_codebase,
    update_server_config,
    get_db_schema,
    execute_sql,
    _get_ayah_safe,
    _get_page_safe,
    _search_quran_safe
]
