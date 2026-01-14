-- Migration 009: Add custom streak emoji column to users table
ALTER TABLE users ADD COLUMN streak_emoji TEXT DEFAULT '🔥';
