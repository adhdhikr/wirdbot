import discord
from discord.ext import commands
import logging
from pathlib import Path

from config import DISCORD_TOKEN
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(intents=intents)
db = Database()


@bot.event
async def on_ready():
    await db.connect()
    logger.info(f"✅ {bot.user} is ready!")
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")


@bot.event
async def on_disconnect():
    await db.close()


def load_extensions():
    cogs_dir = Path(__file__).parent / "cogs"
    
    for cog_file in cogs_dir.glob("*.py"):
        if cog_file.stem.startswith("_"):
            continue
        
        cog_name = f"cogs.{cog_file.stem}"
        try:
            bot.load_extension(cog_name)
            logger.info(f"Loaded extension: {cog_name}")
        except Exception as e:
            logger.error(f"Failed to load extension {cog_name}: {e}")


if __name__ == "__main__":
    load_extensions()
    bot.run(DISCORD_TOKEN)
