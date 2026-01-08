import discord
from database import Database


async def register_user_with_role(interaction: discord.Interaction):
    db = Database()
    await db.connect()
    try:
        await db.register_user(interaction.user.id, interaction.guild_id)
        guild_config = await db.get_guild_config(interaction.guild_id)
        role = None
        # Try to get the role from config, or create if missing
        if guild_config and guild_config['wird_role_id']:
            role = interaction.guild.get_role(guild_config['wird_role_id'])
        if not role:
            # Create the role if it doesn't exist
            try:
                role = await interaction.guild.create_role(name="Wird", reason="Wird registered users")
                await db.create_or_update_guild(interaction.guild_id, wird_role_id=role.id)
            except Exception:
                role = None
        if role:
            try:
                await interaction.user.add_roles(role)
            except Exception:
                pass
        await interaction.response.edit_message(
            content="✅ You've been registered for daily Wird tracking! You'll now be able to track your progress.",
            view=None
        )
    finally:
        await db.close()


async def assign_role(user: discord.Member, guild_id: int):
    db = Database()
    await db.connect()
    
    try:
        guild_config = await db.get_guild_config(guild_id)
        if guild_config and guild_config['wird_role_id']:
            role = user.guild.get_role(guild_config['wird_role_id'])
            if role and role not in user.roles:
                await user.add_roles(role)
    finally:
        await db.close()


async def remove_role(user: discord.Member, guild_id: int):
    db = Database()
    await db.connect()
    
    try:
        guild_config = await db.get_guild_config(guild_id)
        if guild_config and guild_config['wird_role_id']:
            role = user.guild.get_role(guild_config['wird_role_id'])
            if role and role in user.roles:
                await user.remove_roles(role)
    finally:
        await db.close()
