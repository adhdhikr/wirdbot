import discord
from discord.ext import commands
import logging
from pathlib import Path

from config import DISCORD_TOKEN, DEBUG_MODE, DEBUG_GUILD_IDS
from database import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

debug_guilds = DEBUG_GUILD_IDS if DEBUG_MODE else None
bot = commands.Bot(intents=intents, debug_guilds=debug_guilds)

if DEBUG_MODE:
    logger.info(f"🐛 DEBUG MODE ENABLED - Commands will register instantly to guilds {DEBUG_GUILD_IDS}")
else:
    logger.info("🌍 Production mode - Commands will register globally")


@bot.event
async def on_ready():
    await db.connect()
    logger.info(f"✅ {bot.user} is ready!")
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")


@bot.event
async def on_disconnect():
    await db.close()


@bot.event
async def on_guild_join(guild: discord.Guild):
    logger.info(f"Joined new guild: {guild.name} ({guild.id})")
    
    embed = discord.Embed(
        title="📖 Welcome to Wird Bot!",
        description="Thank you for adding me to your server! I help manage daily Quran reading (Wird) with tracking and streaks.",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="🚀 Quick Setup",
        value=(
            "1️⃣ Run `/setup` to configure the bot\n"
            "2️⃣ Set your mosque ID for prayer times\n"
            "3️⃣ Choose mushaf type (madani/uthmani/indopak)\n"
            "4️⃣ Set pages per day and channel"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⏰ Scheduling",
        value=(
            "Use `/schedule` to set when pages are sent:\n"
            "• Add prayer times (Fajr, Dhuhr, Asr, Maghrib, Isha)\n"
            "• Add custom times (e.g., 14:30 UTC)\n"
            "• Multiple times per day supported!"
        ),
        inline=False
    )
    
    embed.add_field(
        name="👥 User Features",
        value=(
            "• `/register` - Join daily Wird tracking\n"
            "• `/stats` - View your streaks and progress\n"
            "• Click 'Mark as Read' on pages to track completion"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Additional Configuration",
        value=(
            "• `/set_role` - Assign a role to registered users\n"
            "• `/update` - Modify individual settings\n"
            "• `/config` - View current configuration\n"
            "• `/send_now` - Manually trigger page sending"
        ),
        inline=False
    )
    
    embed.set_footer(text="Run /setup to get started! • Administrator permission required")
    
    # Try to send to system channel or first available text channel
    target_channel = guild.system_channel
    if not target_channel:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                target_channel = channel
                break
    
    if target_channel:
        try:
            await target_channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning(f"Cannot send welcome message to {guild.name} - no permissions")
    else:
        logger.warning(f"No suitable channel found in {guild.name} for welcome message")


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
