import nextcord as discord



import inspect

class SecureProxy:
    """
    A recursive structural proxy that blocks all internal/private attribute access.
    This makes it impossible to reach __globals__, __dict__, __class__, etc.
    """
    def __init__(self, obj, forbidden_names=None):
        object.__setattr__(self, "_obj", obj)
        object.__setattr__(self, "_forbidden", forbidden_names or set())

    def __getattribute__(self, name):
        # Allow internal access to the wrapped object for the proxy itself
        if name in ("_obj", "_forbidden", "__getattribute__", "__getattr__", "__repr__", "__dir__"):
             return object.__getattribute__(self, name)
             
        # STRUCTURAL BLOCK: No underscores allowed, no forbidden names
        if name.startswith("_") or name in object.__getattribute__(self, "_forbidden"):
            raise AttributeError(f"❌ Security Error: Access to '{name}' is strictly prohibited.")

        attr = getattr(object.__getattribute__(self, "_obj"), name)

        # If it's a method/callable, wrap the result recursively
        if callable(attr):
            def wrapped(*args, **kwargs):
                # Clean args/kwargs (optional, but good for depth)
                res = attr(*args, **kwargs)
                
                if inspect.isawaitable(res):
                    async def async_wrapped():
                        inner_res = await res
                        if isinstance(inner_res, (str, int, float, bool, type(None))):
                            return inner_res
                        return SecureProxy(inner_res)
                    return async_wrapped()
                
                if isinstance(res, (str, int, float, bool, type(None))):
                    return res
                return SecureProxy(res)
            return wrapped
        
        # Recursive wrapping for attributes
        if isinstance(attr, (str, int, float, bool, type(None))):
            return attr
        return SecureProxy(attr)

    def __repr__(self):
        return f"<SecureProxy wrapping {type(object.__getattribute__(self, '_obj')).__name__}>"

    def __dir__(self):
        # Only show safe attributes in dir()
        return [attr for attr in dir(object.__getattribute__(self, "_obj")) if not attr.startswith("_")]


class ScopedBot(SecureProxy):
    """A structurally secured wrapper around the bot instance restricted to one guild."""
    def __init__(self, bot, guild_id):
        forbidden = {'guilds', 'users', 'voice_clients', 'dm_channels', 'private_channels', 'http', 'close', 'logout', 'ws'}
        super().__init__(bot, forbidden_names=forbidden)
        object.__setattr__(self, "_guild_id", guild_id)

    def get_guild(self, guild_id):
        if guild_id == object.__getattribute__(self, "_guild_id"):
            return SecureProxy(object.__getattribute__(self, "_obj").get_guild(guild_id))
        return None

    def get_user(self, user_id):
        guild = object.__getattribute__(self, "_obj").get_guild(object.__getattribute__(self, "_guild_id"))
        if guild and guild.get_member(user_id):
            return SecureProxy(object.__getattribute__(self, "_obj").get_user(user_id))
        return None
        
    async def fetch_user(self, user_id):
        guild = object.__getattribute__(self, "_obj").get_guild(object.__getattribute__(self, "_guild_id"))
        if guild:
             try:
                 member = await guild.fetch_member(user_id)
                 if member:
                     return SecureProxy(member)
             except Exception:
                 pass
        raise discord.Forbidden("Cannot fetch users outside this server.")

    async def fetch_guild(self, guild_id):
        if guild_id == object.__getattribute__(self, "_guild_id"):
            res = await object.__getattribute__(self, "_obj").fetch_guild(guild_id)
            return SecureProxy(res)
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
