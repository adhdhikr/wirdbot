-- Add show_all_notifications column to guilds table
ALTER TABLE guilds ADD COLUMN show_all_notifications BOOLEAN DEFAULT 0;