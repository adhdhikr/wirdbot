import nextcord as discord
from nextcord.ext import commands
import logging
from pathlib import Path

from config import DISCORD_TOKEN, DEBUG_MODE, DEBUG_GUILD_IDS, OWNER_IDS
from database import db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True



bot = commands.Bot(intents=intents, command_prefix="!", owner_ids=OWNER_IDS)

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
async def on_interaction(interaction: discord.Interaction):

    if interaction.type == discord.InteractionType.component:
        custom_id = interaction.data.get('custom_id', '')
        if custom_id.startswith('complete_'):
            try:
                page_number = int(custom_id.split('_')[1])
                from utils.completion import handle_completion
                await handle_completion(interaction, page_number)
                return  # Handled
            except (ValueError, IndexError):
                logger.warning(f"Invalid completion button custom_id: {custom_id}")
                return
        elif custom_id.startswith('translate_'):
            try:
                page_number = int(custom_id.split('_')[1])
                from utils.interaction_handlers import handle_translation
                await handle_translation(interaction, page_number)
                return  # Handled
            except (ValueError, IndexError):
                logger.warning(f"Invalid translation button custom_id: {custom_id}")
                return
        elif custom_id.startswith('tafsir_'):
            parts = custom_id.split('_')
            if len(parts) >= 2 and parts[1].isdigit():
                try:
                    page_number = int(parts[1])
                    from utils.interaction_handlers import handle_tafsir
                    await handle_tafsir(interaction, page_number)
                    return  # Handled
                except (ValueError, IndexError):
                    logger.warning(f"Invalid tafsir button custom_id: {custom_id}")
                    return

    

    try:
        await bot.process_application_commands(interaction)
    except Exception as e:
        logger.error(f"Error processing interaction: {e}")


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
        value="Run `/setup` to configure the bot with an interactive wizard.\n\n**Required Permission:** Manage Channels",
        inline=False
    )
    
    embed.set_footer(text="Run /setup to get started!")
    

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
    bot.load_extension('onami')
    cogs_dir = Path(__file__).parent / "cogs"
    
    # Load .py files
    for cog_file in cogs_dir.glob("*.py"):
        if cog_file.stem.startswith("_"):
            continue
        
        cog_name = f"cogs.{cog_file.stem}"
        try:
            bot.load_extension(cog_name)
            logger.info(f"Loaded extension: {cog_name}")
        except Exception as e:
            logger.error(f"Failed to load extension {cog_name}: {e}")

    # Load directories (packages)
    for cog_dir in cogs_dir.iterdir():
        if cog_dir.is_dir() and (cog_dir / "__init__.py").exists():
            if cog_dir.name.startswith("_"):
                continue
            
            cog_name = f"cogs.{cog_dir.name}"
            try:
                bot.load_extension(cog_name)
                logger.info(f"Loaded extension package: {cog_name}")
            except Exception as e:
                logger.error(f"Failed to load extension package {cog_name}: {e}")


if __name__ == "__main__":
    load_extensions()
    bot.run(DISCORD_TOKEN)
