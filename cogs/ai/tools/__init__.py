"""
AI Tools Package

This package organizes all AI tools into categorical modules:
- quran: Quran and Tafsir tools
- admin: Database and codebase access tools
- user: User-facing tools (stats, streak)
- bot_management: Bot status management
- discord_actions: Discord code execution with security
- web: Web search and URL reading

Built-in Gemini capabilities are also configured here:
- Code execution (sandboxed) - Disabled for Gemini 3 Preview
"""
from .quran import QURAN_TOOLS, lookup_quran_page, lookup_tafsir, show_quran_page, get_ayah_safe, get_page_safe, search_quran_safe
from .admin import ADMIN_TOOLS, execute_sql, search_codebase, read_file, get_db_schema, update_server_config
from .user import USER_TOOLS, get_my_stats, set_my_streak_emoji
from .bot_management import BOT_MANAGEMENT_TOOLS, force_bot_status, add_bot_status_option
from .discord_actions import DISCORD_TOOLS, execute_discord_code, _execute_discord_code_internal
from .web import WEB_TOOLS, search_web, read_url
from .vision import VISION_TOOLS, analyze_image
from .memory import MEMORY_TOOLS
from .sandbox import SANDBOX_TOOLS

# All custom function-calling tools
CUSTOM_TOOLS = QURAN_TOOLS + ADMIN_TOOLS + USER_TOOLS + BOT_MANAGEMENT_TOOLS + DISCORD_TOOLS + WEB_TOOLS + VISION_TOOLS + MEMORY_TOOLS + SANDBOX_TOOLS

__all__ = [
    # Tool lists
    'CUSTOM_TOOLS',
    'QURAN_TOOLS',
    'ADMIN_TOOLS', 
    'USER_TOOLS',
    'BOT_MANAGEMENT_TOOLS',
    'DISCORD_TOOLS',
    'WEB_TOOLS',
    'VISION_TOOLS',
    'MEMORY_TOOLS',
    'SANDBOX_TOOLS',
    
    # Individual tools for dispatcher
    'lookup_quran_page',
    'lookup_tafsir',
    'show_quran_page',
    'get_ayah_safe',
    'get_page_safe',
    'search_quran_safe',
    'execute_sql',
    'search_codebase',
    'read_file',
    'get_db_schema',
    'update_server_config',
    'get_my_stats',
    'set_my_streak_emoji',
    'force_bot_status',
    'add_bot_status_option',
    'execute_discord_code',
    '_execute_discord_code_internal',
    'search_web',
    'read_url',
]
