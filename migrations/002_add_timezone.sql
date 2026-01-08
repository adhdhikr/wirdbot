-- Add timezone column to guilds table
ALTER TABLE guilds ADD COLUMN timezone TEXT DEFAULT 'UTC';
