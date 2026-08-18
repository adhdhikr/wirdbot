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
# One vision-capable model handles every chat, images included.
AI_MODEL = os.getenv("AI_MODEL", "qwen/qwen3-vl-8b-instruct")
# Reasoning effort: "none" disables thinking, otherwise low/medium/high.
AI_REASONING = os.getenv("AI_REASONING", "low")
# The analyze_image tool (for files already in a user's space) — same model by default.
AI_VISION_MODEL = os.getenv("AI_VISION_MODEL", AI_MODEL)

# Optional two-tier routing: a cheap classifier picks a small or big model per
# message. Off by default — AI_MODEL answers everything.
AI_ROUTING_ENABLED = os.getenv("AI_ROUTING_ENABLED", "false").lower() == "true"
AI_COMPLEX_MODEL = os.getenv("AI_COMPLEX_MODEL", AI_MODEL)
AI_SIMPLE_MODEL = os.getenv("AI_SIMPLE_MODEL", "qwen/qwen3.7-flash")
AI_ROUTER_MODEL = os.getenv("AI_ROUTER_MODEL", "qwen/qwen3.7-flash")
AI_COMPLEX_REASONING = os.getenv("AI_COMPLEX_REASONING", AI_REASONING)
AI_SIMPLE_REASONING = os.getenv("AI_SIMPLE_REASONING", "low")

# Context budget, enforced per request (estimated tokens, ~4 chars each).
# Covers the system prompt, tool schemas and conversation; the oldest turns are
# dropped until the request fits, leaving room for the reply.
AI_MAX_CONTEXT_TOKENS = int(os.getenv("AI_MAX_CONTEXT_TOKENS", "48000"))
# A single tool result (web page, file dump) is truncated to this before it
# enters the conversation — otherwise one big page poisons every later turn.
AI_MAX_TOOL_RESULT_CHARS = int(os.getenv("AI_MAX_TOOL_RESULT_CHARS", "12000"))
# Text attachments are inlined into the message up to this size.
AI_MAX_ATTACHMENT_CHARS = int(os.getenv("AI_MAX_ATTACHMENT_CHARS", "20000"))
# How many images from one message are handed to the model.
AI_MAX_IMAGES = int(os.getenv("AI_MAX_IMAGES", "4"))
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
