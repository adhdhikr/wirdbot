import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")
PRAYER_API_BASE_URL = os.getenv("PRAYER_API_BASE_URL", "https://api.mrie.dev/prayertimes")

DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
DEBUG_GUILD_IDS = [int(gid.strip()) for gid in os.getenv("DEBUG_GUILD_IDS", "").split(",") if gid.strip()] if DEBUG_MODE else []

MAX_PAGES = 604
MIN_PAGES_PER_DAY = 1
MAX_PAGES_PER_DAY = 20
