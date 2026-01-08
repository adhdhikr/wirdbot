import discord
from database import Database
from config import MIN_PAGES_PER_DAY, MAX_PAGES_PER_DAY


async def handle_setup(interaction: discord.Interaction, children):
    db = Database()
    await db.connect()
    
    try:
        mosque_id = children[0].value
        mushaf_type = children[1].value
        pages_per_day = int(children[2].value)
        channel_id = int(children[3].value)
        
        if pages_per_day < MIN_PAGES_PER_DAY or pages_per_day > MAX_PAGES_PER_DAY:
            await interaction.response.send_message(
                f"Pages per day must be between {MIN_PAGES_PER_DAY} and {MAX_PAGES_PER_DAY}!", 
                ephemeral=True
            )
            return
        
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            await interaction.response.send_message("Invalid channel ID!", ephemeral=True)
            return
        
        await db.create_or_update_guild(
            interaction.guild_id,
            mosque_id=mosque_id,
            mushaf_type=mushaf_type,
            pages_per_day=pages_per_day,
            channel_id=channel_id,
            configured=1
        )
        
        await interaction.response.send_message(
            f"✅ Configuration saved!\n"
            f"**Mosque ID:** {mosque_id}\n"
            f"**Mushaf:** {mushaf_type}\n"
            f"**Pages/Day:** {pages_per_day}\n"
            f"**Channel:** <#{channel_id}>\n\n"
            f"Use `/schedule` to configure when pages should be sent.",
            ephemeral=True
        )
    except ValueError:
        await interaction.response.send_message("Invalid input! Please check your values.", ephemeral=True)
    finally:
        await db.close()
