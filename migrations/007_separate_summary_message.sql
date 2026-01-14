-- Migration 007: Separate summary message ID from page message IDs
-- This migration adds a separate column to track the summary/progress message
-- so it doesn't get confused with the page messages

-- Add summary_message_id to daily_sessions to track the progress embed separately
ALTER TABLE daily_sessions ADD COLUMN summary_message_id INTEGER;
