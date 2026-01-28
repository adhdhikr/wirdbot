-- User file storage system
-- Each user gets a personal file space with limits:
--   - 100MB per file
--   - 1GB total storage per user

-- User files table - tracks individual files
CREATE TABLE IF NOT EXISTS user_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    mime_type TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, filename)
);

-- User storage quota tracking - aggregated stats
CREATE TABLE IF NOT EXISTS user_storage (
    user_id INTEGER PRIMARY KEY,
    total_bytes_used INTEGER DEFAULT 0,
    file_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for fast user file lookups
CREATE INDEX IF NOT EXISTS idx_user_files_user_id ON user_files(user_id);
CREATE INDEX IF NOT EXISTS idx_user_files_created ON user_files(created_at);
