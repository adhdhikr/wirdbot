# Wird Discord Bot

A modular Discord bot for managing daily Quran reading (Wird) with completion tracking, streaks, and prayer time integration.

## Project Structure

```
bot/
├── main_new.py              # Main bot entry point (NEW CLEAN VERSION)
├── main.py                  # Legacy monolithic version (DEPRECATED)
├── config.py                # Configuration and constants
├── database.py              # Database layer with migration system
├── views.py                 # Discord UI components (modals, buttons, views)
├── requirements.txt         # Python dependencies
├── .env                     # Environment variables (create from .env.example)
├── .env.example            # Environment variables template
├── migrations/             # SQL migration files
│   ├── 000_init.sql       # Initialize migrations table
│   └── 001_initial_schema.sql  # Initial database schema
├── cogs/                   # Command modules (cogs)
│   ├── admin.py           # Admin commands (/setup, /config, /schedule, etc.)
│   ├── user.py            # User commands (/register, /stats, etc.)
│   └── scheduler.py       # Background task for scheduled sending
└── utils/                  # Utility modules
    ├── completion.py      # Page completion logic
    ├── config.py          # Configuration handlers
    ├── followup.py        # Progress report messages
    ├── page_sender.py     # Page sending logic
    ├── scheduler.py       # Prayer time fetching and time validation
    └── user_management.py # User registration and role management
```

## Setup

### 1. Install Dependencies
```bash
cd bot
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
copy .env.example .env
```

Edit `.env`:
```env
DISCORD_TOKEN=your_bot_token_here
API_BASE_URL=http://localhost:5000
PRAYER_API_BASE_URL=https://api.mrie.dev/prayertimes
```

### 3. Run the Bot
```bash
python main_new.py
```

## Migration System

The bot now uses a proper migration system with versioned SQL files:

- **Migrations Directory**: `bot/migrations/`
- **Naming Convention**: `{version}_{name}.sql` (e.g., `001_initial_schema.sql`)
- **Automatic Execution**: Migrations run automatically on bot startup
- **Tracking**: Applied migrations are tracked in the `migrations` table

### Adding New Migrations

1. Create a new file in `migrations/` with the next version number:
   ```
   002_add_new_feature.sql
   ```

2. Write your SQL:
   ```sql
   CREATE TABLE new_feature (
       id INTEGER PRIMARY KEY,
       data TEXT
   );
   ```

3. Restart the bot - migration applies automatically

## Modular Architecture

### Cogs (Command Modules)

Each cog handles a specific domain:

- **AdminCog** (`cogs/admin.py`): Server configuration and management
- **UserCog** (`cogs/user.py`): User-facing commands
- **SchedulerCog** (`cogs/scheduler.py`): Background scheduling tasks

To add a new cog:
```python
# cogs/my_feature.py
from discord.ext import commands

class MyFeatureCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @discord.slash_command(name="my_command")
    async def my_command(self, ctx):
        await ctx.respond("Hello!")

def setup(bot):
    bot.add_cog(MyFeatureCog(bot))
```

The bot will automatically load it on startup!

### Utils (Helper Modules)

Utils contain reusable business logic:

- **completion.py**: Handles page completion, streak calculation
- **config.py**: Setup and configuration logic
- **followup.py**: Progress report generation
- **page_sender.py**: Page sending and session management
- **scheduler.py**: Prayer time API integration
- **user_management.py**: User registration and role assignment

### Views (UI Components)

All Discord UI components in one place:

- `SetupModal`: Initial configuration modal
- `ScheduleTimeModal`: Add custom time modal
- `CompletionButton`: Mark page as read button
- `PageView`: View with completion button
- `RegistrationView`: User registration prompt

## Database Layer

Clean, DRY database interface with helper methods:

```python
# Internal helpers for clean code
async def _execute_one(query, params) -> Optional[Dict]
async def _execute_many(query, params) -> List[Dict]
async def _execute_write(query, params)

# Public API
async def get_guild_config(guild_id) -> Optional[Dict]
async def create_or_update_guild(guild_id, **kwargs)
async def register_user(user_id, guild_id)
# ... etc
```

## Adding New Features

### Example: Adding a New Prayer Feature

1. **Create Migration** (`migrations/002_add_prayer_feature.sql`):
```sql
CREATE TABLE prayer_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    prayer_time TEXT,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

2. **Add Database Methods** (`database.py`):
```python
async def log_prayer(self, user_id: int, prayer_time: str):
    await self._execute_write(
        "INSERT INTO prayer_logs (user_id, prayer_time) VALUES (?, ?)",
        (user_id, prayer_time)
    )
```

3. **Create Cog** (`cogs/prayer.py`):
```python
class PrayerCog(commands.Cog):
    @discord.slash_command(name="log_prayer")
    async def log_prayer(self, ctx, prayer: str):
        db = Database()
        await db.connect()
        try:
            await db.log_prayer(ctx.author.id, prayer)
            await ctx.respond("✅ Prayer logged!")
        finally:
            await db.close()

def setup(bot):
    bot.add_cog(PrayerCog(bot))
```

4. **Restart bot** - everything loads automatically!

## Differences from Old Version

### Before (main.py):
- ❌ 600+ lines in one file
- ❌ Manual table creation (no migrations)
- ❌ Repeated `db.execute()` + `db.commit()` everywhere
- ❌ All commands in one file
- ❌ Hard to extend or maintain

### After (main_new.py):
- ✅ Modular cogs structure
- ✅ Migration system with versioning
- ✅ DRY database layer with helpers
- ✅ Clean separation of concerns
- ✅ Easy to add new features
- ✅ Proper logging throughout
- ✅ Type hints for better IDE support

## Running Tests

(To be implemented - add your test framework here)

## Contributing

When adding features:
1. Create appropriate migrations
2. Add database methods if needed
3. Create a new cog or extend existing one
4. Update this README with new commands
5. Test thoroughly before deployment

## Commands Reference

### Admin Commands
- `/setup` - Initial bot configuration
- `/config` - View current configuration
- `/schedule` - Manage scheduled times
- `/update` - Update specific settings
- `/set_role` - Set the Wird role
- `/send_now` - Manually trigger page sending

### User Commands
- `/register` - Register for Wird tracking
- `/unregister` - Unregister from tracking
- `/stats` - View personal statistics

## Support

For issues or questions, check the logs in the console or add proper error handling to your cogs.
