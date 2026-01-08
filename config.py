import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:5000")
PRAYER_API_BASE_URL = os.getenv("PRAYER_API_BASE_URL", "https://api.mrie.dev/prayertimes")

MAX_PAGES = 604
MIN_PAGES_PER_DAY = 1
MAX_PAGES_PER_DAY = 20
