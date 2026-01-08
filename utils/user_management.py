import discord
from main import db


async def register_user_with_role(interaction: discord.Interaction):
    # use shared db instance
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
    # Do not close db here; keep connection open for app lifetime

    async def register_user_and_assign_role(user_or_interaction, guild_id, respond_func=None):
        """
        Registers the user and ensures the Wird role exists and is assigned.
        Works for both ApplicationContext (slash command) and Interaction (UI button).
        - user_or_interaction: discord.Member or discord.Interaction
        - guild_id: int
        - respond_func: async function to send a response (optional)
        """
        # use shared db instance
            # Determine user and guild objects
        if hasattr(user_or_interaction, 'user') and hasattr(user_or_interaction, 'guild_id'):
            # It's an Interaction
            user = user_or_interaction.user
            guild = user_or_interaction.guild
            interaction = user_or_interaction
        else:
            # It's a Member (from slash command)
            user = user_or_interaction
            guild = user.guild
            interaction = None

        await db.register_user(user.id, guild_id)
        guild_config = await db.get_guild_config(guild_id)
        role = None
        # Try to get the role from config, or create if missing
        if guild_config and guild_config['wird_role_id']:
            role = guild.get_role(guild_config['wird_role_id'])
        if not role:
            # Create the role if it doesn't exist
            try:
                role = await guild.create_role(name="Wird", reason="Wird registered users")
                await db.create_or_update_guild(guild_id, wird_role_id=role.id)
            except Exception:
                role = None
        if role:
            try:
                await user.add_roles(role)
            except Exception:
                pass

        # Respond appropriately
        if interaction:
            await interaction.response.edit_message(
                content="✅ You've been registered for daily Wird tracking! You'll now be able to track your progress.",
                view=None
            )
        elif respond_func:
                await respond_func("✅ You've been registered for daily Wird tracking! You'll now be able to track your progress.")
        # Do not close db here; keep connection open for app lifetime


async def assign_role(user: discord.Member, guild_id: int):
    # use shared db instance
    
    guild_config = await db.get_guild_config(guild_id)
    if guild_config and guild_config['wird_role_id']:
        role = user.guild.get_role(guild_config['wird_role_id'])
        if role and role not in user.roles:
            await user.add_roles(role)

    # assign_role is now handled by register_user_and_assign_role


async def remove_role(user: discord.Member, guild_id: int):
    # use shared db instance
    
    guild_config = await db.get_guild_config(guild_id)
    if guild_config and guild_config['wird_role_id']:
        role = user.guild.get_role(guild_config['wird_role_id'])
        if role and role in user.roles:
            await user.remove_roles(role)
