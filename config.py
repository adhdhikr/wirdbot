import os

from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "180"))
OPENROUTER_MAX_TOKENS = int(os.getenv("OPENROUTER_MAX_TOKENS", "8000"))
# Sent as HTTP-Referer / X-Title so the bot shows up properly on openrouter.ai
OPENROUTER_APP_URL = os.getenv("OPENROUTER_APP_URL", "https://github.com/wirdbot")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "WirdBot")

# Models (OpenRouter slugs). Override in .env without touching code.
AI_COMPLEX_MODEL = os.getenv("AI_COMPLEX_MODEL", "deepseek/deepseek-v4-pro")
AI_SIMPLE_MODEL = os.getenv("AI_SIMPLE_MODEL", "qwen/qwen3.7-flash")
AI_ROUTER_MODEL = os.getenv("AI_ROUTER_MODEL", "qwen/qwen3.7-flash")
AI_VISION_MODEL = os.getenv("AI_VISION_MODEL", "qwen/qwen3.7-flash")

# Reasoning effort per tier: "none" disables thinking, otherwise low/medium/high.
# Rough cap on how much conversation we resend each turn (characters, not tokens).
AI_MAX_HISTORY_CHARS = int(os.getenv("AI_MAX_HISTORY_CHARS", "120000"))
AI_COMPLEX_REASONING = os.getenv("AI_COMPLEX_REASONING", "high")
AI_SIMPLE_REASONING = os.getenv("AI_SIMPLE_REASONING", "low")
CLOUDCONVERT_API_KEY = os.getenv("CLOUDCONVERT_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
DEBUG_GUILD_IDS = [int(gid.strip()) for gid in os.getenv("DEBUG_GUILD_IDS", "").split(",") if gid.strip()] if DEBUG_MODE else []

TOOL_LOG_CHANNEL_ID = int(os.getenv("TOOL_LOG_CHANNEL_ID")) if os.getenv("TOOL_LOG_CHANNEL_ID") and os.getenv("TOOL_LOG_CHANNEL_ID").isdigit() else None
MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS", "15"))

MAX_PAGES = 604
MIN_PAGES_PER_DAY = 1
MAX_PAGES_PER_DAY = 20

VALID_MUSHAF_TYPES = [
    "kfgqpc-warsh",
    "ayat-warsh",
    "kfgqpc-hafs-wasat",
    "easyquran-hafs-tajweed",
    "ayat-hafs",
    "ayat-tajweed"
]

OWNER_IDS = {
    1030575337869955102,
    1172856531667140669
}
