CREATE TABLE IF NOT EXISTS guilds (
    guild_id INTEGER PRIMARY KEY,
    mosque_id TEXT,
    mushaf_type TEXT DEFAULT 'madani',
    channel_id INTEGER,
    pages_per_day INTEGER DEFAULT 1,
    current_page INTEGER DEFAULT 1,
    followup_channel_id INTEGER,
    followup_on_completion BOOLEAN DEFAULT 0,
    followup_after_send BOOLEAN DEFAULT 1,
    wird_role_id INTEGER,
    configured BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduled_times (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    time_type TEXT NOT NULL,
    time_value TEXT,
    enabled BOOLEAN DEFAULT 1,
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    registered BOOLEAN DEFAULT 1,
    current_streak INTEGER DEFAULT 0,
    longest_streak INTEGER DEFAULT 0,
    last_completion_date TEXT,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, guild_id),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS completions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    completion_date TEXT NOT NULL,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id, guild_id) REFERENCES users(user_id, guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS daily_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    session_date TEXT NOT NULL,
    start_page INTEGER NOT NULL,
    end_page INTEGER NOT NULL,
    message_ids TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_completions_user_guild_date ON completions(user_id, guild_id, completion_date);
CREATE INDEX IF NOT EXISTS idx_users_guild ON users(guild_id);
CREATE INDEX IF NOT EXISTS idx_scheduled_times_guild ON scheduled_times(guild_id);
CREATE INDEX IF NOT EXISTS idx_daily_sessions_guild_date ON daily_sessions(guild_id, session_date);
