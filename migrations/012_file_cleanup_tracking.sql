-- Migration: Add last_accessed tracking for auto-cleanup
-- Files will be auto-deleted after inactivity period unless user is active

-- Add last_accessed column to track when files were last used
ALTER TABLE user_files ADD COLUMN last_accessed TEXT DEFAULT CURRENT_TIMESTAMP;

-- Update existing files to have last_accessed = created_at
UPDATE user_files SET last_accessed = created_at WHERE last_accessed IS NULL;

-- Add indexes for cleanup queries
CREATE INDEX IF NOT EXISTS idx_user_files_last_accessed ON user_files(last_accessed);
CREATE INDEX IF NOT EXISTS idx_user_files_user_accessed ON user_files(user_id, last_accessed);
