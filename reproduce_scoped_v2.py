
import asyncio
import sys

# Mock classes
class MockUser:
    id = 123
    name = "User"

class MockGuild:
    id = 456
    name = "Guild"
    
    def get_member(self, uid):
        return MockUser()

class MockBot:
    user = MockUser()
    loop = asyncio.get_event_loop()
    
    def get_guild(self, did):
        if did == 456: return MockGuild()
        return None
    
    async def foo(self):
        return "bar"

# ScopedBot implementation from utils.py
class ScopedBot:
    """A wrapper around the bot instance to restrict access to the current guild."""
    def __init__(self, bot, guild_id):
        self._bot = bot
        self._guild_id = guild_id
        
        self.user = bot.user
        self.loop = bot.loop
        
    def __getattr__(self, name):
        if name in ('guilds', 'users', 'voice_clients', 'dm_channels', 'private_channels'):
            raise AttributeError(f"Access to 'bot.{name}' is restricted for security.")
        return getattr(self._bot, name)

async def test():
    bot = MockBot()
    scoped = ScopedBot(bot, 456)
    
    print(f"User: {scoped.user.name}")
    print(f"Method proxy: {await scoped.foo()}")
    
    try:
        print(scoped.guilds)
    except AttributeError as e:
        print(f"Caught expected error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
