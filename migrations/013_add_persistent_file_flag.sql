-- Migration: Add is_persistent flag to user_files
-- Added on: 2026-01-29
-- Purpose: allow users to mark files as "saved forever" to bypass cleanup

ALTER TABLE user_files ADD COLUMN is_persistent BOOLEAN DEFAULT 0;
