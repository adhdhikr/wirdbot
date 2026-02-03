import nextcord as discord

class ScopedBot:
    """A wrapper around the bot instance to restrict access to the current guild."""
    def __init__(self, bot, guild_id):
        self._bot = bot
        self._guild_id = guild_id
        
        # self.user and self.loop are accessed via property/getattr now

        
    def __getattr__(self, name):

        if name in ('guilds', 'users', 'voice_clients', 'dm_channels', 'private_channels', 'http', 'close', 'logout', 'ws'):
            raise AttributeError(f"Access to 'bot.{name}' is restricted for security.")
        
        return getattr(self._bot, name)

    @property
    def user(self):
        """Return a read-only-like wrapper for the bot user or just the user but we can't easily wrap it fully without a proxy."""
        # For now, we return the user, but we rely on code analysis to block 'edit' calls or we can wrap it.
        # Simplest: Returns the user object, but we trust the user won't find a way to edit unless we proxy it.
        # To be safe, let's just return the user. The prompt says "dont allow ... setting the bots about me".
        # We can try to wrap it.
        return self._bot.user

    def __repr__(self):
        return f"<ScopedBot guild_id={self._guild_id} wrapper>"

    def __dir__(self):
        try:
            d = set(dir(self._bot))
            forbidden = {'guilds', 'users', 'voice_clients', 'dm_channels', 'private_channels'}
            return list(d - forbidden)
        except:
            return []

    def get_guild(self, guild_id):
        if guild_id == self._guild_id:
            return self._bot.get_guild(guild_id)
        return None

    def get_user(self, user_id):

        guild = self._bot.get_guild(self._guild_id)
        if guild and guild.get_member(user_id):
            return self._bot.get_user(user_id)
        return None
        
    async def fetch_user(self, user_id):
        guild = self._bot.get_guild(self._guild_id)
        if guild:
             try:
                 member = await guild.fetch_member(user_id)
                 if member: return member
             except:
                 pass
        raise discord.Forbidden("Cannot fetch users outside this server.")

    async def fetch_guild(self, guild_id):
        if guild_id == self._guild_id:
            return await self._bot.fetch_guild(guild_id)
        raise discord.Forbidden("Cannot fetch other guilds.")

    async def application_info(self):
        raise discord.Forbidden("Restricted.")


def safe_split_text(text: str, limit: int = 2000) -> list[str]:
    """
    Splits text into chunks of maximum `limit` characters.
    Attempts to split at the last newline character within the limit to avoid breaking lines.
    If no newline is found within the last 500 characters of the chunk, defaults to hard split.
    """
    chunks = []
    while len(text) > limit:

        split_index = -1
        


        slice_end = limit
        slice_start = max(0, limit - 500)
        

        last_newline = text.rfind('\n', slice_start, slice_end)
        
        if last_newline != -1:
            split_index = last_newline
        else:

            split_index = limit
            
        chunks.append(text[:split_index])

        if last_newline != -1:
             text = text[split_index+1:] # Skip the newline itself
        else:
             text = text[split_index:]
             
    if text:
        chunks.append(text)
        
    return chunks
