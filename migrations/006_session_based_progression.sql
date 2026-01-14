-- Migration 006: Session-based progression system
-- This migration adds support for tracking completions per session instead of per day
-- and introduces session-based streaks

-- Add session_id to completions table to link completions to specific sessions
ALTER TABLE completions ADD COLUMN session_id INTEGER REFERENCES daily_sessions(id);

-- Add is_late flag to track late completions (completing old sessions)
ALTER TABLE completions ADD COLUMN is_late BOOLEAN DEFAULT 0;

-- Add completion tracking to sessions
ALTER TABLE daily_sessions ADD COLUMN is_completed BOOLEAN DEFAULT 0;
ALTER TABLE daily_sessions ADD COLUMN completed_at TIMESTAMP;

-- Add session-based streak to users (separate from legacy day-based streak)
ALTER TABLE users ADD COLUMN session_streak INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN longest_session_streak INTEGER DEFAULT 0;

-- Create indexes for session-based queries
CREATE INDEX IF NOT EXISTS idx_completions_session ON completions(session_id, user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_completed ON daily_sessions(guild_id, is_completed, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_guild_date ON daily_sessions(guild_id, session_date DESC);
