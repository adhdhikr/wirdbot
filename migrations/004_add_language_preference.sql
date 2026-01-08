-- Add language_preference column to users table
ALTER TABLE users ADD COLUMN language_preference TEXT DEFAULT 'eng';